import tempfile
import unittest
from pathlib import Path
from cc_batches import active_csv_files

class BatchTests(unittest.TestCase):
    def test_atomic_replacement(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);old=p/'september.csv';old.write_text('ASIN List\nB000000001\n')
            new=p/'20261001-replacement-0000-000000.csv';new.write_text('ASIN List\nB000000002\n')
            self.assertEqual(active_csv_files(p),[old])
            marker=p/'20261001-replacement-complete.csv'
            marker.write_text('ASIN List,Batch file\n,'+new.name+'\n')
            self.assertEqual(active_csv_files(p),[new])
            new.unlink()
            with self.assertRaises(ValueError):active_csv_files(p)
