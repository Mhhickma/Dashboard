import tempfile
import unittest
from datetime import date
from pathlib import Path

from early_cc import accepted_ids_from_csv, merge_accepted, upcoming


class EarlyCcTests(unittest.TestCase):
    def test_accepted_csv_requires_campaign_id(self):
        with self.assertRaisesRegex(ValueError, 'Campaign Id'):
            accepted_ids_from_csv('ASIN List\nB000000001\n')

    def test_accepted_history_merges_and_filters_upcoming(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cc = root / 'cc'
            cc.mkdir()
            (cc / 'campaigns.csv').write_text(
                'Campaign Id,Campaign Start Date,Campaign Name,Commission Rate\n'
                'C1,2026-10-01,One,10%\nC2,2026-10-02,Two,15%\n', encoding='utf-8')
            history = root / '.research' / 'accepted-cc.json'
            first = merge_accepted(history, 'Campaign ID\nC1\n')
            second = merge_accepted(history, 'campaign_id\nC1\nC3\n')
            self.assertEqual({k: first[k] for k in ('imported', 'added', 'accepted_total')},
                             {'imported': 1, 'added': 1, 'accepted_total': 1})
            self.assertEqual({k: second[k] for k in ('imported', 'added', 'accepted_total')},
                             {'imported': 2, 'added': 1, 'accepted_total': 2})
            self.assertTrue(second['accepted_updated_at'].endswith('+00:00'))
            result = upcoming(cc, date(2026, 9, 23), history)
            self.assertEqual(result['campaign_ids'], ['C2'])
            self.assertEqual(result['accepted_total'], 2)
            self.assertEqual(result['accepted_excluded'], 1)
            self.assertEqual(result['upcoming_total'], 2)
            self.assertEqual(result['accepted_updated_at'], second['accepted_updated_at'])

    def test_legacy_history_uses_file_date_for_countdown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cc = root / 'cc'
            cc.mkdir()
            (cc / 'campaigns.csv').write_text(
                'Campaign Id,Campaign Start Date\nC1,2026-10-01\n', encoding='utf-8')
            history = root / 'accepted.json'
            history.write_text('{"campaign_ids":["C1"]}', encoding='utf-8')
            result = upcoming(cc, date(2026, 9, 23), history)
            self.assertIsNotNone(result['accepted_updated_at'])


if __name__ == '__main__':
    unittest.main()
