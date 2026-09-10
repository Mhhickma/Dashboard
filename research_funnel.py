"""One filter contract for the local feed and on-demand scan."""
import math

NUMBERS={'commission_min','commission_max','price_min','price_max','sales_min','influencer_max','score_min','rating_min','reviews_min','variants_max','sellers_max','growth_min','total_videos_max'}
BOOLS={'cc_only','exclude_apparel','merchant_required','main_required'}
TEXT={'q','category','exclude_categories','trend','bsr_trend','expires_before','expires_after'}

def normalize(filters,config):
    result={}
    defaults=config['filters']
    for key in NUMBERS:
        v=filters.get(key,defaults.get(key))
        if v not in ('',None):
            v=float(v)
            if not math.isfinite(v):raise ValueError('Filters must be finite numbers')
            result[key]=v
    for key in BOOLS:
        v=filters.get(key,defaults.get(key,False))
        result[key]=v is True or v=='true'
    for key in TEXT:
        v=filters.get(key,defaults.get(key,''))
        result[key]=','.join(v) if isinstance(v,list) else str(v or '')
    if filters.get('view')=='trending' and not result['trend']:result['trend']='rising'
    if filters.get('view')=='low':result['influencer_max']=min(result.get('influencer_max',float('inf')),config['thresholds']['primary_videos_max'])
    if result['trend'] not in ('','rising','flat','falling') or result['bsr_trend'] not in ('','improving','worsening'):raise ValueError('Invalid trend filter')
    return result

def reasons(row,f,config):
    failed=[]
    def check(key,ok):
        if not ok:failed.append(key)
    if f.get('cc_only'):check('active_cc',row.get('cc_active') is True)
    if f.get('exclude_apparel'):check('not_apparel',(row.get('checks') or {}).get('not_apparel') is True)
    for key,field,op in [('commission_min','commission',lambda a,b:a>b),('commission_max','commission',lambda a,b:a<=b),('price_min','price',lambda a,b:a>=b),('price_max','price',lambda a,b:a<=b),('sales_min','monthly_sold',lambda a,b:a>=b),('influencer_max','influencer_videos',lambda a,b:a<=b),('total_videos_max','total_videos',lambda a,b:a<=b),('growth_min','growth',lambda a,b:a>=b),('score_min','film_score',lambda a,b:a>=b),('rating_min','rating',lambda a,b:a>=b),('reviews_min','review_count',lambda a,b:a>=b),('variants_max','variant_count',lambda a,b:a<=b),('sellers_max','seller_count',lambda a,b:a<=b)]:
        if key in f:check(key,row.get(field) is not None and op(row[field],f[key]))
    for key,field in [('merchant_required','merchant_video'),('main_required','main_video')]:
        if f.get(key):check(key,row.get(field) is True)
    category=(row.get('category') or '')
    if f.get('category'):check('category',category==f['category'])
    for cat in f.get('exclude_categories','').split(','):
        if cat.strip():check('excluded_category',bool(category) and cat.strip().lower() not in category.lower())
    if f.get('q'):check('search',f['q'].lower() in ' '.join(str(row.get(k) or '') for k in ('asin','title','brand')).lower())
    growth=row.get('growth');band=config['thresholds']['stable_band']
    if f.get('trend'):check('sales_trend',growth is not None and {'rising':growth>band,'flat':abs(growth)<=band,'falling':growth < -band}[f['trend']] if growth is not None else False)
    bsr=row.get('bsr90')
    if f.get('bsr_trend'):check('bsr_trend',bsr is not None and (bsr>0 if f['bsr_trend']=='improving' else bsr<0))
    if f.get('expires_before'):check('expires_before',bool(row.get('campaign_end')) and row['campaign_end']<=f['expires_before'])
    if f.get('expires_after'):check('expires_after',bool(row.get('campaign_end')) and row['campaign_end']>=f['expires_after'])
    return sorted(set(failed))
