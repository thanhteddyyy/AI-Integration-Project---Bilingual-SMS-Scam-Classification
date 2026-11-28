import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed")
class CharCnnSmokeTests(unittest.TestCase):
    def test_vocabulary_is_train_only_and_bounded(self):
        from scam_baseline.models.charcnn import CharVocabulary

        vocabulary = CharVocabulary.fit(
            ["abc", "abz"], max_size=5, min_frequency=1
        )
        encoded = vocabulary.encode("abx", max_length=5)
        self.assertEqual(len(encoded), 5)
        self.assertLessEqual(len(vocabulary), 5)


if __name__ == "__main__":
    unittest.main()

