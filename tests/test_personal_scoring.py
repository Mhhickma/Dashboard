import unittest
from research_model import sales_minimum,qualification,score
class ScoringRules(unittest.TestCase):
 def test_sales_curve(self):
  self.assertEqual(sales_minimum(25),300);self.assertAlmostEqual(sales_minimum(100),50);self.assertEqual(sales_minimum(500),25);self.assertGreater(sales_minimum(10),300)
 def test_missing_and_known_failure(self):
  row=dict(price=25,monthly_sold=300,cc_active=True,commission=10,merchant_video=True,total_videos=10,category='Tools')
  self.assertEqual(qualification(row)[1:],([],[]))
  self.assertIn('Merchant video',qualification({**row,'merchant_video':None})[2])
  self.assertIn('At most 10 total videos',qualification({**row,'total_videos':11})[1])
