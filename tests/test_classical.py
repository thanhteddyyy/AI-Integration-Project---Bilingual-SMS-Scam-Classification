import unittest

import pandas as pd

from scam_baseline.models.classical import build_naive_bayes, build_svm


class ClassicalSmokeTests(unittest.TestCase):
    def _config(self):
        return {
            "seed": 42,
            "models": {
                "naive_bayes": {
                    "word_ngram_range": [1, 2],
                    "min_df": 1,
                    "max_df": 1.0,
                    "max_features": 1000,
                    "sublinear_tf": True,
                    "alpha": 0.5,
                },
                "svm": {
                    "word_ngram_range": [1, 2],
                    "char_ngram_range": [3, 5],
                    "min_df": 1,
                    "max_df": 1.0,
                    "word_max_features": 1000,
                    "char_max_features": 2000,
                    "sublinear_tf": True,
                    "C": 1.0,
                    "class_weight": "balanced",
                },
            },
        }

    def test_models_fit_and_predict(self):
        texts = pd.Series(
            [
                "see you at class",
                "meeting moved to ten",
                "limited offer buy now",
                "discount today only",
                "verify bank account now",
                "send otp to unlock account",
            ]
        )
        labels = pd.Series(
            ["legitimate", "legitimate", "spam", "spam", "scam", "scam"]
        )
        for model in [build_naive_bayes(self._config()), build_svm(self._config())]:
            model.fit(texts, labels)
            predictions = model.predict(texts)
            self.assertEqual(len(predictions), len(texts))


if __name__ == "__main__":
    unittest.main()

