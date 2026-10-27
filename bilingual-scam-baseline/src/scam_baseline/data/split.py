from __future__ import annotations

import pandas as pd
from sklearn.model_selection import train_test_split


def assign_splits(frame: pd.DataFrame, config: dict) -> pd.DataFrame:
    result = frame.copy()
    data_cfg = config["data"]
    split_cfg = config["split"]
    result["split"] = "pending"
    result["exclusion_reason"] = ""

    invalid_text = result["text_clean"].str.len() < int(
        data_cfg.get("min_clean_characters", 1)
    )
    invalid_label = result["label_level_1"].isna()
    result.loc[invalid_text, "split"] = "excluded"
    result.loc[invalid_text, "exclusion_reason"] = "empty_or_short_text"
    result.loc[invalid_label, "split"] = "excluded"
    result.loc[invalid_label, "exclusion_reason"] = "unmapped_label"

    # Predefined external test datasets
    external_raw = data_cfg.get("external_dataset", [])
    if isinstance(external_raw, str):
        external_names = {external_raw} if external_raw else set()
    else:
        external_names = set(external_raw or [])
    if external_names:
        external_mask = result["source_dataset"].isin(external_names) & result["split"].eq("pending")
        result.loc[external_mask, "split"] = "external_test"

    # Handle label conflicts in duplicate groups
    conflict_mask = result["label_conflict"] & result["split"].isin(
        ["pending", "external_test"]
    )
    if split_cfg.get("label_conflict_policy", "exclude") == "exclude":
        result.loc[conflict_mask, "split"] = "excluded"
        result.loc[conflict_mask, "exclusion_reason"] = "label_conflict_in_duplicate_group"

    # Exclude development rows overlapping with external test
    if external_names and split_cfg.get("external_overlap_policy") == "exclude_development":
        external_groups = set(
            result.loc[result["source_dataset"].isin(external_names), "group_id"]
        )
        overlap_mask = (
            result["group_id"].isin(external_groups)
            & ~result["source_dataset"].isin(external_names)
            & result["split"].eq("pending")
        )
        result.loc[overlap_mask, "split"] = "excluded"
        result.loc[overlap_mask, "exclusion_reason"] = "overlap_with_external_test"

    # Predefined internal test datasets
    test_raw = data_cfg.get("test_dataset", [])
    if isinstance(test_raw, str):
        test_names = {test_raw} if test_raw else set()
    else:
        test_names = set(test_raw or [])
    if test_names:
        test_mask = result["source_dataset"].isin(test_names) & result["split"].eq("pending")
        result.loc[test_mask, "split"] = "test"

        # Exclude remaining development rows overlapping with internal test
        if split_cfg.get("test_overlap_policy", "exclude_development") == "exclude_development":
            internal_test_groups = set(
                result.loc[result["source_dataset"].isin(test_names), "group_id"]
            )
            overlap_test_mask = (
                result["group_id"].isin(internal_test_groups)
                & ~result["source_dataset"].isin(test_names)
                & result["split"].eq("pending")
            )
            result.loc[overlap_test_mask, "split"] = "excluded"
            result.loc[overlap_test_mask, "exclusion_reason"] = "overlap_with_internal_test"

    if data_cfg.get("drop_exact_duplicates", True):
        candidate_mask = result["split"].isin(["pending", "external_test", "test"])
        candidate_ranks = (
            result.loc[candidate_mask]
            .groupby(["split", "strict_duplicate_key"], sort=False)
            .cumcount()
            .add(1)
        )
        exact_duplicate_mask = pd.Series(False, index=result.index)
        exact_duplicate_mask.loc[candidate_ranks.index] = candidate_ranks.gt(1)
        result.loc[exact_duplicate_mask, "split"] = "excluded"
        result.loc[exact_duplicate_mask, "exclusion_reason"] = "exact_duplicate_non_primary"

    eligible = result[result["split"].eq("pending")]
    groups = (
        eligible.groupby("group_id", as_index=False)
        .agg(label_level_1=("label_level_1", "first"))
        .sort_values("group_id")
        .reset_index(drop=True)
    )
    if groups.empty:
        raise ValueError("No development groups remain after filtering")

    seed = int(config["seed"])
    test_fraction = float(split_cfg.get("test_fraction", 0.15))
    validation_fraction = float(split_cfg.get("validation_fraction", 0.15))

    assignments: dict[str, str] = {}
    if test_fraction > 0:
        holdout_fraction = test_fraction + validation_fraction
        train_groups, holdout_groups = _stratified_group_partition(
            groups,
            test_size=holdout_fraction,
            seed=seed,
        )
        relative_test_fraction = test_fraction / holdout_fraction
        validation_groups, test_groups = _stratified_group_partition(
            holdout_groups,
            test_size=relative_test_fraction,
            seed=seed + 1,
        )
        assignments.update({group_id: "train" for group_id in train_groups["group_id"]})
        assignments.update(
            {group_id: "validation" for group_id in validation_groups["group_id"]}
        )
        assignments.update({group_id: "test" for group_id in test_groups["group_id"]})
    else:
        # Predefined test set is already assigned; partition pending groups into train and validation
        train_groups, validation_groups = _stratified_group_partition(
            groups,
            test_size=validation_fraction,
            seed=seed,
        )
        assignments.update({group_id: "train" for group_id in train_groups["group_id"]})
        assignments.update(
            {group_id: "validation" for group_id in validation_groups["group_id"]}
        )

    result.loc[result["split"].eq("pending"), "split"] = result.loc[
        result["split"].eq("pending"), "group_id"
    ].map(assignments)
    if result["split"].isna().any() or result["split"].eq("pending").any():
        raise RuntimeError("Split assignment left unresolved rows")
    return result


def _stratified_group_partition(
    groups: pd.DataFrame, *, test_size: float, seed: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    label_counts = groups["label_level_1"].value_counts()
    stratify = groups["label_level_1"] if int(label_counts.min()) >= 2 else None
    left, right = train_test_split(
        groups,
        test_size=test_size,
        random_state=seed,
        shuffle=True,
        stratify=stratify,
    )
    return left.reset_index(drop=True), right.reset_index(drop=True)


def assert_no_group_leakage(frame: pd.DataFrame) -> None:
    active = frame[frame["split"].isin(["train", "validation", "test", "external_test"])]
    group_split_count = active.groupby("group_id")["split"].nunique()
    leaking = group_split_count[group_split_count > 1]
    if not leaking.empty:
        raise AssertionError(
            f"Found {len(leaking)} duplicate groups across active splits"
        )

