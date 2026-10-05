import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scam_baseline.data.adapters import load_imc25, load_smishx, load_sms_phishing


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


if __name__ == "__main__":
    unittest.main()
