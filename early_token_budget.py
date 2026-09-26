"""Price-only completed-hour average for the automatic research allowance."""
import base64,json,math,time
from datetime import datetime
import research_github as github
WINDOW_HOURS=24

def calculate(usage,now=None):
    now=time.time() if now is None else now
    result={'average_tokens_per_hour':None,'early_token_budget':0,'average_hours':0}
    try:
        stamp=lambda value:datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
        updated=stamp(usage['updated_at']);started=stamp(usage['tracking_started_at'])
        end=math.floor(now/3600)*3600
        start=max(end-WINDOW_HOURS*3600,math.ceil(started/3600)*3600)
        hours=int((end-start)/3600)
        if hours<1 or now-updated>7200 or updated<end:return result
        entries=[e for e in usage['entries'] if start<=stamp(e['timestamp'])<end]
        if any(e.get('unreported_responses',0) for e in entries):return result
        average=sum(max(0,float(e['tokens'])) for e in entries)/hours
        return {'average_tokens_per_hour':round(average,2),'early_token_budget':max(0,math.floor((1500-average)/2)),'average_hours':hours}
    except (KeyError,ValueError,TypeError):return result

def current():
    response=github.api('/contents/data/keepa_token_usage.json?ref=main')
    return calculate(json.loads(base64.b64decode(response['content'])))
