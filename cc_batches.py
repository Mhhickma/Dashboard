"""Only completed replacement batches are active; old files remain archived."""
import csv
import re
from pathlib import Path

def active_csv_files(folder):
    folder=Path(folder)
    manifests=sorted(folder.glob('*-replacement-complete.csv'))
    if not manifests:
        return sorted(p for p in folder.glob('*.csv') if '-replacement-' not in p.name)
    manifest=manifests[-1]
    prefix=manifest.name.removesuffix('complete.csv')
    with manifest.open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.DictReader(stream))
    names=[row.get('Batch file','') for row in rows]
    if not names or len(names)!=len(set(names)):raise ValueError('Invalid completed CC batch')
    for name in names:
        if not re.fullmatch(re.escape(prefix)+r'\d{4}-\d{6}\.csv',name) or not (folder/name).is_file():
            raise ValueError('Completed CC batch has missing or invalid files')
    return [folder/name for name in names]
