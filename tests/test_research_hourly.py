import unittest
from unittest.mock import patch
import research_hourly as budget
class BudgetTests(unittest.TestCase):
 def setUp(self):self.state={'safe_after':0,'entries':[]};self.now=10000
 def change(self,fn):
  self.state['entries']=[e for e in self.state['entries'] if e['time']>self.now-3600]
  return fn(self.state,self.now)
 def test_combined_allowance_unknown_and_refund(self):
  with patch.object(budget,'update',side_effect=self.change):
   price=budget.reserve(1000);budget.settle(price,936)
   research=budget.reserve(514)
   with self.assertRaises(budget.BudgetPause):budget.reserve(1)
   budget.settle(research,None)
   with self.assertRaises(budget.BudgetPause):budget.reserve(1)
   budget.settle(research,500);budget.reserve(14)
   with self.assertRaises(budget.BudgetPause):budget.reserve(1)
   self.now+=3601;budget.reserve(1450)
 def test_warmup(self):
  self.state['safe_after']=11000
  with patch.object(budget,'update',side_effect=self.change):
   with self.assertRaises(budget.BudgetPause):budget.reserve(1)
