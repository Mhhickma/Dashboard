"""Upcoming campaigns from the current completed CC upload."""
import csv
import hashlib
from datetime import date
from cc_batches import active_csv_files

def upcoming(folder, today=None):
    today = today or date.today()
    campaigns = {}
    invalid = 0
    files = active_csv_files(folder)
    for path in files:
        with path.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                campaign = row.get('Campaign Id', '').strip()
                try:
                    start = date.fromisoformat(row.get('Campaign Start Date', '').strip())
                except ValueError:
                    invalid += 1
                    continue
                if campaign and start > today:
                    campaigns[campaign] = {'id': campaign, 'start': start.isoformat(), 'name': row.get('Campaign Name', ''), 'commission': row.get('Commission Rate', '')}
    rows = sorted(campaigns.values(), key=lambda row: (row['start'], row['id']))
    ids = [row['id'] for row in rows]
    return {'campaign_ids': ids, 'rows': rows, 'today': today.isoformat(), 'invalid_dates': invalid,
            'cc_files': len(files), 'batch_key': hashlib.sha256('\n'.join(ids).encode()).hexdigest()}
