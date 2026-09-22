import unittest
from filing_tracker.numbers import compare_numbers, date_only_change

class NumericRegressions(unittest.TestCase):
    def test_signed_growth_reversal(self):
        result = compare_numbers('Revenue decreased 10%.', 'Revenue increased 5%.', 2023, 2024)
        row = result['comparisons'][0]
        self.assertEqual((row['old']['value'], row['new']['value']), (-10, 5))
        self.assertEqual(row['percentage_point_change'], 15)

    def test_decrease_by_and_decrease_to_have_different_roles(self):
        row = compare_numbers('Revenue decreased by $10 million.', 'Revenue increased by $5 million.', 2023, 2024)['comparisons'][0]
        self.assertEqual(row['absolute_change'], 15000000)
        row = compare_numbers('Revenue decreased to $90 million.', 'Revenue increased to $95 million.', 2023, 2024)['comparisons'][0]
        self.assertEqual(row['old']['value'], 90000000)
        self.assertEqual(row['absolute_change'], 5000000)

    def test_multi_metric_sentence_abstains(self):
        row = compare_numbers('Revenue was $100 million and gross margin was 20%.', 'Revenue was $120 million and gross margin was 22%.', 2023, 2024)
        self.assertEqual(row['comparisons'], [])
        self.assertTrue(any('Multiple metrics' in reason for reason in row['abstentions']))

    def test_separate_metric_sentences_remain_supported(self):
        rows = compare_numbers('Revenue was $100 million. Gross margin was 20%.', 'Revenue was $120 million. Gross margin was 22%.', 2023, 2024)['comparisons']
        self.assertEqual({(r['metric'],r['unit'],r['absolute_change']) for r in rows}, {('revenue','USD',20000000),('gross margin','percent',2)})

    def test_money_and_counts_are_not_date_rollovers(self):
        for old,new in [('Revenue was $ 2023.','Revenue was $ 2024.'),('Revenue was USD 2023.','Revenue was USD 2024.'),('We employ 2023 people.','We employ 2024 people.')]:
            self.assertFalse(date_only_change(old,new))
        self.assertTrue(date_only_change('Report for fiscal year 2023','Report for fiscal year 2024'))
        row = compare_numbers('Revenue was $ 2023.','Revenue was $ 2024.',2023,2024)['comparisons'][0]
        self.assertEqual(row['absolute_change'],1)

    def test_specific_metric_wins_over_its_generic_substring(self):
        rows=compare_numbers('Microsoft Cloud revenue increased 22% to $111.6 billion.','Microsoft Cloud revenue increased 23% to $137.4 billion.',2023,2024)['comparisons']
        self.assertEqual(len(rows),2)
        self.assertTrue(all(r['metric']=='Microsoft Cloud revenue' for r in rows))
