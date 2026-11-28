import unittest

from scam_baseline.data.clean import (
    clean_text,
    strict_duplicate_key,
    template_duplicate_key,
)


class CleaningTests(unittest.TestCase):
    def test_clean_text_preserves_model_signals(self):
        value = "  Verify\nNOW at https://bank.example/7  OTP=1234  "
        cleaned = clean_text(value)
        self.assertEqual(
            cleaned, "Verify NOW at https://bank.example/7 OTP=1234"
        )

    def test_template_key_masks_dynamic_fields(self):
        first = "Pay 100 now at https://bad.example/a"
        second = "Pay 900 now at https://bad.example/b"
        self.assertEqual(template_duplicate_key(first), template_duplicate_key(second))
        self.assertNotEqual(strict_duplicate_key(first), strict_duplicate_key(second))


if __name__ == "__main__":
    unittest.main()

