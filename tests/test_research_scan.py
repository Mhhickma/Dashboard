import csv
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from research_keepa import connect
from research_scan import run,KeepaClient
from research_funnel import normalize,reasons
from research_server import ROOT
from research_server import Store
import research_jobs
import io
import zipfile

class ScanTests(unittest.TestCase):
    def setUp(self):
        self.cfg=json.loads((ROOT/'research-config.json').read_text())
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.cwd=Path.cwd();os.chdir(self.tmp.name);self.addCleanup(os.chdir,self.cwd)
        folder=Path('data/creator-connections');folder.mkdir(parents=True)
        with (folder/'20260901T000000.csv').open('w',newline='') as f:
            w=csv.writer(f);w.writerow(['Campaign ID','Campaign Name','Brand','Commission','Start Date','End Date','ASIN List'])
            w.writerow(['1','Eligible','Brand','9.5%','2020-01-01','2099-01-01','B000000001 B000000002 B000000003'])
            w.writerow(['2','Low','Brand','9%','2020-01-01','2099-01-01','B000000004'])
        self.db=connect(Path('state.sqlite'));self.addCleanup(self.db.close)
        self.request={'job':'one','limit':2,'batch_size':1,'token_budget':2,'config':self.cfg,'filters':{'exclude_apparel':False,'exclude_categories':'','price_min':20}}
    def client(self):
        c=Mock();c.reserved=0;c.consumed=0;c.balance=10;c.unknown=False
        c.fetch.side_effect=lambda asins:([{'asin':a,'title':'Product','stats':{'current':[-1,3000]},'productType':0} for a in asins],None)
        return c
    def test_bounded_cc_funnel_and_new_cohort(self):
        client=self.client();result=run(self.db,self.request,client,time.monotonic()+60,Path('out'))
        self.assertEqual(result['selected'],2);self.assertEqual(client.fetch.call_count,2)
        self.assertEqual(result['matched'],2)
        request={**self.request,'job':'two'};client=self.client();result=run(self.db,request,client,time.monotonic()+60,Path('out2'))
        self.assertEqual(result['selected'],1);self.assertEqual(client.fetch.call_args.args[0],['B000000003'])
    def test_resume_never_requeries_completed(self):
        client=self.client();success=client.fetch.side_effect
        client.fetch.side_effect=[success(['B000000001']),(None,'paused_tokens')]
        result=run(self.db,self.request,client,time.monotonic()+60,Path('out'));self.assertEqual(result['phase'],'paused_tokens')
        client=self.client();result=run(self.db,self.request,client,time.monotonic()+60,Path('out'))
        self.assertEqual(client.fetch.call_args.args[0],['B000000002']);self.assertEqual(client.fetch.call_count,1);self.assertEqual(result['evaluated'],2)
    def test_missing_growth_cannot_pass_bsr(self):
        f=normalize({'growth_min':10,'exclude_apparel':False,'exclude_categories':''},self.cfg)
        self.assertIn('growth_min',reasons({'cc_active':True,'commission':10,'growth':None,'bsr90':80},f,self.cfg))
    def test_resume_rejects_changed_funnel(self):
        run(self.db,self.request,self.client(),time.monotonic()+60,Path('out'))
        self.request['limit']=3
        with self.assertRaises(ValueError):run(self.db,self.request,self.client(),time.monotonic()+60,Path('out'))
    def test_budget_and_no_paid_refresh_parameters(self):
        session=Mock();response=Mock();response.status_code=200;response.json.return_value={'products':[],'tokensConsumed':1,'tokensLeft':0};session.get.return_value=response
        client=KeepaClient('private-test-value',1,time.monotonic()+300,session)
        client.fetch(['B000000001']);products,error=client.fetch(['B000000002'])
        self.assertEqual(error,'paused_budget');self.assertEqual(session.get.call_count,1)
        params=session.get.call_args.kwargs['params'];self.assertEqual(params['update'],-1);self.assertNotIn('offers',params)
    def test_retry_reservations_bound_actual_attempts(self):
        session=Mock();response=Mock();response.status_code=503;response.headers={};response.json.return_value={};session.get.return_value=response
        client=KeepaClient('secret',2,time.monotonic()+300,session)
        with patch('research_scan.time.sleep'):
            _,error=client.fetch(['B000000001'])
        self.assertEqual(error,'paused_budget');self.assertEqual(session.get.call_count,2);self.assertTrue(client.unknown)
    def test_dispatch_is_explicit_and_duplicate_protected(self):
        store=Store(Path('local.sqlite'))
        with patch('research_jobs.github.api',return_value={}) as api:
            job=research_jobs.start(store,{'limit':100,'batch_size':10,'token_budget':100,'filters':{}})
            self.assertEqual(job['state'],'queued')
            dispatch=api.call_args.args
            self.assertTrue(dispatch[0].endswith('/dispatches'))
            request=json.loads(dispatch[1]['inputs']['request'])
            self.assertEqual(request['limit'],100)
            with self.assertRaises(ValueError):research_jobs.start(store,{})
            self.assertEqual(sum(str(c.args[0]).endswith('/dispatches') for c in api.call_args_list),1)
    def test_completed_artifact_import_preserves_notes(self):
        store=Store(Path('local.sqlite'))
        with patch('research_jobs.github.api',return_value={}):job=research_jobs.start(store,{'filters':{}})
        with store.db() as db:
            payload=json.loads(db.execute('SELECT payload FROM jobs WHERE id=?',(job['id'],)).fetchone()[0])
            store.put(db,{'asin':'B000000001'},[],store.config())
        store.save_shortlist('B000000001',{'status':'Researching','priority':'High','notes':'keep this'})
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as archive:
            archive.writestr('status.json',json.dumps({'job':job['request']['job'],'phase':'complete','matched':1}))
            archive.writestr('products.jsonl',json.dumps({'base':{'asin':'B000000001','title':'Returned'},'campaigns':[],'raw':{},'passed':True,'failed_filters':[]})+'\n')
        stream.seek(0)
        with patch('research_jobs.github.api',side_effect=[{'workflow_runs':[{'id':55,'display_title':'Film Research '+payload['ticket'],'html_url':'https://github.com/Mhhickma/Dashboard/actions/runs/55','status':'completed','conclusion':'success'}]},{'artifacts':[{'id':1,'name':'film-research-result','expired':False}]}]),patch('research_jobs.github.artifact',return_value=stream):
            result=research_jobs.status(store)
        self.assertEqual(result['state'],'complete')
        self.assertEqual(store.detail('B000000001')['shortlist']['notes'],'keep this')
        self.assertEqual(store.query({'scan_job':str(job['id']),'cc_only':'false','commission_min':'','exclude_categories':''})['total'],1)

if __name__=='__main__':unittest.main()
