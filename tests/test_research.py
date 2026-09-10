import json
import tempfile
import unittest
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path
from research_model import KeepaVideos,score
from research_server import Store,ROOT,handler

class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'research.sqlite');self.cfg=self.store.config()
    def add(self,asin,commission=9.5):
        c={'campaign_id':'one','commission':commission,'start':'2020-01-01','end':'2099-01-01'}
        with self.store.db() as db:self.store.put(db,{'asin':asin,'title':'Product','price':50,'category':'Tools','monthly_sold':500},[c],self.cfg)
    def test_commission_strict_and_pagination(self):
        self.add('B000000001',9);self.add('B000000002');self.add('B000000003',10)
        result=self.store.query({'size':'1'});self.assertEqual(result['total'],2);self.assertEqual(len(result['rows']),1)
        self.assertEqual(self.store.query({'commission_min':'0'})['total'],3)
    def test_shortlist_survives_import_and_filters(self):
        self.add('B000000001');self.store.save_shortlist('B000000001',{'status':'Researching','priority':'High','notes':'My note'})
        self.add('B000000001',1)
        self.assertEqual(self.store.query({'view':'shortlist'})['total'],1)
        self.assertEqual(self.store.detail('B000000001')['shortlist']['notes'],'My note')
    def test_missing_video_not_zero(self):
        self.assertIsNone(KeepaVideos().normalize({})['influencer_videos'])
        self.assertIsNone(KeepaVideos().normalize({'videos':[{'url':'x','creator':'Main'}]})['influencer_videos'])
        self.assertIsNone(KeepaVideos().normalize({'videos':[],'offersSuccessful':False})['total_videos'])
    def test_score_unknown_coverage(self):
        points,components,coverage=score({},self.cfg)
        self.assertEqual((points,coverage),(0,0));self.assertIsNone(components['competition']['points'])
    def test_invalid_settings_rollback(self):
        cfg=self.store.config();cfg['weights']['competition']=999
        with self.assertRaises(ValueError):self.store.save_settings(cfg)
        self.assertEqual(self.store.config(),self.cfg)
    def test_search_is_parameterized(self):
        self.add('B000000001');self.assertEqual(self.store.query({'q':"' OR 1=1 --"})['total'],0)
    def test_api_private_files_and_csrf(self):
        self.add('B000000001')
        server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.store));server.csrf='test-session'
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base=f'http://127.0.0.1:{server.server_port}'
            with urllib.request.urlopen(base+'/api/products') as response:
                self.assertEqual(json.load(response)['total'],1)
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(base+'/.research/research.sqlite')
            self.assertEqual(error.exception.code,404)
            request=urllib.request.Request(base+'/api/shortlist/B000000001',data=b'{}',method='POST')
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
            self.assertEqual(error.exception.code,403)
            request=urllib.request.Request(base+'/api/products',headers={'Origin':'https://example.com'})
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
            self.assertEqual(error.exception.code,403)
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
