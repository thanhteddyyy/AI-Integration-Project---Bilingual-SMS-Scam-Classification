import unittest

from sklearn.metrics import fbeta_score, matthews_corrcoef

from scam_baseline.evaluation import compute_metrics


CLASSES = ["legitimate", "spam", "scam"]


class ComputeMetricsTests(unittest.TestCase):
    def test_scam_f2_and_mcc(self):
        truth = ["scam", "scam", "scam", "scam", "spam", "legitimate", "legitimate"]
        pred = ["scam", "scam", "scam", "legitimate", "scam", "legitimate", "spam"]
        metrics = compute_metrics(truth, pred, CLASSES)
        # scam: precision 3/4, recall 3/4 -> F2 = 0.75
        self.assertAlmostEqual(metrics["scam_f2"], 0.75)
        self.assertAlmostEqual(
            metrics["scam_f2"],
            fbeta_score(truth, pred, beta=2, labels=["scam"], average="macro"),
        )
        self.assertAlmostEqual(metrics["mcc"], matthews_corrcoef(truth, pred))
        self.assertEqual(metrics["positive_label"], "scam")
        self.assertEqual(metrics["scam_support"], 4)

    def test_f2_weighs_recall_more_than_precision(self):
        truth = ["scam", "scam", "legitimate", "legitimate"]
        high_recall = compute_metrics(truth, ["scam", "scam", "scam", "scam"], CLASSES)
        high_precision = compute_metrics(truth, ["scam", "legitimate", "legitimate", "legitimate"], CLASSES)
        self.assertGreater(high_recall["scam_f2"], high_precision["scam_f2"])

    def test_no_scam_in_split_gives_zero_not_error(self):
        truth = ["legitimate", "spam", "legitimate"]
        pred = ["legitimate", "spam", "legitimate"]
        metrics = compute_metrics(truth, pred, CLASSES)
        self.assertEqual(metrics["scam_f2"], 0.0)
        self.assertEqual(metrics["scam_support"], 0)
        self.assertAlmostEqual(metrics["mcc"], 1.0)

    def test_wilson_interval_and_false_alarm_rate(self):
        truth = ["scam"] * 10 + ["legitimate"] * 4
        pred = ["scam"] * 8 + ["spam"] * 2 + ["scam"] + ["legitimate"] * 3
        metrics = compute_metrics(truth, pred, CLASSES)
        low, high = metrics["scam_recall_ci95"]
        self.assertAlmostEqual(low, 0.490, places=2)   # 8/10 -> [0.49, 0.94]
        self.assertAlmostEqual(high, 0.943, places=2)
        self.assertAlmostEqual(metrics["scam_fpr"], 0.25)
        self.assertIsNone(compute_metrics(["spam"], ["spam"], CLASSES)["scam_recall_ci95"])

    def test_binary_risky_positive_label(self):
        metrics = compute_metrics(["risky", "legitimate"], ["risky", "legitimate"], ["legitimate", "risky"])
        self.assertEqual(metrics["positive_label"], "risky")
        self.assertAlmostEqual(metrics["scam_f2"], 1.0)


if __name__ == "__main__":
    unittest.main()
