"""Import auto-scan artifacts into the local Film Research view."""
import json,zipfile,base64,urllib.request
import research_github as github

def scan_counts(store):
    with store.db() as db:
        asins=[row[0] for row in db.execute('SELECT asin FROM early_research_products ORDER BY asin')]
    return {'scanned_asins':asins,'total_scanned':len(asins)}

def sync(store):
    with store.db() as db:
        db.execute('CREATE TABLE IF NOT EXISTS early_research_products(asin TEXT PRIMARY KEY)')
    artifacts=github.api('/actions/artifacts?name=early-research-results&per_page=100')['artifacts']
    items=[a for a in artifacts if not a['expired'] and a.get('workflow_run',{}).get('head_branch')=='main']
    settings=github.api('/contents/data/early-research-settings.json?ref=main')
    enabled=json.loads(base64.b64decode(settings['content'])).get('enabled',False)
    from early_token_budget import current
    allowance=current()
    if not items:return {**allowance,'enabled':enabled,'phase':'Waiting for the first hourly run',**scan_counts(store)}
    item=max(items,key=lambda a:a['id']);key='early-artifact'
    with store.db() as db:previous=db.execute('SELECT value FROM research_local_state WHERE key=?',(key,)).fetchone()
    if not previous or json.loads(previous[0])['artifact']!=item['id']:
        with github.artifact(item['id']) as stream,zipfile.ZipFile(stream) as archive:
            report=json.loads(archive.read('status.json'));report['artifact']=item['id']
            cfg=store.config()
            with store.db() as db,archive.open('products.jsonl') as products:
                for line in products:
                    p=json.loads(line);store.put(db,p['base'],p['campaigns'],cfg,p['raw'])
                    db.execute('INSERT OR IGNORE INTO early_research_products VALUES(?)',(p['base']['asin'],))
                db.execute('INSERT OR REPLACE INTO research_local_state VALUES(?,?)',(key,json.dumps(report)))
    else:report=json.loads(previous[0])
    return {**report,**allowance,'enabled':enabled,**scan_counts(store)}

def toggle(enabled):
    if not isinstance(enabled,bool):raise ValueError('enabled must be true or false')
    path='/contents/data/early-research-settings.json';previous=github.api(path+'?ref=main')
    body={'message':'Set Early Access Research queue','branch':'main','sha':previous['sha'],'content':base64.b64encode(json.dumps({'enabled':enabled}).encode()).decode()}
    req=urllib.request.Request('https://api.github.com/repos/'+github.REPO+path,data=json.dumps(body).encode(),method='PUT',headers={'Authorization':'Bearer '+github.token(),'Content-Type':'application/json','User-Agent':'FilmResearch'})
    with urllib.request.urlopen(req,timeout=30):pass
    return {'enabled':enabled}
