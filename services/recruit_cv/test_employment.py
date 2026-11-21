import unittest
from employment import employment_records


class EmploymentEvidence(unittest.TestCase):
    def test_explicit_labels_and_partial_dates(self):
        rows = employment_records('Company: Acme\nJob title: Agronomist\nJan 2021 – December 2023\nCompany: Seed Ltd\nRole: Advisor\n2024 - Present')
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[0]['employer'], rows[0]['title'], rows[0]['start'], rows[0]['end']), ('Acme', 'Agronomist', '2021-01', '2023-12'))
        self.assertTrue(rows[1]['current'])
        self.assertEqual(rows[1]['start'], '2024')
        self.assertEqual(rows[1]['end'], '')
        self.assertIn('Only the year', rows[1]['note'])
        self.assertIn('Company: Acme', rows[0]['source'])

    def test_vietnamese_and_indonesian(self):
        for text in ['Kỹ sư tại Acme\ntháng 2/2020 đến hiện tại', 'Engineer di Acme\nFebruari 2020 sampai sekarang']:
            row = employment_records(text)[0]
            self.assertEqual(row['employer'], 'Acme')
            self.assertEqual(row['start'], '2020-02')
            self.assertTrue(row['current'])

    def test_ambiguous_titles_are_not_guessed(self):
        row = employment_records('Acme Developer 2021 - 2025')[0]
        self.assertEqual(row['employer'], '')
        self.assertEqual(row['title'], '')
        self.assertIn('Acme Developer', row['source'])
        self.assertEqual(employment_records('An undated career description'), [])

    def test_month_validation_and_reversed_dates(self):
        row = employment_records('Engineer at Acme 2023-13 - 2025-01')[0]
        self.assertEqual(row['start'], '')
        self.assertIn('unrecognised', row['note'])
        row = employment_records('Engineer at Acme 2025-06 - 2023-01')[0]
        self.assertIn('precedes', row['note'])

    def test_year_first_and_numeric_months(self):
        row = employment_records('Engineer at Acme\n2020-02 - 03/2021')[0]
        self.assertEqual((row['start'], row['end']), ('2020-02', '2021-03'))
