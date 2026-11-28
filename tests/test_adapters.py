import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scam_baseline.data.adapters import (
    load_custom_dataset,
    load_imc25,
    load_smishx,
    load_sms_phishing,
)


class AdapterTests(unittest.TestCase):
    def test_sms_phishing_mapping_is_case_insensitive(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sms.csv"
            pd.DataFrame(
                {
                    "LABEL": ["ham", "Spam", "Smishing"],
                    "TEXT": ["a", "b", "c"],
                    "URL": ["No"] * 3,
                    "EMAIL": ["No"] * 3,
                    "PHONE": ["No"] * 3,
                }
            ).to_csv(path, index=False)
            result = load_sms_phishing(path)
            self.assertEqual(
                result["label_level_1"].tolist(),
                ["legitimate", "spam", "scam"],
            )

    def test_smishx_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "smishx.csv"
            pd.DataFrame(
                {
                    "SMS": ["a", "b", "c"],
                    "label": ["legitimate", "spam", "smishing"],
                    "if_URL": ["0"] * 3,
                    "if_phone": ["0"] * 3,
                    "if_email": ["0"] * 3,
                }
            ).to_csv(path, index=False)
            result = load_smishx(path)
            self.assertEqual(
                result["label_level_1"].tolist(),
                ["legitimate", "spam", "scam"],
            )

    def test_imc_filters_english_and_prepares_level_two(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "imc.csv"
            base = {
                "time": ["2025", "2025", "2025"],
                "sender_id": [None] * 3,
                "telephone_number_type": [None] * 3,
                "original_network_name": [None] * 3,
                "original_network_country": [None] * 3,
                "url_shortener": [None] * 3,
                "named_entity": [None] * 3,
                "lure_principles": [None] * 3,
                "text": ["bank", "ad", "hola"],
                "language": ["English", "English", "Spanish"],
                "scam_type": ["banking", "spam", "delivery"],
            }
            pd.DataFrame(base).to_csv(path, index=False)
            result = load_imc25(path, language_filter="English")
            self.assertEqual(len(result), 2)
            self.assertEqual(result["source_dataset"].tolist(), ["imc25", "imc25"])
            self.assertEqual(result["label_level_1"].tolist(), ["scam", "spam"])
            self.assertEqual(result["scam_type"].tolist(), ["banking_finance", "unknown"])

    def test_load_custom_tsv_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corpus.txt"
            with open(path, "w", encoding="utf-8") as f:
                f.write("ham\tTin nhan hop le\n")
                f.write("spam\tTin nhan lua dao\n")
            spec = {
                "name": "custom_corpus",
                "path": str(path),
                "text_column": "text",
                "label_column": "label",
                "language": "vi",
                "sep": "\t",
                "names": ["label", "text"],
                "label_mapping": {
                    "ham": "legitimate",
                    "spam": "risky",
                },
            }
            result = load_custom_dataset(spec, directory)
            self.assertEqual(len(result), 2)
            self.assertEqual(result["label_level_1"].tolist(), ["legitimate", "risky"])
            self.assertEqual(result["text_raw"].tolist(), ["Tin nhan hop le", "Tin nhan lua dao"])

    def test_custom_dataset_scam_type_column_only_for_scam(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vi.csv"
            pd.DataFrame(
                {
                    "message": ["a", "b", "c", "d"],
                    "label_3class": ["legitimate", "scam", "spam", "scam"],
                    "scam_type": ["none", "banking_finance", "none", ""],
                }
            ).to_csv(path, index=False)
            spec = {
                "name": "vi",
                "path": str(path),
                "text_column": "message",
                "label_column": "label_3class",
                "scam_type_column": "scam_type",
                "language": "vi",
                "label_mapping": {"legitimate": "legitimate", "spam": "spam", "scam": "scam"},
            }
            result = load_custom_dataset(spec, directory)
            self.assertEqual(
                result["scam_type"].tolist(),
                ["unknown", "banking_finance", "unknown", "unknown"],
            )


class EnglishPlaceholderTests(unittest.TestCase):
    def test_imc_tags_and_raw_text_end_up_identical(self):
        from scam_baseline.data.adapters import normalize_en_placeholders as norm

        imc = "CALL <NAMED_ENTITY> ON <PHONE_NUMBER> BEFORE <DATE_TIME> OR VISIT <URL>"
        raw = "CALL ON 0871 230 0220 BEFORE 12/05/2024 OR VISIT http://bit.ly/abc"
        self.assertEqual(norm(imc), norm(raw))
        self.assertEqual(norm(raw), "CALL ON <PHONE> BEFORE <DATE_TIME> OR VISIT <URL>")

    def test_ids_emails_times_and_money(self):
        from scam_baseline.data.adapters import normalize_en_placeholders as norm

        self.assertEqual(norm("code <US_DRIVER_LICENSE> mail a.b@x.com at 10:30pm"),
                         "code <NUMBER> mail <EMAIL> at <DATE_TIME>")
        self.assertEqual(norm("Refund of $573.00 to amazon.com/x"), "Refund of $573.00 to <URL>")
        self.assertEqual(norm("ref 1234567"), "ref <NUMBER>")


if __name__ == "__main__":
    unittest.main()
