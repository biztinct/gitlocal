import importlib.util
from pathlib import Path
import unittest
from datetime import datetime, timedelta, timezone
spec=importlib.util.spec_from_file_location('policy_engine',Path(__file__).parents[1]/'engine.py')
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
TZ=timezone(timedelta(hours=7))
BANDS=[dict(category='worker',minimum=0,maximum=1,hours=0,confirmed=True),dict(category='worker',minimum=1,maximum=10,hours=0,confirmed=False),dict(category='worker',minimum=10,maximum=None,hours=4,confirmed=True),dict(category='manager',minimum=0,maximum=10,hours=0,confirmed=True),dict(category='manager',minimum=10,maximum=None,hours=1,confirmed=True)]
class EngineTest(unittest.TestCase):
 def calc(self,minutes=0,category='worker',finish=20.5,extra=(),kind='weekday'):
  start=datetime(2026,11,18,7,30,tzinfo=TZ)
  end=start+timedelta(hours=finish-7.5)
  return engine.calculate([start+timedelta(minutes=minutes),end,*extra],start,start+timedelta(hours=9),start+timedelta(hours=13),[(start+timedelta(hours=4),start+timedelta(hours=5))],BANDS,category,kind)
 def test_normal_and_ot(self):
  r=self.calc();self.assertEqual((r['normal_hours'],r['overtime_hours'],r['break_hours']),(8,4,1))
 def test_worker_additional_not_replacement(self):
  r=self.calc(10);self.assertAlmostEqual(r['normal_hours'],8-10/60-4);self.assertEqual(r['overtime_hours'],4)
 def test_manager_threshold(self):
  self.assertEqual(self.calc(9,'manager')['penalty_hours'],0)
  self.assertEqual(self.calc(10,'manager')['penalty_hours'],1)
  self.assertAlmostEqual(self.calc(120,'manager')['normal_hours'],5)
 def test_unknown_band(self):
  self.assertIn('confirmation',self.calc(1)['error']);self.assertIn('confirmation',self.calc(9)['error'])
 def test_floor_zero_and_penalty_spill(self):
  r=self.calc(10,finish=10);self.assertEqual(r['normal_hours'],0);self.assertAlmostEqual(r['penalty_hours'],2.5-10/60)
 def test_duplicates_and_middle_punches(self):
  middle=datetime(2026,11,18,11,30,tzinfo=TZ)
  self.assertEqual(self.calc(extra=(middle,middle))['normal_hours'],8)
 def test_partial_break(self):
  r=self.calc(finish=12);self.assertEqual(r['break_hours'],.5);self.assertEqual(r['normal_hours'],4)
 def test_early_arrival_not_paid(self):
  r=self.calc(-60);self.assertEqual(r['normal_hours'],8)
 def test_rest_day(self):
  r=self.calc(kind='weekend');self.assertEqual(r['normal_hours'],0);self.assertEqual(r['overtime_hours'],12)
 def test_overnight(self):
  start=datetime(2026,11,18,19,30,tzinfo=TZ);end=start+timedelta(hours=12)
  r=engine.calculate([start,end],start,start+timedelta(hours=9),end,[(start+timedelta(hours=4),start+timedelta(hours=5))],BANDS,'worker')
  self.assertEqual((r['normal_hours'],r['overtime_hours'],r['break_hours']),(8,3,1))
 def test_missing_punch(self):
  t=datetime(2026,11,18,7,30,tzinfo=TZ)
  self.assertIn('error',engine.calculate([t],t,t+timedelta(hours=9),t+timedelta(hours=13),[],BANDS,'worker'))
 def test_paid_grace_preserves_actual_punches_and_threshold(self):
  start=datetime(2026,11,18,7,30,tzinfo=TZ);end=start+timedelta(hours=9)
  bands=[dict(b, confirmed=True, pay_late_minutes=(b['maximum'] is not None and b['maximum'] <=10)) for b in BANDS]
  for category,penalty in [('worker',4),('manager',1)]:
   for minutes in [0,.5,1,9,9.99,10,60]:
    first=start+timedelta(minutes=minutes)
    result=engine.calculate([first,end],start,end,end,[(start+timedelta(hours=4),start+timedelta(hours=5))],bands,category)
    self.assertEqual(result['first'],first.isoformat())
    self.assertAlmostEqual(result['worked_hours'],8-minutes/60)
    self.assertAlmostEqual(result['late_minutes'],minutes)
    self.assertAlmostEqual(result['normal_hours'],8 if minutes<10 else 8-minutes/60-penalty)
 def test_long_shift_two_breaks_and_partial_checkout(self):
  start=datetime(2026,11,18,7,30,tzinfo=TZ);end=start+timedelta(hours=20.5)
  breaks=[(start+timedelta(hours=a),start+timedelta(hours=b)) for a,b in [(4,5),(16,17)]]
  result=engine.calculate([start,end],start,start+timedelta(hours=9),end,breaks,BANDS,'worker')
  self.assertEqual((result['normal_hours'],result['overtime_hours'],result['break_hours']),(8,10.5,2))
  partial=engine.calculate([start,start+timedelta(hours=16.5)],start,start+timedelta(hours=9),end,breaks,BANDS,'worker')
  self.assertEqual((partial['normal_hours'],partial['overtime_hours'],partial['break_hours']),(8,7,1.5))
if __name__=='__main__':unittest.main()
