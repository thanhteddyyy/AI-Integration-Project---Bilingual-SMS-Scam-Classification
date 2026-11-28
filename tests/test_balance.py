import random
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import balance_datasets as bd  # noqa: E402


def _row(sample_id, text, label, split="train", group=None):
    return {
        "sample_id": sample_id, "source_record_id": f"src:{sample_id}", "text_raw": text,
        "text_clean": text, "label_level_1": label, "split": split, "group_id": group or f"g_{sample_id}",
        "is_augmented": False, "aug_parent_id": "", "aug_ops": "",
    }


class AugmentOpsTests(unittest.TestCase):
    def test_strip_diacritics_keeps_placeholders(self):
        out = bd.op_strip_diacritics("Tài khoản [MONEY] đã bị khóa", random.Random(0))
        self.assertEqual(out, "Tai khoan [MONEY] da bi khoa")
        self.assertIsNone(bd.op_strip_diacritics("Tai khoan da bi khoa", random.Random(0)))

    def test_entity_swap_stays_in_group(self):
        out = bd.op_entity("Vietcombank thong bao: tai khoan bi khoa", random.Random(1))
        self.assertNotIn("Vietcombank", out)
        self.assertTrue(any(bank in out for bank in bd.ENTITY_GROUPS["bank"]))

    def test_synonym_matches_whole_words_only(self):
        # "tai khoanx" must not be touched
        self.assertIsNone(bd.op_synonym("tai khoanx abc", random.Random(0)))

    def test_variant_differs_from_original(self):
        rng = random.Random(3)
        for text in ["Quý khách vui lòng xác thực tài khoản tại https://x.top",
                     "Chuc mung ban trung thuong [MONEY], lien he [NUMBER]"]:
            result = bd.make_variant(text, rng)
            self.assertIsNotNone(result)
            self.assertNotEqual(result[0], text)
            self.assertIn(result[0].count("["), (text.count("["),))


class AugmentVietnameseTests(unittest.TestCase):
    def test_augmented_rows_are_new_unique_and_traceable(self):
        train = pd.DataFrame([
            _row("a", "Quý khách vui lòng xác thực tài khoản Vietcombank tại https://x.top", "scam"),
            _row("b", "Chúc mừng bạn trúng thưởng [MONEY], liên hệ ngay", "scam"),
            _row("c", "Mẹ ơi con về muộn", "legitimate"),
            _row("d", "Hẹn gặp lúc 7h", "legitimate"),
            _row("e", "Cảm ơn nhé", "legitimate"),
            _row("f", "Ok anh", "legitimate"),
            _row("g", "Đã nhận", "legitimate"),
        ])
        test = pd.DataFrame([_row("t", "Chuc mung ban trung thuong [MONEY], lien he ngay", "scam", split="test")])
        all_rows = pd.concat([train, test], ignore_index=True)
        aug = bd.augment_vietnamese(train, all_rows, ["scam"], max_per_row=2, rng=random.Random(0))
        self.assertGreater(len(aug), 0)
        self.assertLessEqual(len(aug), 4)
        self.assertTrue(aug["sample_id"].is_unique)
        self.assertFalse(aug["sample_id"].isin(all_rows["sample_id"]).any())
        self.assertTrue(set(aug["aug_parent_id"]) <= {"a", "b"})
        self.assertTrue((aug["text_raw"] == aug["text_clean"]).all())
        keys = set(all_rows["text_raw"].map(bd.template_duplicate_key))
        # never recreates an existing message, including the test one
        self.assertFalse(aug["text_raw"].map(bd.template_duplicate_key).isin(keys).any())
        # group_id is the parent's
        parent_group = dict(zip(train["sample_id"], train["group_id"]))
        self.assertTrue((aug["group_id"] == aug["aug_parent_id"].map(parent_group)).all())

    def test_integrity_rejects_duplicate_ids_and_aug_outside_train(self):
        df = pd.DataFrame([_row("a", "x", "scam"), _row("a", "y", "scam")])
        with self.assertRaises(AssertionError):
            bd.assert_integrity(df, "t")
        df = pd.DataFrame([_row("a", "x", "scam", split="test")])
        df["is_augmented"] = True
        with self.assertRaises(AssertionError):
            bd.assert_integrity(df, "t")


if __name__ == "__main__":
    unittest.main()
