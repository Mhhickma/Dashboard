import tempfile,unittest
from pathlib import Path
from prime_match import match
class PrimeMatchTests(unittest.TestCase):
 def test_boundary_missing_overlap_and_dedup(self):
  with tempfile.TemporaryDirectory() as d:
   Path(d,'cc.csv').write_text('Campaign Id,ASIN List\nC1,B000000001 B000000002\nC1,B000000001\nC2,B000000002\n')
   result=match('asin,promotionPrice,lowestPriceYtd\nB000000001,110,100\nB000000002,80,100\nB000000003,111,100\nB000000004,10,0\nB000000005,90,100\nB000000001,109,100\n',d)
   self.assertEqual([r['asin'] for r in result['rows']],['B000000002','B000000001'])
   self.assertEqual(result['rows'][1]['event_price'],109)
   self.assertEqual(result['campaign_ids'],['C1','C2'])
   self.assertEqual(result['above_limit'],1)
   self.assertEqual(result['invalid_rows'],1)
   self.assertEqual(result['not_in_cc'],1)
