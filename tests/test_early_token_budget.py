import unittest
from unittest.mock import patch
from datetime import datetime,timezone
from early_token_budget import calculate
import research_hourly as budget

def stamp(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()
class AverageTests(unittest.TestCase):
 def usage(self):return {'tracking_started_at':stamp(0),'updated_at':stamp(7200),'entries':[{'timestamp':stamp(100),'tokens':800},{'timestamp':stamp(3700),'tokens':780},{'timestamp':stamp(7300),'tokens':900}]}
 def test_example_ignores_partial_hour(self):
  result=calculate(self.usage(),7500)
  self.assertEqual(result['average_tokens_per_hour'],790)
  self.assertEqual(result['early_token_budget'],355)
 def test_stale_and_missing(self):
  self.assertEqual(calculate(self.usage(),20000)['early_token_budget'],0)
  self.assertEqual(calculate({},7500)['early_token_budget'],0)
 def test_unknown(self):
  data=self.usage();data['entries'][0]['unreported_responses']=1
  self.assertEqual(calculate(data,7500)['early_token_budget'],0)
 def test_cap_floor(self):
  data=self.usage();data['entries'][0]['tokens']=3000
  self.assertEqual(calculate(data,7500)['early_token_budget'],0)
 def test_early_reservations_across_runs(self):
  state={'entries':[]}
  with patch.dict('os.environ',{'EARLY_RESEARCH_AUTO':'1'}),patch('early_token_budget.current',return_value={'early_token_budget':355}),patch.object(budget,'update',side_effect=lambda fn:fn(state,10000)):
   budget.reserve(350)
   with self.assertRaises(budget.BudgetPause):budget.reserve(10)
   budget.reserve(5)
