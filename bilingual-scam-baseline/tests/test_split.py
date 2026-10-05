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


if __name__ == "__main__":
    unittest.main()
