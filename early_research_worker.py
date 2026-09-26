"""Scan upcoming CC products only with the remaining shared hourly allowance."""
import csv,json,os,re,time,uuid
from pathlib import Path
from datetime import datetime
from cc_batches import active_csv_files
from research_keepa import connect,evaluate
from research_scan import run,KeepaClient
from research_hourly import reserve,BudgetPause
from research_model import enrich

def main():
    cfg=json.loads(Path('data/early-research-settings.json').read_text())
    if not cfg.get('enabled'):print('Early Access Research paused');return
    from research_github import restore
    restore()
    db=connect(Path('.research-scan/checkpoint.sqlite'))
    db.execute('CREATE TABLE IF NOT EXISTS early_research_asins(asin TEXT PRIMARY KEY)')
    today=datetime.now().date().isoformat();asins=set()
    for path in active_csv_files('data/creator-connections'):
        with path.open(encoding='utf-8-sig',newline='') as stream:
            for row in csv.DictReader(stream):
                if row.get('Campaign Start Date','')>today:
                    asins.update(re.findall(r'\b[A-Z0-9]{10}\b',row.get('ASIN List','').upper()))
    db.executemany('INSERT OR IGNORE INTO early_research_asins VALUES(?)',((a,) for a in sorted(asins)));db.commit()
    cached={row[0] for row in db.execute('SELECT asin FROM cache')}
    exclusions_path=Path('data/early-research-category-exclusions.json')
    if not exclusions_path.exists():raise ValueError('Category exclusion list is missing; no paid early scans allowed')
    excluded=set(json.loads(exclusions_path.read_text(encoding='utf-8'))['asins'])
    pending=sorted(asins-cached-excluded)
    config=json.loads(Path('research-config.json').read_text())
    from early_token_budget import current
    allowance=current()
    pending=pending[:allowance['early_token_budget']]
    deadline=time.monotonic()+600;report={'phase':'paused_average_budget' if not pending else 'complete'}
    try:
        for offset in range(0,min(len(pending),1450),1000):
            cohort=pending[offset:offset+1000]
            request={'job':'early-'+uuid.uuid4().hex,'asins':cohort,'limit':len(cohort),'batch_size':10,'token_budget':len(cohort),'filters':{'cc_only':False},'config':config}
            report=run(db,request,KeepaClient(os.environ['KEEPA_API_KEY'],len(cohort),deadline),deadline,Path('.research-scan/early-run'))
            if report['phase']!='complete':break
    finally:
        output=Path('.research-scan/early-results');output.mkdir(exist_ok=True)
        with (output/'products.jsonl').open('w',encoding='utf-8') as out:
            for asin,fetched,payload in db.execute('SELECT k.asin,k.fetched,k.payload FROM cache k JOIN early_research_asins e ON k.asin=e.asin'):
                campaigns=[json.loads(row[0]) for row in db.execute('SELECT c.payload FROM campaigns c JOIN links l ON l.id=c.id AND l.source=c.source WHERE l.asin=?',(asin,))]
                raw=json.loads(payload);base=evaluate(raw,campaigns,time.time(),fetched)
                out.write(json.dumps({'base':base,'campaigns':campaigns,'raw':raw})+'\n')
        (output/'status.json').write_text(json.dumps({**allowance,'updated':time.time(),'upcoming_asins':len(asins),'remaining':len(asins-excluded-{r[0] for r in db.execute('SELECT asin FROM cache')}),'category_skipped':len(asins & excluded),'phase':report.get('phase','complete')}))
        db.close()
if __name__=='__main__':main()
