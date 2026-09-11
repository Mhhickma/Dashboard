"""Bounded CC-first GitHub worker. All paid requests use the Actions secret."""
import json
import os
import time
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
from research_keepa import connect,import_sources,evaluate,number,book_asin
from research_model import campaign_active,enrich
from research_funnel import normalize,reasons

class KeepaClient:
    def __init__(self,key,budget,deadline,session=None):
        import requests
        self.session=session or requests.Session();self.key=key;self.budget=budget;self.deadline=deadline
        self.reserved=0;self.consumed=0;self.balance=None;self.unknown=False
    def wait_for_tokens(self,needed):
        import requests
        while self.balance is not None and self.balance<needed:
            if time.monotonic()+75>=self.deadline:return 'paused_tokens'
            time.sleep(10)
            try:
                response=self.session.get('https://api.keepa.com/token',params={'key':self.key},timeout=(10,50))
                payload=response.json()
                balance=payload.get('tokensLeft')
                if response.status_code!=200 or not isinstance(balance,(int,float)):return 'paused_tokens'
                self.balance=balance
            except (requests.RequestException,ValueError,TypeError,AttributeError):return 'paused_tokens'
        return None

    def fetch(self,asins):
        import requests
        for attempt in range(4):
            if self.reserved+len(asins)>self.budget:return None,'paused_budget'
            if time.monotonic()+65>=self.deadline:return None,'paused_time'
            token_error=self.wait_for_tokens(len(asins))
            if token_error:return None,token_error
            self.reserved+=len(asins);wait=2**(attempt+1)
            try:
                response=self.session.get('https://api.keepa.com/product',params={'key':self.key,'domain':1,'asin':','.join(asins),'history':1,'stats':90,'videos':1,'update':-1},timeout=(10,50))
                payload=response.json();used=number(payload.get('tokensConsumed'))
                if used is None:self.unknown=True
                else:self.consumed+=used
                balance=payload.get('tokensLeft')
                if isinstance(balance,(int,float)):self.balance=balance
                if response.status_code==200 and not payload.get('error') and isinstance(payload.get('products'),list):return payload['products'],None
                if response.status_code not in (429,500,502,503,504):return None,'paused_http_'+str(response.status_code)
                wait=max(wait,number(response.headers.get('Retry-After')) or 0,(number(payload.get('refillIn')) or 0)/1000)
            except (requests.RequestException,ValueError,TypeError,AttributeError):self.unknown=True
            if time.monotonic()+wait+65>=self.deadline:return None,'paused_backoff'
            time.sleep(wait)
        return None,'paused_retries'

def campaign_index(db,filters,today):
    latest_index(db)
    db.execute('DROP TABLE IF EXISTS temp.scan_campaigns')
    db.execute('CREATE TEMP TABLE scan_campaigns(id TEXT PRIMARY KEY,source TEXT,payload TEXT)')
    query='SELECT id,source,payload FROM latest_scan_campaigns'
    for cid,source,payload in db.execute(query):
        c=json.loads(payload)
        if filters['cc_only'] and not campaign_active(c,today):continue
        if 'commission_min' in filters and (c.get('commission') is None or c['commission']<=filters['commission_min']):continue
        db.execute('INSERT INTO scan_campaigns VALUES(?,?,?)',(cid,source,payload))
    db.commit()

def latest_index(db):
    db.execute('DROP TABLE IF EXISTS temp.latest_scan_campaigns')
    db.execute('''CREATE TEMP TABLE latest_scan_campaigns AS SELECT id,source,payload FROM (SELECT c.*,ROW_NUMBER() OVER(PARTITION BY c.id ORDER BY s.priority DESC,s.path DESC) n FROM campaigns c JOIN sources s ON c.source=s.path WHERE s.complete=1) WHERE n=1''')
    db.execute('CREATE UNIQUE INDEX latest_scan_id ON latest_scan_campaigns(id)')

def run(db,request,client,deadline,output):
    config=request['config'];f=normalize(request['filters'],config);job=request['job'];limit=request['limit'];batch=request['batch_size']
    db.executescript('''CREATE TABLE IF NOT EXISTS scan_jobs(id TEXT PRIMARY KEY,request TEXT); CREATE TABLE IF NOT EXISTS scan_members(job TEXT,asin TEXT,state TEXT DEFAULT 'pending',PRIMARY KEY(job,asin)); CREATE INDEX IF NOT EXISTS scan_member_state ON scan_members(job,state); CREATE INDEX IF NOT EXISTS scan_member_asin ON scan_members(asin);''')
    existing=db.execute('SELECT request FROM scan_jobs WHERE id=?',(job,)).fetchone()
    identity=json.dumps({'config':config,'filters':f,'limit':limit},sort_keys=True)
    if existing and existing[0]!=identity:raise ValueError('Resume must retain its original funnel and cohort size')
    db.execute('INSERT OR IGNORE INTO scan_jobs VALUES(?,?)',(job,identity));db.commit()
    paths=sorted(Path('data/creator-connections').glob('*.csv'))
    if not paths:raise ValueError('No uploaded CC CSV files found')
    phase='complete'
    if not import_sources(db,paths,deadline):phase='paused_import'
    if phase=='complete':
        campaign_index(db,f,datetime.now(timezone.utc).date().isoformat())
        db.create_function('is_book_asin',1,book_asin)
        if not db.execute('SELECT 1 FROM scan_members WHERE job=?',(job,)).fetchone():
            # A new scan takes the next previously unscanned CC products, never random Amazon ASINs.
            exclude_books='books' in [s.strip().lower() for s in f.get('exclude_categories','').split(',')]
            query='''SELECT DISTINCT l.asin FROM links l JOIN scan_campaigns c ON c.id=l.id AND c.source=l.source WHERE NOT EXISTS(SELECT 1 FROM scan_members m WHERE m.asin=l.asin) AND NOT EXISTS(SELECT 1 FROM cache k WHERE k.asin=l.asin) AND (?=0 OR is_book_asin(l.asin)=0) ORDER BY l.asin LIMIT ?'''
            db.executemany('INSERT INTO scan_members(job,asin) VALUES(?,?)',[(job,r[0]) for r in db.execute(query,(int(exclude_books),limit))]);db.commit()
        while True:
            asins=[r[0] for r in db.execute("SELECT asin FROM scan_members WHERE job=? AND state='pending' ORDER BY asin LIMIT ?",(job,batch))]
            if not asins:break
            products,error=client.fetch(asins)
            if error:
                phase=error
                with db:
                    for asin in asins:db.execute('INSERT INTO failures VALUES(?,?,1,?) ON CONFLICT(asin) DO UPDATE SET code=excluded.code,attempts=attempts+1,last_at=excluded.last_at',(asin,error,time.time()))
                break
            found={p.get('asin'):p for p in products if isinstance(p,dict) and p.get('asin') in asins}
            with db:
                for asin in asins:
                    if asin in found:
                        db.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',(asin,time.time(),json.dumps(found[asin])))
                        db.execute('DELETE FROM failures WHERE asin=?',(asin,))
                        db.execute("UPDATE scan_members SET state='done' WHERE job=? AND asin=?",(job,asin))
                    else:
                        db.execute('INSERT OR REPLACE INTO failures VALUES(?,?,1,?)',(asin,'not_returned',time.time()))
                        db.execute("UPDATE scan_members SET state='failed' WHERE job=? AND asin=?",(job,asin))
    if phase=='paused_import':latest_index(db)
    output.mkdir(parents=True,exist_ok=True);counts=Counter();matches=0;evaluated=0
    with (output/'products.jsonl').open('w',encoding='utf-8') as out:
        for asin,fetched,payload in db.execute('SELECT k.asin,k.fetched,k.payload FROM cache k JOIN scan_members m ON m.asin=k.asin WHERE m.job=?',(job,)):
            # Keep all latest campaigns for an ASIN; the funnel chooses the best live one.
            campaigns=[json.loads(r[0]) for r in db.execute('''SELECT c.payload FROM latest_scan_campaigns c JOIN links l ON l.source=c.source AND l.id=c.id WHERE l.asin=?''',(asin,))]
            latest={c['key']:c for c in campaigns};campaigns=list(latest.values());raw=json.loads(payload)
            base=evaluate(raw,campaigns,time.time(),fetched);row=enrich(base,campaigns,config,raw);failed=reasons(row,f,config)
            counts.update(failed);matches+=not failed;evaluated+=1
            out.write(json.dumps({'base':base,'campaigns':campaigns,'raw':raw,'passed':not failed,'failed_filters':failed})+'\n')
    selected=db.execute('SELECT COUNT(*) FROM scan_members WHERE job=?',(job,)).fetchone()[0]
    failed=[dict(asin=r[0],code=r[1],attempts=r[2]) for r in db.execute('SELECT f.asin,f.code,f.attempts FROM failures f JOIN scan_members m ON m.asin=f.asin WHERE m.job=?',(job,))]
    status=dict(job=job,phase=phase,requested=limit,selected=selected,evaluated=evaluated,matched=matches,rejected=evaluated-matches,rejection_reasons=dict(counts),tokens_reserved=client.reserved,tokens_consumed=None if client.unknown else client.consumed,tokens_left=client.balance,failed=failed,filters=f)
    (output/'status.json').write_text(json.dumps(status),encoding='utf-8');print(json.dumps({k:v for k,v in status.items() if k not in ('filters','failed')}));return status

if __name__=='__main__':
    try:
        request=json.loads(os.environ['SCAN_REQUEST']);deadline=time.monotonic()+900
        if not 1<=int(request['limit'])<=1000 or not 1<=int(request['batch_size'])<=100 or not 1<=int(request['token_budget'])<=1000:raise ValueError('Invalid scan limits')
        key=os.environ.get('KEEPA_API_KEY')
        if not key:raise ValueError('Keepa secret unavailable')
        db=connect(Path('.research-scan/checkpoint.sqlite'))
        try:run(db,request,KeepaClient(key,int(request['token_budget']),deadline),deadline,Path('.research-scan/result'))
        finally:db.close()
    except Exception:
        print('Scan stopped safely. See workflow stage and checkpoint; request details are not logged.')
        raise SystemExit(1)
