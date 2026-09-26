"""Category exclusions apply only to paid early-access scans, never opt-in batches."""
import json,re,sqlite3,base64,urllib.request
from pathlib import Path
from contextlib import closing
EXCLUDED=['Books','Kindle Store','Audible Books & Originals','Digital Music','Apps & Games','Software','Gift Cards','Digital Codes','Amazon Services','Clothing, Shoes & Jewelry']
def norm(value):return re.sub(r'[^a-z0-9]','',str(value).lower())
ALIASES={norm(v) for v in EXCLUDED}|{'apparel','designerapparel','shoes','jewelry','watches','clothing','digitalebookpurchase','digitalsoftware','consumablesphysicalgiftcards','consumablesemailgiftcards','audible','ebooks','digitalcodes'}
def excluded(value):
 return any(norm(part) in ALIASES for part in str(value or '').split('>'))
def build(root):
 root=Path(root);asins=set();dbpath=root/'.research/sales-catalog.sqlite'
 if dbpath.exists():
  with closing(sqlite3.connect(dbpath)) as db:
   headers=json.loads(db.execute('SELECT headers FROM metadata').fetchone()[0])
   names=[name for name in ('productCategory','gl') if name in headers]
   if 'asin' in headers and names:
    columns=['c'+str(headers.index(name)) for name in ['asin']+names]
    for row in db.execute('SELECT '+','.join(columns)+' FROM deals'):
     if any(excluded(value) for value in row[1:]):asins.add(row[0].strip().upper())
 payload={'categories':EXCLUDED,'asins':sorted(asins)}
 target=root/'data/early-research-category-exclusions.json';target.parent.mkdir(exist_ok=True);target.write_text(json.dumps(payload),encoding='utf-8');return payload

def publish(root):
 import research_github as github
 payload=build(root);path='/contents/data/early-research-category-exclusions.json'
 previous=github.api(path+'?ref=main')
 body={'message':'Update early-access scan category exclusions','branch':'main','sha':previous['sha'],'content':base64.b64encode(json.dumps(payload).encode()).decode()}
 req=urllib.request.Request('https://api.github.com/repos/'+github.REPO+path,data=json.dumps(body).encode(),method='PUT',headers={'Authorization':'Bearer '+github.token(),'Content-Type':'application/json','User-Agent':'FilmResearch'})
 with urllib.request.urlopen(req,timeout=60):pass
