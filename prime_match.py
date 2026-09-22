"""Local CSV intersection; no paid lookups."""
import csv,io,re
from decimal import Decimal,InvalidOperation
from cc_batches import active_csv_files

def amount(value):
    try:
        n=Decimal(str(value).strip().replace('$','').replace(',',''))
        return n if n.is_finite() and n>0 else None
    except (InvalidOperation,ValueError):return None

def match(text,folder):
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    required={'asin','promotionPrice','lowestPriceYtd'}
    if not required.issubset(reader.fieldnames or []):raise ValueError('CSV must include asin, promotionPrice and lowestPriceYtd.')
    deals={};total=0;invalid=0;over=0
    for r in reader:
        total+=1;a=r['asin'].strip().upper();price=amount(r['promotionPrice']);low=amount(r['lowestPriceYtd'])
        if not re.fullmatch(r'[A-Z0-9]{10}',a) or price is None or low is None:invalid+=1;continue
        if price>low*Decimal('1.10'):over+=1;continue
        ratio=(price/low-1)*100
        item=dict(asin=a,title=r.get('asin_name') or r.get('deal_title') or a,event_price=float(price),ytd_low=float(low),vs_ytd_pct=float(ratio),advertised_discount=r.get('discountPct',''),start=r.get('promotionStartTimestamp',''),end=r.get('promotionEndTimestamp',''),campaign_ids=[])
        if a not in deals or ratio<Decimal(str(deals[a]['vs_ytd_pct'])):deals[a]=item
    paths=active_csv_files(folder)
    if not paths:raise ValueError('No completed CC list is available on this PC.')
    for path in paths:
        with path.open(encoding='utf-8-sig',newline='') as stream:
            for r in csv.DictReader(stream):
                cid=(r.get('Campaign Id') or r.get('Campaign ID') or '').strip()
                if not cid:continue
                for a in set(re.findall(r'(?<![A-Z0-9])[A-Z0-9]{10}(?![A-Z0-9])',(r.get('ASIN List') or '').upper())) & deals.keys():
                    if cid not in deals[a]['campaign_ids']:deals[a]['campaign_ids'].append(cid)
    rows=sorted((r for r in deals.values() if r['campaign_ids']),key=lambda r:(r['vs_ytd_pct'],r['asin']))
    ids=list(dict.fromkeys(c for r in rows for c in r['campaign_ids']))
    return dict(rows=rows,campaign_ids=ids,input_rows=total,invalid_rows=invalid,above_limit=over,not_in_cc=sum(not r['campaign_ids'] for r in deals.values()),cc_files=len(paths),cc_source=paths[-1].name,cc_replacement='-replacement-' in paths[-1].name)
