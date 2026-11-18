import unittest
from filing_tracker.benchmark import drift


def record(recall=19, seconds=1.0, engine_hash='a'):
    return {'engine_hashes': {'filing_tracker/core.py': engine_hash},
            'results': [{'pair': 'p', 'engine': 'v2', 'comparison_seconds': seconds,
                         'changed_decision_recall': {'numerator': recall, 'denominator': 19}}]}


class BenchmarkDriftTest(unittest.TestCase):
    def test_timings_alone_are_not_drift(self):
        self.assertEqual(drift(record(seconds=1.2), record(seconds=3.4)), [])

    def test_changed_metric_is_drift(self):
        self.assertEqual(drift(record(recall=18), record()),
                         ['results.0.changed_decision_recall.numerator'])

    def test_changed_code_hash_is_drift(self):
        self.assertEqual(drift(record(engine_hash='b'), record()),
                         ['engine_hashes.filing_tracker/core.py'])

    def test_missing_result_row_is_drift(self):
        short = record()
        short['results'] = []
        self.assertEqual(drift(record(), short), ['results'])


if __name__ == '__main__':
    unittest.main()
