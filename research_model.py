"""Research normalization and configurable scoring. No network access."""
import json
import math
import re
import time
from datetime import datetime, timezone
from typing import Protocol
from decimal import Decimal, ROUND_HALF_UP

EPOCH = 1293840000
STAGES = ['Researching','Want Sample','Brand Contacted','Sample Approved','Purchased','Received','Ready to Film','Filmed','Needs Editing','Ready to Upload','Uploaded to Amazon','Published','Rejected / Skip']

class VideoProvider(Protocol):
    def normalize(self, product: dict) -> dict: ...

def numeric(v):
    return v if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v >= 0 else None

def timestamp(v):
    return EPOCH + v*60 if numeric(v) is not None and v > 0 else None

class KeepaVideos:
    def normalize(self,p):
        videos=p.get('videos'); valid=isinstance(videos,list)
        unique={v['url']:v for v in videos or [] if isinstance(v,dict) and isinstance(v.get('url'),str)} if valid else {}
        complete=valid and len(unique)==len({v.get('url') for v in videos if isinstance(v,dict)}) and all(isinstance(v,dict) and v.get('url') for v in videos)
        typed=complete and all(v.get('creator') in {'Main','Customer','Seller','Influencer','Vendor','ThirdParty','Amazon','Merchant','Brand'} for v in unique.values())
        merchant=sum(v.get('creator') in {'Seller','Vendor','Merchant','Brand'} for v in unique.values())
        main=any(v.get('creator')=='Main' for v in unique.values())
        # Main is unclassified carousel content: it cannot prove no merchant/creator videos.
        exact_types=typed and not main
        history=(p.get('csv') or [])
        updates=history[15] if len(history)>15 else None
        checked=timestamp(updates[-2]) if isinstance(updates,list) and len(updates)>=2 else None
        return dict(total_videos=len(unique) if complete else None,
            merchant_video=True if merchant else False if exact_types else None,
            merchant_video_count=merchant if exact_types or merchant else None,
            influencer_videos=sum(v.get('creator')=='Influencer' for v in unique.values()) if exact_types else None,
            main_video=True if main else None,video_count_source='Keepa observed video metadata' if complete else 'Unknown',
            video_count_confidence='observed, not exhaustive' if complete else 'Unknown',video_count_last_checked=checked)

def trend_label(growth, cfg):
    if growth is None: return 'Unknown'
    band=cfg['stable_band']; fast=cfg['accelerating_growth']
    return 'Accelerating' if growth>=fast else 'Rising' if growth>band else 'Rapidly declining' if growth<=-fast else 'Declining' if growth < -band else 'Stable'

def score(row,cfg):
    t=cfg['thresholds']; w=cfg['weights']
    def ratio(value,full): return None if value is None else min(1,max(0,value/full))
    v=row.get('influencer_videos')
    competition=None if v is None else 1 if v<=t['primary_videos_max'] else .5 if v<=t['secondary_videos_max'] else 0
    values={'sales_volume':ratio(row.get('monthly_sold'),t['monthly_sales_full']),
        'sales_trend':ratio(row.get('growth'),t['growth_full']),'competition':competition,
        'commission':ratio(row.get('commission') if row.get('cc_active') else None,t['commission_full']),
        'merchant_video':None if row.get('merchant_video') is None else int(row['merchant_video']),
        'earning_potential':ratio(row.get('estimated_commission_per_sale'),t['commission_per_sale_full'])}
    components={k: {'points':None if values[k] is None else round(values[k]*w[k],2),'maximum':w[k]} for k in w}
    return round(sum(c['points'] or 0 for c in components.values()),2),components,round(sum(w[k] for k,v in values.items() if v is not None),2)

def campaign_active(c,today):
    return bool(c.get('start') and c.get('end') and c['start']<=today<=c['end'] and str(c.get('status','')).lower() not in {'inactive','paused','cancelled','canceled','ended','expired','closed','upcoming'})

def enrich(row,campaigns,cfg,raw=None):
    r=dict(row); today=datetime.now(timezone.utc).date().isoformat()
    live=[c for c in campaigns if campaign_active(c,today)]
    best=max(live or campaigns,key=lambda c:c.get('commission') or 0,default={})
    r.update(cc_active=bool(live),commission=best.get('commission'),campaign_end=best.get('end'),campaign_id=best.get('campaign_id'),campaign_status=best.get('status') or ('Active' if live else 'Inactive' if campaigns else 'Unknown'),campaigns=campaigns)
    r['estimated_commission_per_sale']=float((Decimal(str(r['price']))*Decimal(str(r['commission']))/100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) if r.get('price') is not None and r.get('commission') is not None and live else None
    r['amazon_url']='https://www.amazon.com/dp/'+r['asin']
    r.setdefault('video_count_source','Keepa saved scan' if r.get('total_videos') is not None else 'Unknown')
    r.setdefault('video_count_confidence','observed, not exhaustive' if r.get('total_videos') is not None else 'Unknown')
    if raw:
        r.update(KeepaVideos().normalize(raw))
        stats=raw.get('stats') or {};cur=stats.get('current') or []
        def track(values,index,scale=1):
            v=numeric(values[index]) if len(values)>index else None
            return v/scale if v is not None else None
        r['rating']=track(cur,16,10);r['review_count']=track(cur,17)
        # Offer count is distinct from seller count. Count distinct sellers only with complete live offers.
        offers=raw.get('offers');order=raw.get('liveOffersOrder')
        r['seller_count']=len({offers[i]['sellerId'] for i in order if isinstance(i,int) and 0<=i<len(offers) and offers[i].get('sellerId')}) if isinstance(offers,list) and isinstance(order,list) and order and all(isinstance(i,int) and 0<=i<len(offers) and offers[i].get('sellerId') for i in order) else None
        r['seller_count_source']='Keepa observed live offers; may be partial' if r['seller_count'] is not None else 'Unknown'
        r['variant_count']=len(raw['variations']) if isinstance(raw.get('variations'),list) else None
        r['bsr_avg30']=track(stats.get('avg30') or [],3);r['bsr_avg90']=track(stats.get('avg90') or [],3)
        for days in (30,90):
            values=stats.get('avg'+str(days)) or []
            r['price_avg'+str(days)]=next((track(values,i,100) for i in (18,0,1) if track(values,i,100) is not None),None)
        images=raw.get('images') or []; image=next((i.get('m') or i.get('l') for i in images if isinstance(i,dict) and (i.get('m') or i.get('l'))),None)
        r['image']='https://m.media-amazon.com/images/I/'+image if image and re.fullmatch(r'[A-Za-z0-9+_.%\-]+',image) else None
        r['keepa_last_updated']=timestamp(raw.get('lastUpdate'));r['sales_last_updated']=timestamp(raw.get('lastSoldUpdate'))
        r['listed_since']=timestamp(raw.get('listedSince'))
        r['history']={'monthly_sold':raw.get('monthlySoldHistory'),'bsr':(raw.get('csv') or [None]*4)[3] if len(raw.get('csv') or [])>3 else None}
    r['sales_trend_direction']=trend_label(r.get('growth'),cfg['thresholds'])
    r['film_score'],r['score_components'],r['score_coverage']=score(r,cfg)
    r['sources']={'price':'Keepa','bsr':'Keepa','monthly_sold':'Amazon bought-in-past-month via Keepa (bracketed lower bound)','cc':'Creator Connection CSV import','video':r['video_count_source'],'growth':'Calculated from full 90-day time-weighted monthly-sold history; BSR is diagnostic only'}
    r['subcategory']=(r.get('category') or '').split(' > ')[-1] or None
    r['apparel']=(r.get('checks') or {}).get('not_apparel') is False
    return r
