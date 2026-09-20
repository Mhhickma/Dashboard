import re

def parse_asins(value):
    if not isinstance(value,str) or len(value)>50000:raise ValueError('Paste at most 1,000 ASINs')
    entries=[s for s in re.split(r'[\s,;]+',value.upper().strip()) if s]
    if not entries or any(not re.fullmatch(r'[A-Z0-9]{10}',s) for s in entries):raise ValueError('Use 10-character ASINs separated by spaces, commas or new lines')
    result=list(dict.fromkeys(entries))
    if len(result)>1000:raise ValueError('Maximum 1,000 unique ASINs')
    return result
