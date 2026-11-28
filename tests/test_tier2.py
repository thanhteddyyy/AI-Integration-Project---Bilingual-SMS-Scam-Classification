import pandas as pd
import pytest

from scam_baseline.data.scam_types import VI_TIER2_CLASSES, VI_TIER2_GROUPS, merge_vi_scam_type
from scam_baseline.tier2 import assign_family_splits, load_tuan_scams, tier2_metrics

FRACTIONS = {"train": 0.7, "validation": 0.15, "test": 0.15}


def _toy(n_families: dict[str, int], size: int = 2):
    labels, families = [], []
    for label, count in n_families.items():
        for f in range(count):
            labels += [label] * size
            families += [f"{label}_{f}"] * size
    return pd.Series(labels), pd.Series(families)


def test_whole_families_stay_in_one_split_and_every_class_reaches_val_and_test():
    labels, families = _toy({"a": 20, "b": 5, "c": 3})
    split = assign_family_splits(labels, families, FRACTIONS, seed=1)
    assert (pd.DataFrame({"f": families, "s": split}).groupby("f")["s"].nunique() == 1).all()
    for label in ("a", "b", "c"):
        assert set(split[labels == label]) == {"train", "validation", "test"}


def test_split_is_deterministic():
    labels, families = _toy({"a": 15, "b": 6})
    first = assign_family_splits(labels, families, FRACTIONS, seed=7)
    assert first.equals(assign_family_splits(labels, families, FRACTIONS, seed=7))


def test_mixed_family_is_rejected():
    with pytest.raises(ValueError):
        assign_family_splits(pd.Series(["a", "b"]), pd.Series(["f", "f"]), FRACTIONS, seed=0)


def test_load_tuan_scams_dedups_merges_and_keeps_only_scam(tmp_path):
    pd.DataFrame({
        "message_id": ["1", "2", "3", "4"],
        "message": ["Khoa SIM ngay", "Khoa SIM ngay", "Xin chao", "Trung thuong"],
        "label_3class": ["scam", "scam", "legitimate", "scam"],
        "scam_type": ["telecom_account", "telecom_account", "none", "prize_lottery"],
    }).to_csv(tmp_path / "a.csv", index=False)
    config = {"_project_root": str(tmp_path), "data": {"extra_datasets": [{
        "name": "a", "path": "a.csv", "text_column": "message", "label_column": "label_3class",
        "scam_type_column": "scam_type", "id_column": "message_id"}]}}
    data = load_tuan_scams(config)
    assert len(data) == 2
    row = data[data["text_clean"].eq("Khoa SIM ngay")].iloc[0]
    assert row["label_level_1"] == "gov_utility_services" and row["copies"] == 2
    assert row["source_record_id"] == "1;2"


def test_class_list_and_groups_are_consistent():
    assert set(VI_TIER2_CLASSES) == set(VI_TIER2_GROUPS)
    assert merge_vi_scam_type("government_services") == "gov_utility_services"
    metrics = tier2_metrics(["loan_debt", "job_task_scam"], ["investment", "job_task_scam"], VI_TIER2_CLASSES)
    # loan_debt and investment are both definition group 3.2 -> correct at group level
    assert metrics["accuracy"] == 0.5 and metrics["group_level"]["accuracy"] == 1.0


def test_crawl_goes_to_train_only_and_never_leaks_a_val_or_test_template():
    from scam_baseline.tier2 import add_crawl_to_train
    frame = pd.DataFrame({
        "sample_id": ["t1", "t2"], "text_clean": [
            "Tai khoan Vietcombank cua quy khach bi khoa vui long dang nhap ngay de xac thuc",
            "Con dang cap cuu o benh vien can dong vien phi gap bo me chuyen ngay giup con"],
        "label_level_1": ["banking_finance", "social_impersonation"], "split": ["test", "train"],
        "group_id": ["fam_0", "fam_1"], "source_dataset": "spamscam_train", "copies": 1})
    crawl = pd.DataFrame({
        "sample_id": ["c1", "c2", "c3"], "source_dataset": "crawl", "text_clean": [
            "Tai khoan Vietcombank cua quy khach bi khoa vui long dang nhap ngay de xac thuc tai link",  # test template
            "Co du tien khong cho muon tam co viec sang mai gui lai duoc khong",                         # new template
            "Con dang cap cuu o benh vien can dong vien phi gap bo me chuyen ngay giup con nhe"],         # train template
        "label_level_1": ["banking_finance", "social_impersonation", "social_impersonation"]})
    out, skipped = add_crawl_to_train(frame, crawl, threshold=0.5)
    added = out[out["source_dataset"].eq("crawl")]
    assert set(added["sample_id"]) == {"c2", "c3"} and added["split"].eq("train").all()
    assert skipped["sample_id"].tolist() == ["c1"]
    assert out.loc[out["sample_id"].eq("c3"), "group_id"].item() == "fam_1"  # joins the Tuan family
    assert out[out["sample_id"].isin(["t1", "t2"])]["split"].tolist() == ["test", "train"]  # unchanged


def test_mask_payee_bank_only_masks_the_receiving_account():
    from scam_baseline.tier2 import mask_payee_bank
    assert mask_payee_bank("Bo/me chuyen ngay vao STK [NUMBER] Vietcombank giup con") == \
        "Bo/me chuyen ngay vao STK [NUMBER] [PAYEE_BANK] giup con"
    assert mask_payee_bank("me chuyen vao [NUMBER] (Sacombank) dung goi con") == "me chuyen vao [NUMBER] ([PAYEE_BANK]) dung goi con"
    sender = "[Vietcombank] Tai khoan cua quy khach bi khoa, dang nhap vcb-xacminh.com"
    assert mask_payee_bank(sender) == sender
