"""Upcoming campaigns, excluding campaigns already accepted by the user."""
import csv
import hashlib
import io
import json
from datetime import date
from cc_batches import active_csv_files

CAMPAIGN_ID_HEADERS = ('Campaign Id', 'Campaign ID', 'campaign_id', 'campaignId')

def _campaign_id(row):
    return next((row.get(header, '').strip() for header in CAMPAIGN_ID_HEADERS
                 if row.get(header, '').strip()), '')

def accepted_ids_from_csv(text):
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if not reader.fieldnames or not any(header in reader.fieldnames for header in CAMPAIGN_ID_HEADERS):
        raise ValueError('Accepted CSV must include a Campaign Id column')
    return {_campaign_id(row) for row in reader if _campaign_id(row)}

def load_accepted(path):
    path = path and path if hasattr(path, 'exists') else None
    if not path or not path.exists():
        return set()
    data = json.loads(path.read_text(encoding='utf-8'))
    return {str(value).strip() for value in data.get('campaign_ids', []) if str(value).strip()}

def merge_accepted(path, text):
    imported = accepted_ids_from_csv(text)
    if not imported:
        raise ValueError('No campaign IDs were found in the accepted CSV')
    existing = load_accepted(path)
    combined = existing | imported
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'campaign_ids': sorted(combined)}, indent=2), encoding='utf-8')
    temporary.replace(path)
    return {'imported': len(imported), 'added': len(combined - existing), 'accepted_total': len(combined)}

def upcoming(folder, today=None, accepted_path=None):
    today = today or date.today()
    campaigns = {}
    invalid = 0
    accepted = load_accepted(accepted_path)
    files = active_csv_files(folder)
    for path in files:
        with path.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                campaign = _campaign_id(row)
                try:
                    start = date.fromisoformat(row.get('Campaign Start Date', '').strip())
                except ValueError:
                    invalid += 1
                    continue
                if campaign and start > today:
                    campaigns[campaign] = {'id': campaign, 'start': start.isoformat(), 'name': row.get('Campaign Name', ''), 'commission': row.get('Commission Rate', '')}
    upcoming_total = len(campaigns)
    excluded = len(set(campaigns) & accepted)
    rows = sorted((row for campaign, row in campaigns.items() if campaign not in accepted),
                  key=lambda row: (row['start'], row['id']))
    ids = [row['id'] for row in rows]
    return {'campaign_ids': ids, 'rows': rows, 'today': today.isoformat(), 'invalid_dates': invalid,
            'cc_files': len(files), 'upcoming_total': upcoming_total,
            'accepted_total': len(accepted), 'accepted_excluded': excluded,
            'batch_key': hashlib.sha256('\n'.join(ids).encode()).hexdigest()}
