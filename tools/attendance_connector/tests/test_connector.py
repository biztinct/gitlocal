import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ['PAYOBOOK_LOCAL_TEST'] = '1'
spec = importlib.util.spec_from_file_location('connector', Path(__file__).parents[1] / 'connector.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)


class CollectorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.home = Path(self.temp.name)
        self.config = {'server': 'https://example.invalid', 'token': 'test-only', 'database': 'unused',
                       'remote': {'history_from': '2026-09-01', 'interval_minutes': 15}}
    def tearDown(self):
        self.temp.cleanup()
    def test_replay_queue_and_exact_dedup(self):
        q = c.Queue(self.home); q.add([{'x': 1}, {'x': 1}, {'x': 2}])
        self.assertEqual(q.count(), 2)
        keys = [k for k, _ in q.batch()]; q.acknowledge(keys)
        q.add([{'x': 1}]); self.assertEqual(q.count(), 0)
        self.assertIsNone(q.db.execute('select payload from events limit 1').fetchone()[0])
        q.replay(); q.add([{'x': 1}]); self.assertEqual(q.count(), 1); q.close()
    def test_outage_keeps_rows_and_restart_retries(self):
        def offline(*args): raise OSError('offline')
        with patch.object(c, 'extract', return_value=([{'TimeStr': 'bad'}, {'TimeStr': 'valid'}], {'read_ok': True})):
            with self.assertRaises(OSError): c.sync(self.home, self.config, offline)
        q=c.Queue(c.queue_home(self.home,self.config)); self.assertEqual(q.count(),2); q.close()
        received=[]
        def online(server, operation, payload, token):
            received.extend(payload['rows']); return {'acknowledged':len(payload['rows']), 'config':self.config['remote']}
        with patch.object(c,'extract',side_effect=OSError('file locked')):
            result=c.sync(self.home,self.config,online)
        self.assertEqual(len(received),2); self.assertIn('file locked',result['error'])
    def test_partial_ack_never_discards(self):
        with patch.object(c,'extract',return_value=([{'x':1}], {'read_ok':True})):
            with self.assertRaises(RuntimeError):
                c.sync(self.home,self.config,lambda *args:{'acknowledged':0})
        q=c.Queue(c.queue_home(self.home,self.config)); self.assertEqual(q.count(),1); q.close()
    def test_late_punch_not_max_timestamp_filtered(self):
        uploaded=[]
        def sender(a,b,payload,d):
            uploaded.extend(payload['rows']); return {'acknowledged':len(payload['rows'])}
        for rows in [[{'time':'2026-11-12'}],[{'time':'2026-11-12'},{'time':'2026-09-03'}]]:
            with patch.object(c,'extract',return_value=(rows, {'read_ok':True})):
                c.sync(self.home,self.config,sender)
        self.assertEqual(uploaded,[{'time':'2026-11-12'},{'time':'2026-09-03'}])
    def test_https_and_no_path_or_credentials(self):
        for url in ['http://example.com','https://user:secret@example.com','https://example.com/x','https://example.com?db=x']:
            with self.assertRaises(ValueError): c.post(url,'sync',{})
    def test_repair_to_another_source_keeps_queues_isolated(self):
        a=dict(self.config,remote={'connector_id':1})
        b=dict(self.config,remote={'connector_id':2})
        qa=c.Queue(c.queue_home(self.home,a));qa.add([{'employee':'source-a-only'}]);qa.close()
        qb=c.Queue(c.queue_home(self.home,b));self.assertEqual(qb.count(),0);qb.close()
        qa=c.Queue(c.queue_home(self.home,a));self.assertEqual(qa.count(),1);qa.close()
    def test_config_roundtrip(self):
        c.save_config(self.home,self.config); self.assertEqual(c.load_config(self.home),self.config)

if __name__=='__main__': unittest.main()
