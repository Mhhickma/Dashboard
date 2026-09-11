"""Local research workspace. Serves only explicit assets; never calls Keepa."""
import argparse
import csv
import io
import json
import logging
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from research_model import enrich, STAGES

ROOT=Path(__file__).resolve().parent
ASSETS={'/':'research.html','/research.html':'research.html','/research.js':'research.js','/research.css':'research.css'}
FIELDS=['asin','title','brand','category','price','monthly_sold','bsr','bsr30','bsr90','influencer_videos','merchant_video','cc_active','commission','estimated_commission_per_sale','film_score','score_coverage','video_count_source','video_count_last_checked']

class Store:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY,applied REAL);
            CREATE TABLE IF NOT EXISTS products(asin TEXT PRIMARY KEY,title TEXT,brand TEXT,category TEXT,price REAL,monthly_sold REAL,commission REAL,cc_active INTEGER,apparel INTEGER,influencer_videos INTEGER,merchant_video INTEGER,rating REAL,review_count INTEGER,variant_count INTEGER,seller_count INTEGER,growth REAL,bsr90 REAL,campaign_end TEXT,film_score REAL,payload TEXT,base TEXT,raw TEXT);
            CREATE INDEX IF NOT EXISTS products_score ON products(film_score DESC,asin);
            CREATE INDEX IF NOT EXISTS products_cc ON products(cc_active,commission);
            CREATE INDEX IF NOT EXISTS products_category ON products(category);
            CREATE TABLE IF NOT EXISTS product_campaigns(asin TEXT,id TEXT,payload TEXT,PRIMARY KEY(asin,id));
            CREATE INDEX IF NOT EXISTS product_campaigns_asin ON product_campaigns(asin);
            CREATE TABLE IF NOT EXISTS shortlist(asin TEXT PRIMARY KEY,payload TEXT,added REAL,updated REAL);
            CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT);
            CREATE TABLE IF NOT EXISTS target_brands(brand TEXT PRIMARY KEY,enabled INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,asin TEXT,kind TEXT,payload TEXT,created REAL,delivered INTEGER DEFAULT 0);
            CREATE INDEX IF NOT EXISTS events_pending ON events(delivered,created);
            CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY,kind TEXT,state TEXT,created REAL,finished REAL,payload TEXT);
            CREATE TABLE IF NOT EXISTS research_scan_results(job INTEGER,asin TEXT,passed INTEGER,reasons TEXT,PRIMARY KEY(job,asin));
            CREATE INDEX IF NOT EXISTS research_scan_matches ON research_scan_results(job,passed);
            INSERT OR IGNORE INTO schema_migrations VALUES(2,strftime('%s','now'));
            INSERT OR IGNORE INTO schema_migrations VALUES(1,strftime('%s','now'));
            ''')
            db.execute('INSERT OR IGNORE INTO settings VALUES(1,?)',( (ROOT/'research-config.json').read_text(encoding='utf-8'),))
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=30);db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()
    def config(self):
        with self.db() as db:return json.loads(db.execute('SELECT payload FROM settings WHERE id=1').fetchone()[0])
    def put(self,db,base,campaigns,cfg,raw=None):
        r=enrich(base,campaigns,cfg,raw)
        columns=['asin','title','brand','category','price','monthly_sold','commission','cc_active','apparel','influencer_videos','merchant_video','rating','review_count','variant_count','seller_count','growth','bsr90','campaign_end','film_score']
        db.execute('INSERT OR REPLACE INTO products('+','.join(columns)+',payload,base,raw) VALUES('+','.join('?' for _ in range(len(columns)+3))+')', [r.get(k) for k in columns]+[json.dumps(r),json.dumps(base),json.dumps(raw) if raw else None])
        db.execute('DELETE FROM product_campaigns WHERE asin=?',(r['asin'],))
        for i,c in enumerate(campaigns):db.execute('INSERT OR REPLACE INTO product_campaigns VALUES(?,?,?)',(r['asin'],c.get('campaign_id') or str(i),json.dumps(c)))
    def import_saved(self,folder):
        cfg=self.config();count=0
        with self.db() as db:
            for page in sorted(Path(folder).glob('page-*.json')):
                for row in json.loads(page.read_text(encoding='utf-8')):
                    detail=Path(folder)/'details'/f"{row['asin']}.json"
                    campaigns=json.loads(detail.read_text(encoding='utf-8')).get('campaigns',[]) if detail.exists() else []
                    existing=db.execute('SELECT base,raw FROM products WHERE asin=?',(row['asin'],)).fetchone()
                    if existing and existing['raw']:
                        campaigns=[json.loads(c[0]) for c in db.execute('SELECT payload FROM product_campaigns WHERE asin=?',(row['asin'],))]
                        self.put(db,json.loads(existing['base']),campaigns,cfg,json.loads(existing['raw']))
                    else:self.put(db,row,campaigns,cfg)
                    count+=1
        return count
    def import_checkpoint(self,path):
        # Source is read-only; source campaign records and product caches stay intact.
        from research_keepa import evaluate
        cfg=self.config();source=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True);count=0
        try:
            source.execute('''CREATE TEMP TABLE latest AS SELECT id,source,payload FROM (
                SELECT c.*,ROW_NUMBER() OVER(PARTITION BY c.id ORDER BY s.priority DESC,s.path DESC) AS n
                FROM campaigns c JOIN sources s ON c.source=s.path WHERE s.complete=1) WHERE n=1''')
            source.execute('CREATE INDEX latest_id ON latest(id)')
            with self.db() as db:
                for asin,fetched,payload in source.execute('SELECT asin,fetched,payload FROM cache'):
                    campaigns=[json.loads(c[0]) for c in source.execute('SELECT DISTINCT c.payload FROM latest c JOIN links l ON l.id=c.id WHERE l.asin=?',(asin,))]
                    raw=json.loads(payload);base=evaluate(raw,campaigns,time.time(),fetched)
                    self.put(db,base,campaigns,cfg,raw);count+=1
        finally:source.close()
        return count
    def save_settings(self,cfg):
        default=json.loads((ROOT/'research-config.json').read_text())
        if set(cfg)!=set(default) or set(cfg['weights'])!=set(default['weights']) or set(cfg['thresholds'])!=set(default['thresholds']):raise ValueError('Keep all configuration keys')
        numbers=list(cfg['weights'].values())+list(cfg['thresholds'].values())
        if any(type(v) not in (int,float) or not 0<=v<=1000000 for v in numbers) or abs(sum(cfg['weights'].values())-100)>.001:raise ValueError('Weights must total 100; thresholds must be nonnegative numbers')
        for key in ['monthly_sales_full','growth_full','commission_full','commission_per_sale_full','accelerating_growth']:
            if cfg['thresholds'][key]<=0:raise ValueError('Full-score thresholds must be positive')
        if cfg['thresholds']['secondary_videos_max']<cfg['thresholds']['primary_videos_max']:raise ValueError('Secondary video maximum must be at least primary maximum')
        if not isinstance(cfg['target_brands'],list) or any(not isinstance(b,str) or len(b)>150 for b in cfg['target_brands']):raise ValueError('Invalid target brands')
        if cfg['refresh']['automatic'] or cfg['refresh']['paid_video_refresh']!='explicit_selection_only':raise ValueError('Automatic paid refresh is not supported')
        if not isinstance(cfg['filters'].get('exclude_categories'),list) or any(not isinstance(v,str) for v in cfg['filters']['exclude_categories']):raise ValueError('Invalid category exclusions')
        with self.db() as db:
            records=db.execute('SELECT base,raw FROM products').fetchall()
            db.execute('UPDATE settings SET payload=? WHERE id=1',(json.dumps(cfg),))
            for record in records:
                base=json.loads(record['base']);campaigns=[json.loads(c[0]) for c in db.execute('SELECT payload FROM product_campaigns WHERE asin=?',(base['asin'],))]
                self.put(db,base,campaigns,cfg,json.loads(record['raw']) if record['raw'] else None)
            db.execute('DELETE FROM target_brands')
            db.executemany('INSERT INTO target_brands VALUES(?,1)',[(b,) for b in set(cfg['target_brands'])])
    def query(self,q,export=False):
        cfg=self.config(); defaults=cfg['filters']; where=[];values=[]
        def add(sql,v=None):
            where.append(sql)
            if v is not None:values.append(v)
        view=q.get('view','feed')
        if q.get('scan_job'):
            add('p.asin IN (SELECT asin FROM research_scan_results WHERE job=? AND passed=1)',int(q['scan_job']))
        workflow=view in ('shortlist','outreach','film','published')
        if workflow:
            add('p.asin IN (SELECT asin FROM shortlist)')
            if view=='published':add("p.asin IN (SELECT asin FROM shortlist WHERE json_extract(payload,'$.status')='Published')")
            if view=='film':add("p.asin IN (SELECT asin FROM shortlist WHERE json_extract(payload,'$.status') IN ('Sample Approved','Purchased','Received','Ready to Film','Filmed','Needs Editing','Ready to Upload','Uploaded to Amazon'))")
            if view=='outreach':add("p.asin IN (SELECT asin FROM shortlist WHERE json_extract(payload,'$.sample_requested')=1 OR json_extract(payload,'$.brand_contacted')=1)")
        else:
            if q.get('cc_only',str(defaults['cc_only']).lower())=='true' or view=='cc':add('p.cc_active=1')
            floor=q.get('commission_min',defaults['commission_min'])
            if floor not in ('',None):add('p.commission>?',float(floor))
            if q.get('exclude_apparel',str(defaults['exclude_apparel']).lower())=='true':add('p.apparel=0')
            exclusions=q.get('exclude_categories',','.join(defaults['exclude_categories']))
            for cat in str(exclusions).split(','):
                if cat.strip():add("lower(p.category) NOT LIKE ?",'%'+cat.strip().lower()+'%')
        if q.get('q'):add("(p.asin LIKE ? OR p.title LIKE ? OR p.brand LIKE ?)",'%'+q['q']+'%');values.extend(['%'+q['q']+'%']*2)
        if q.get('category'):add('p.category=?',q['category'])
        ranges={'price_min':('price','>='),'price_max':('price','<='),'sales_min':('monthly_sold','>='),'influencer_max':('influencer_videos','<='),'rating_min':('rating','>='),'reviews_min':('review_count','>='),'variants_max':('variant_count','<='),'sellers_max':('seller_count','<='),'commission_max':('commission','<='),'score_min':('film_score','>='),'bsr_min':('bsr90','>=')}
        for key,(column,operator) in ranges.items():
            v=q.get(key,defaults.get(key))
            if v not in ('',None):add(f'p.{column}{operator}?',float(v))
        if q.get('merchant_required',str(defaults['merchant_required']).lower())=='true':add('p.merchant_video=1')
        if q.get('main_required')=='true':add("json_extract(p.payload,'$.main_video')=1")
        if q.get('growth_min') not in ('',None):add('p.growth>=?',float(q['growth_min']))
        if q.get('total_videos_max') not in ('',None):add("json_extract(p.payload,'$.total_videos')<=?",float(q['total_videos_max']))
        if view=='low':add('p.influencer_videos<=?',cfg['thresholds']['primary_videos_max'])
        trend=q.get('trend','rising' if view=='trending' else '')
        band=cfg['thresholds']['stable_band']
        if trend=='rising':add('p.growth>?',band)
        if trend=='flat':add('ABS(p.growth)<=?',band)
        if trend=='falling':add('p.growth<?',-band)
        bsr_trend=q.get('bsr_trend')
        if bsr_trend=='improving':add('p.bsr90>0')
        if bsr_trend=='worsening':add('p.bsr90<0')
        if q.get('expires_before'):add('p.campaign_end<=?',q['expires_before'])
        if q.get('expires_after'):add('p.campaign_end>=?',q['expires_after'])
        clause=' AND '.join(where) or '1=1'
        allowed={'film_score','price','monthly_sold','commission','growth','bsr90','influencer_videos','title','asin','fetched_at'}
        sort=q.get('sort','film_score');sort=sort if sort in allowed else 'film_score'
        sort_expression="CASE WHEN json_extract(p.payload,'$.fetched_at')>0 THEN CAST(json_extract(p.payload,'$.fetched_at') AS REAL) END" if sort=='fetched_at' else f'p.{sort}'
        direction='ASC' if q.get('direction')=='asc' else 'DESC'
        page=max(1,int(q.get('page',1)));size=min(100,max(1,int(q.get('size',50))))
        sql=f'SELECT p.payload,s.payload AS shortlist FROM products p LEFT JOIN shortlist s ON s.asin=p.asin WHERE {clause} ORDER BY {sort_expression} IS NULL,{sort_expression} {direction},p.asin'
        with self.db() as db:
            total=db.execute(f'SELECT COUNT(*) FROM products p WHERE {clause}',values).fetchone()[0]
            if not export:sql+=' LIMIT ? OFFSET ?';values += [size,(page-1)*size]
            rows=[]
            for item in db.execute(sql,values):
                row=json.loads(item['payload']);row.pop('history',None);row.pop('campaigns',None);row['shortlist']=json.loads(item['shortlist']) if item['shortlist'] else None;rows.append(row)
            categories=[r[0] for r in db.execute('SELECT DISTINCT category FROM products WHERE category IS NOT NULL ORDER BY category')]
        return dict(rows=rows,total=total,page=page,size=size,categories=categories)
    def detail(self,asin):
        with self.db() as db:
            r=db.execute('SELECT payload FROM products WHERE asin=?',(asin,)).fetchone()
            if not r:raise KeyError('Product not found')
            result=json.loads(r[0]);saved=db.execute('SELECT payload,added,updated FROM shortlist WHERE asin=?',(asin,)).fetchone()
            result['shortlist']=dict(json.loads(saved[0]),date_added=saved[1],last_updated=saved[2]) if saved else None
            return result
    def save_shortlist(self,asin,data):
        self.detail(asin)
        allowed={'notes','priority','status','purchase_price','sample_requested','brand_contacted','product_ordered','contact_date','contact_method','response_status','followup_date','date_acquired','date_filmed','date_uploaded','video_url'}
        if set(data)-allowed or data.get('status') not in STAGES:raise ValueError('Invalid shortlist fields/status')
        if len(data.get('notes',''))>10000:raise ValueError('Notes exceed 10000 characters')
        if data.get('priority') not in ('Low','Normal','High'):raise ValueError('Invalid priority')
        if data.get('purchase_price') not in ('',None) and (type(data['purchase_price']) not in (float,int) or not 0<=data['purchase_price']<=1000000):raise ValueError('Invalid cost')
        if data.get('video_url') and not data['video_url'].startswith('https://'):raise ValueError('Video URL must use HTTPS')
        with self.db() as db:
            now=time.time();db.execute('INSERT INTO shortlist VALUES(?,?,?,?) ON CONFLICT(asin) DO UPDATE SET payload=excluded.payload,updated=excluded.updated',(asin,json.dumps(data),now,now))
            db.execute('INSERT INTO events(asin,kind,payload,created) VALUES(?,?,?,?)',(asin,'shortlist_updated',json.dumps({'status':data['status']}),now))

def handler(store):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def guard(self):
            hosts={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
            if self.headers.get('Host') not in hosts:raise PermissionError('Local access only')
            origin=self.headers.get('Origin')
            if origin and origin not in {'http://'+h for h in hosts}:raise PermissionError('Cross-origin access denied')
            if self.headers.get('Sec-Fetch-Site')=='cross-site' and not (self.command=='GET' and urlparse(self.path).path in ASSETS and self.headers.get('Sec-Fetch-Mode')=='navigate'):raise PermissionError('Cross-site access denied')
        def send(self,data,kind='application/json',status=200):
            body=json.dumps(data,allow_nan=False).encode() if kind=='application/json' else data
            self.send_response(status);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' https://m.media-amazon.com; style-src 'self'; script-src 'self'; frame-ancestors 'none'; connect-src 'self'");self.end_headers();self.wfile.write(body)
        def do_GET(self):
            try:
                self.guard();url=urlparse(self.path);q={k:v[0] for k,v in parse_qs(url.query,keep_blank_values=True).items()}
                if url.path in ASSETS:
                    name=ASSETS[url.path];return self.send((ROOT/name).read_bytes(), 'text/html' if name.endswith('.html') else 'text/css' if name.endswith('.css') else 'text/javascript')
                if url.path=='/api/settings':return self.send({'config':store.config(),'csrf':self.server.csrf,'stages':STAGES})
                if url.path=='/api/scan':
                    from research_jobs import status
                    return self.send(status(store))
                if url.path=='/api/products':return self.send(store.query(q))
                if url.path.startswith('/api/products/'):return self.send(store.detail(url.path.rsplit('/',1)[-1]))
                if url.path=='/api/export':
                    out=io.StringIO();w=csv.writer(out);w.writerow(FIELDS)
                    for r in store.query(q,export=True)['rows']:
                        values=[r.get(k) if r.get(k) is not None else 'Unknown' for k in FIELDS]
                        w.writerow(["'"+str(v) if str(v).startswith(('=','+','-','@','\t','\r')) else v for v in values])
                    return self.send(out.getvalue().encode(),'text/csv')
                self.send({'error':'Not found'},status=404)
            except PermissionError as e:self.send({'error':str(e)},status=403)
            except KeyError as e:self.send({'error':str(e)},status=404)
            except (ValueError,TypeError) as e:self.send({'error':str(e)},status=400)
            except Exception:logging.exception('Research read failed');self.send({'error':'Research read failed; see local log'},status=500)
        def do_POST(self):
            try:
                self.guard()
                if not secrets.compare_digest(self.headers.get('X-Research-CSRF',''),self.server.csrf):raise PermissionError('Reload the page before saving')
                size=int(self.headers.get('Content-Length',0))
                if not 0<size<=100000:raise ValueError('Invalid request size')
                data=json.loads(self.rfile.read(size))
                if self.path=='/api/scan':
                    from research_jobs import start
                    return self.send(start(store,data))
                if self.path=='/api/settings':store.save_settings(data)
                elif self.path.startswith('/api/shortlist/'):store.save_shortlist(self.path.rsplit('/',1)[-1],data)
                else:raise ValueError('Unknown action')
                self.send({'ok':True})
            except PermissionError as e:self.send({'error':str(e)},status=403)
            except (ValueError,KeyError,TypeError) as e:self.send({'error':str(e)},status=400)
            except Exception:logging.exception('Research save failed');self.send({'error':'Save failed; see local log'},status=500)
    return Handler

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);parser.add_argument('--db',default=str(ROOT/'.research/research.sqlite'));parser.add_argument('--checkpoint');parser.add_argument('--import-only',action='store_true');args=parser.parse_args()
    store=Store(args.db)
    if args.checkpoint:count=store.import_checkpoint(args.checkpoint)
    else:count=store.import_saved(ROOT/'data/influencer')
    print(f'Loaded {count} saved products. No Keepa requests.',flush=True)
    if args.import_only:return
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler(store));server.csrf=secrets.token_urlsafe(32)
    print(f'Research workspace: http://127.0.0.1:{args.port}',flush=True)
    server.serve_forever()

if __name__=='__main__':main()
