"""Persist full deal uploads and query their original columns without browser-sized downloads."""
import csv, io, json, sqlite3, os, uuid, hashlib, threading, time
from urllib.request import urlopen
from urllib.parse import quote
from datetime import datetime, timezone
from contextlib import closing
from cc_batches import active_csv_files
from early_cc import load_accepted
from prime_match import match
LOCK=threading.RLock()

def ingest(root,text):
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    headers=reader.fieldnames
    if not {'asin','promotionPrice','lowestPriceYtd'}.issubset(headers or []):raise ValueError('CSV must include asin, promotionPrice and lowestPriceYtd.')
    folder=root/'.research';folder.mkdir(exist_ok=True)
    temp=folder/('sales-'+uuid.uuid4().hex+'.sqlite')
    try:
        with closing(sqlite3.connect(temp)) as db:
            db.execute('CREATE TABLE metadata (headers TEXT, uploaded TEXT)')
            db.execute('INSERT INTO metadata VALUES (?,?)',(json.dumps(headers),datetime.now(timezone.utc).isoformat()))
            columns=','.join('c'+str(i)+' TEXT' for i in range(len(headers)))
            db.execute('CREATE TABLE deals ('+columns+')')
            sql='INSERT INTO deals VALUES ('+','.join('?' for _ in headers)+')'
            db.executemany(sql,([row.get(h,'') or '' for h in headers] for row in reader))
            db.commit()
        with LOCK:os.replace(temp,folder/'sales-catalog.sqlite')
    finally:temp.unlink(missing_ok=True)

def sync_cc(root):
    folder=root/'.research/current-sales-cc';folder.mkdir(exist_ok=True)
    checked=folder/'checked.json'
    if checked.exists() and time.time()-checked.stat().st_mtime<60:return folder
    base='https://raw.githubusercontent.com/Mhhickma/Dashboard/main/data/creator-connections/'
    with urlopen('https://api.github.com/repos/Mhhickma/Dashboard/git/trees/main?recursive=1',timeout=60) as response:tree=json.load(response)
    if tree.get('truncated'):raise ValueError('CC list listing is incomplete; retry later.')
    names=sorted(item['path'].split('/')[-1] for item in tree['tree'] if item['path'].startswith('data/creator-connections/') and item['path'].endswith('-replacement-complete.csv'))
    if not names:return root/'data/creator-connections'
    marker=names[-1]
    if not (folder/marker).exists():
        with urlopen(base+quote(marker),timeout=60) as response:manifest=response.read()
        rows=list(csv.DictReader(io.StringIO(manifest.decode('utf-8-sig'))))
        for row in rows:
            name=row['Batch file']
            if '/' in name or '\\' in name or not name.startswith(marker.removesuffix('complete.csv')):raise ValueError('Invalid CC manifest')
            if not (folder/name).exists() and (root/'data/creator-connections'/name).exists():
                import shutil
                shutil.copyfile(root/'data/creator-connections'/name,folder/name)
            if not (folder/name).exists():
                with urlopen(base+quote(name),timeout=60) as response:content=response.read()
                temp=folder/(name+'.tmp');temp.write_bytes(content);temp.replace(folder/name)
        (folder/marker).write_bytes(manifest)
    active_csv_files(folder)
    checked.write_text('{}')
    return folder

def current(root, refresh_cc=True):
    with LOCK:
        path=root/'.research/sales-catalog.sqlite'
        if not path.exists():return None
        cc_folder=sync_cc(root) if refresh_cc else root/'data/creator-connections'
        files=active_csv_files(cc_folder)
        fingerprint=str(path.stat().st_mtime_ns)+''.join(str(p)+str(p.stat().st_mtime_ns) for p in files)
        accepted_path=root/'.research/accepted-cc.json'
        if accepted_path.exists():fingerprint+=str(accepted_path.stat().st_mtime_ns)
        cache=root/'.research/sales-current.json';key=hashlib.sha256(fingerprint.encode()).hexdigest()
        if cache.exists():
            saved=json.loads(cache.read_text(encoding='utf-8'))
            if saved.get('source_key')==key:return saved
        with closing(sqlite3.connect(path)) as db:
            header,uploaded=db.execute('SELECT * FROM metadata').fetchone();headers=json.loads(header)
            out=io.StringIO();writer=csv.writer(out);writer.writerow(headers);writer.writerows(db.execute('SELECT * FROM deals'))
        result=match(out.getvalue(),cc_folder)
        accepted=load_accepted(accepted_path);before=result['campaign_ids']
        result['campaign_ids']=[cid for cid in before if cid not in accepted]
        result['accepted_excluded']=len(before)-len(result['campaign_ids'])
        result['batch_key']=hashlib.sha256('\n'.join(result['campaign_ids']).encode()).hexdigest()
        result['saved_at']=uploaded;result['source_key']=key
        cache.write_text(json.dumps(result),encoding='utf-8')
        return result

def query(root,q):
    with LOCK:
        path=root/'.research/sales-catalog.sqlite'
        if not path.exists():return {'headers':[],'rows':[],'total':0,'categories':[]}
        with closing(sqlite3.connect(path)) as db:
            headers=json.loads(db.execute('SELECT headers FROM metadata').fetchone()[0])
            sort=q.get('sort','asin');idx=headers.index(sort) if sort in headers else 0
            col='c'+str(idx);direction='DESC' if q.get('direction')=='desc' else 'ASC'
            numeric={'promotionPrice','listingPrice','lowestPriceYtd','lowestt30dPrice','discountPct','asinRating'}
            order=('CAST('+col+' AS REAL)') if headers[idx] in numeric else col+' COLLATE NOCASE'
            cat='c'+str(headers.index('productCategory')) if 'productCategory' in headers else None
            categories=[r[0] for r in db.execute('SELECT DISTINCT '+cat+' FROM deals ORDER BY 1')] if cat else []
            excluded=json.loads(q.get('exclude','[]'));excluded=[str(v) for v in excluded]
            where=(' WHERE '+cat+' NOT IN ('+','.join('?' for _ in excluded)+')') if cat and excluded else ''
            args=excluded if where else []
            total=db.execute('SELECT COUNT(*) FROM deals'+where,args).fetchone()[0]
            offset=max(0,int(q.get('offset',0)))
            rows=db.execute('SELECT * FROM deals'+where+' ORDER BY '+order+' '+direction+' LIMIT 100 OFFSET ?',args+[offset]).fetchall()
            return {'headers':headers,'rows':rows,'total':total,'categories':categories}

