"""Durable pre-request reservations shared by price and Film Research workflows."""
import base64,json,os,time,uuid
import research_github as github
PATH='/contents/data/research-hourly-budget.json'
CAP=1450
class BudgetPause(ValueError):pass

def update(change):
    for attempt in range(5):
        try:remote=github.api(PATH+'?ref=main')
        except ValueError as e:
            if '404' not in str(e):raise
            remote=None
        now=time.time()
        data=json.loads(base64.b64decode(remote['content'])) if remote else {'entries':[], 'safe_after':now+3600}
        data['entries']=[e for e in data['entries'] if e['time']>now-3600]
        result=change(data,now)
        body={'message':'Reserve shared Keepa hourly allowance','branch':'main','content':base64.b64encode(json.dumps(data).encode()).decode()}
        if remote:body['sha']=remote['sha']
        try:
            # Contents writes require PUT, unlike workflow dispatches.
            import urllib.request
            req=urllib.request.Request('https://api.github.com/repos/'+github.REPO+PATH,data=json.dumps(body).encode(),method='PUT',headers={'Authorization':'Bearer '+github.token(),'Content-Type':'application/json','User-Agent':'FilmResearch'})
            with urllib.request.urlopen(req,timeout=30):pass
            return result
        except Exception as error:
            if getattr(error,'code',None)!=409:raise
    raise BudgetPause('Shared budget changed; retry later')

def reserve(cost):
    identity=uuid.uuid4().hex
    def change(data,now):
        if now<data.get('safe_after',0):return False
        if sum(e['cost'] for e in data['entries'])+cost>CAP:return False
        data['entries'].append({'id':identity,'time':now,'cost':cost});return True
    if not update(change):raise BudgetPause('Hourly allowance exhausted or initial tracking warm-up; queue will resume later')
    return identity

def settle(identity,used):
    if not isinstance(used,(int,float)) or used<0:return
    def change(data,now):
        for entry in data['entries']:
            if entry['id']==identity:
                entry['cost']=used;entry['time']=now
                if used>CAP:data['safe_after']=now+3600
    update(change)
