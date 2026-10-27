import unittest

import pandas as pd

from scam_baseline.data.split import assert_no_group_leakage, assign_splits


class SplitTests(unittest.TestCase):
    def _config(self):
        return {
            "seed": 42,
            "data": {
                "external_dataset": "smishx",
                "drop_exact_duplicates": True,
                "min_clean_characters": 1,
            },
            "split": {
                "train_fraction": 0.7,
                "validation_fraction": 0.15,
                "test_fraction": 0.15,
                "external_overlap_policy": "exclude_development",
                "label_conflict_policy": "exclude",
            },
        }

    def test_external_overlap_is_removed_from_development(self):
        rows = []
        labels = ["legitimate", "spam", "scam"]
        for label in labels:
            for index in range(12):
                rows.append(
                    {
                        "source_dataset": "sms_phishing",
                        "text_clean": f"{label} {index}",
                        "label_level_1": label,
                        "group_id": f"{label}_{index}",
                        "strict_duplicate_key": f"{label}_{index}",
                        "label_conflict": False,
                        "exact_duplicate_rank": 1,
                    }
                )
        rows.extend(
            [
                {
                    "source_dataset": "smishx",
                    "text_clean": "external overlap",
                    "label_level_1": "scam",
                    "group_id": "shared",
                    "strict_duplicate_key": "shared_text",
                    "label_conflict": False,
                    "exact_duplicate_rank": 1,
                },
                {
                    "source_dataset": "sms_phishing",
                    "text_clean": "development overlap",
                    "label_level_1": "scam",
                    "group_id": "shared",
                    "strict_duplicate_key": "shared_text",
                    "label_conflict": False,
                    "exact_duplicate_rank": 1,
                },
            ]
        )
        result = assign_splits(pd.DataFrame(rows), self._config())
        external = result[result["source_dataset"].eq("smishx")].iloc[0]
        development = result[
            result["source_dataset"].eq("sms_phishing")
            & result["group_id"].eq("shared")
        ].iloc[0]
        self.assertEqual(external["split"], "external_test")
        self.assertEqual(development["split"], "excluded")
        self.assertEqual(development["exclusion_reason"], "overlap_with_external_test")
        assert_no_group_leakage(result)

    def test_internal_test_dataset_and_overlap_removal(self):
        config = {
            "seed": 42,
            "data": {
                "test_dataset": "spamscam_test",
                "external_dataset": "corpus_ext",
                "drop_exact_duplicates": True,
                "min_clean_characters": 1,
            },
            "split": {
                "train_fraction": 0.85,
                "validation_fraction": 0.15,
                "test_fraction": 0.0,
                "test_overlap_policy": "exclude_development",
                "external_overlap_policy": "exclude_development",
                "label_conflict_policy": "exclude",
            },
        }
        rows = []
        for index in range(20):
            label = "legitimate" if index % 2 == 0 else "risky"
            rows.append(
                {
                    "source_dataset": "spamscam_train",
                    "text_clean": f"train {index}",
                    "label_level_1": label,
                    "group_id": f"train_grp_{index}",
                    "strict_duplicate_key": f"train_{index}",
                    "label_conflict": False,
                    "exact_duplicate_rank": 1,
                }
            )
        rows.append(
            {
                "source_dataset": "spamscam_test",
                "text_clean": "test message",
                "label_level_1": "risky",
                "group_id": "test_grp_1",
                "strict_duplicate_key": "test_1",
                "label_conflict": False,
                "exact_duplicate_rank": 1,
            }
        )
        rows.append(
            {
                "source_dataset": "spamscam_train",
                "text_clean": "overlapping train message",
                "label_level_1": "risky",
                "group_id": "test_grp_1",
                "strict_duplicate_key": "test_1_dup",
                "label_conflict": False,
                "exact_duplicate_rank": 1,
            }
        )
        result = assign_splits(pd.DataFrame(rows), config)
        test_row = result[result["source_dataset"].eq("spamscam_test")].iloc[0]
        overlapping_train = result[
            result["source_dataset"].eq("spamscam_train")
            & result["text_clean"].eq("overlapping train message")
        ].iloc[0]
        self.assertEqual(test_row["split"], "test")
        self.assertEqual(overlapping_train["split"], "excluded")
        self.assertEqual(overlapping_train["exclusion_reason"], "overlap_with_internal_test")
        assert_no_group_leakage(result)


if __name__ == "__main__":
    unittest.main()
