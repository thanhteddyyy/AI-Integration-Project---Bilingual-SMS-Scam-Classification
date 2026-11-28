import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scam_baseline.data.overrides import apply_label_overrides


def _frame():
    return pd.DataFrame({
        "source_record_id": ["imc25:1", "imc25:2", "sms:9", "imc25:3", "imc25:4"],
        "text_raw": ["Your Uber code: 1234", "You won a prize! claim <URL>", "Your Uber code: 1234",
                     "hey free for coffee? reply STOP", "unrelated"],
        "label_level_1": ["scam", "spam", "scam", "scam", "legitimate"],
        "scam_type": ["other_scam", "unknown", "other_scam", "other_scam", "unknown"],
    })


class OverrideTests(unittest.TestCase):
    def _write(self, directory, rows):
        path = Path(directory) / "o.csv"
        pd.DataFrame(rows).to_csv(path, index=False)
        return path

    def test_relabel_propagates_to_exact_copies_and_drops(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, [
                {"source_record_id": "imc25:1", "text": "Your Uber code: 1234", "review_label": "legitimate",
                 "review_scam_type": ""},
                {"source_record_id": "imc25:2", "text": "You won a prize! claim <URL>", "review_label": "scam",
                 "review_scam_type": "prize_lottery"},
                {"source_record_id": "imc25:3", "text": "hey free for coffee? reply STOP", "review_label": "drop",
                 "review_scam_type": ""},
            ])
            result, report = apply_label_overrides(_frame(), [path], directory)
        self.assertEqual(result["source_record_id"].tolist(), ["imc25:1", "imc25:2", "sms:9", "imc25:4"])
        self.assertEqual(result["label_level_1"].tolist(), ["legitimate", "scam", "legitimate", "legitimate"])
        self.assertEqual(result["scam_type"].tolist(), ["unknown", "prize_lottery", "unknown", "unknown"])
        self.assertEqual(report["rows_dropped"], 1)
        self.assertEqual(report["rows_relabelled"], 3)

    def test_changed_text_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, [
                {"source_record_id": "imc25:1", "text": "something else", "review_label": "legitimate"},
            ])
            with self.assertRaises(ValueError):
                apply_label_overrides(_frame(), [path], directory)

    def test_unknown_record_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, [
                {"source_record_id": "imc25:999", "text": "", "review_label": "spam"},
            ])
            with self.assertRaises(ValueError):
                apply_label_overrides(_frame(), [path], directory)


if __name__ == "__main__":
    unittest.main()
