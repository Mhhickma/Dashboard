import unittest,tempfile,json
from pathlib import Path
from sales_catalog import ingest,current,query
class SalesCatalogTests(unittest.TestCase):
 def test_current_lists_and_full_catalog(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);cc=root/'data/creator-connections';cc.mkdir(parents=True)
   f=cc/'list.csv';f.write_text('Campaign Id,ASIN List\nC1,B000000001\nC2,B000000001\n')
   ingest(root,'asin,promotionPrice,lowestPriceYtd,productCategory\nB000000001,9,10,Tools\nB000000002,20,10,Books\n')
   (root/'.research/accepted-cc.json').write_text(json.dumps({'campaign_ids':['C1']}))
   r=current(root,False);self.assertEqual(r['campaign_ids'],['C2']);self.assertEqual(len(r['rows']),1)
   q=query(root,{'sort':'promotionPrice','direction':'desc'});self.assertEqual(q['total'],2);self.assertEqual(q['rows'][0][0],'B000000002')
   self.assertEqual(query(root,{'exclude':'["Books"]'})['total'],1)
   f.write_text('Campaign Id,ASIN List\nC3,B000000001\n')
   self.assertEqual(current(root,False)['campaign_ids'],['C3'])
   with self.assertRaises(ValueError):ingest(root,'wrong\n1\n')
   self.assertEqual(query(root,{})['total'],2)
