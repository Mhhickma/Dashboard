"""Durable local control for explicitly requested GitHub scans."""
import json
import time
import uuid
import zipfile
import threading
from research_funnel import normalize
import research_github as github

LOCK=threading.Lock()
ACTIVE={'dispatching','queued','in_progress','waiting','requested','pending','dispatch_unknown'}

def start(store,data):
    with LOCK:
        limit=int(data.get('limit',100));batch=int(data.get('batch_size',10));budget=int(data.get('token_budget',100))
        if not 1<=limit<=1000 or not 1<=batch<=100 or not 1<=budget<=1000:raise ValueError('Use 1–1,000 ASINs/tokens and batch size 1–100')
        # Verify deployment/access before recording any paid dispatch.
        github.api('/actions/workflows/'+github.WORKFLOW)
        with store.db() as db:
            last=db.execute("SELECT * FROM jobs WHERE kind='scan' ORDER BY id DESC LIMIT 1").fetchone()
            if last and last['state'] in ACTIVE:raise ValueError('A scan is already queued or running. Check its status.')
            if last and last['state']=='checkpoint_attention':raise ValueError('Checkpoint needs inspection before another paid scan')
            if last and last['state'].startswith('paused') and not data.get('resume'):raise ValueError('Resume the paused batch before starting a new scan')
            if data.get('resume'):
                if not last or not last['state'].startswith('paused'):raise ValueError('There is no paused scan to resume')
                prior=json.loads(last['payload']);request=prior['request'];request['token_budget']=budget;request['batch_size']=batch
            else:
                cfg=store.config();filters=normalize(data.get('filters',{}),cfg)
                request={'job':uuid.uuid4().hex,'limit':limit,'batch_size':batch,'token_budget':budget,'filters':filters,'config':cfg}
            ticket=uuid.uuid4().hex
            payload={'ticket':ticket,'request':request}
            cursor=db.execute("INSERT INTO jobs(kind,state,created,payload) VALUES('scan','dispatching',?,?)",(time.time(),json.dumps(payload)));job_id=cursor.lastrowid
        try:
            github.api('/actions/workflows/'+github.WORKFLOW+'/dispatches',{'ref':'main','inputs':{'ticket':ticket,'request':json.dumps(request)}})
            state='queued'
        except ValueError as error:
            state='dispatch_failed' if str(error).startswith(('GitHub returned 4','GitHub sign-in')) else 'dispatch_unknown'
            with store.db() as db:db.execute('UPDATE jobs SET state=? WHERE id=?',(state,job_id))
            raise
        with store.db() as db:db.execute('UPDATE jobs SET state=? WHERE id=?',(state,job_id))
        return {'id':job_id,'state':state,'request':request}

def status(store):
    with LOCK:
        with store.db() as db:last=db.execute("SELECT * FROM jobs WHERE kind='scan' ORDER BY id DESC LIMIT 1").fetchone()
        if not last:return {'state':'idle'}
        payload=json.loads(last['payload']);result={'id':last['id'],'state':last['state'],**payload}
        if last['state'] not in ACTIVE:return result
        run=payload.get('run')
        if run:run=github.api('/actions/runs/'+str(run['id']))
        else:
            for page in range(1,4):
                runs=github.api(f'/actions/workflows/{github.WORKFLOW}/runs?event=workflow_dispatch&per_page=100&page={page}')['workflow_runs']
                run=next((r for r in runs if r.get('display_title')=='Film Research '+payload['ticket']),None)
                if run or len(runs)<100:break
        if not run:return result
        payload['run']={'id':run['id'],'url':run['html_url']}
        state=run['status']
        if state=='completed':
            artifacts=github.api(f"/actions/runs/{run['id']}/artifacts")['artifacts']
            item=next((a for a in artifacts if a['name']=='film-research-result' and not a['expired']),None)
            if item:
                with github.artifact(item['id']) as stream,zipfile.ZipFile(stream) as archive:
                    report=json.loads(archive.read('status.json'));payload['report']=report
                    if report['job']!=payload['request']['job']:raise ValueError('Scan result identity mismatch')
                    cfg=store.config()
                    with store.db() as db,archive.open('products.jsonl') as products:
                        for line in products:
                            product=json.loads(line);store.put(db,product['base'],product['campaigns'],cfg,product['raw'])
                            db.execute('INSERT OR REPLACE INTO research_scan_results VALUES(?,?,?,?)',(last['id'],product['base']['asin'],int(product['passed']),json.dumps(product['failed_filters'])))
                state=report['phase']
                if run.get('conclusion')!='success':
                    state='checkpoint_attention'
                    payload['error']='Results were received but the workflow failed. Check checkpoint persistence before spending more tokens.'
            else:
                state='paused_workflow_failure';payload['error']='Workflow ended without a result artifact. Open the run for the failing stage. Resume uses the same cohort.'
        with store.db() as db:db.execute('UPDATE jobs SET state=?,payload=?,finished=? WHERE id=?',(state,json.dumps(payload),time.time() if state not in ACTIVE else None,last['id']))
        return {'id':last['id'],'state':state,**payload}
