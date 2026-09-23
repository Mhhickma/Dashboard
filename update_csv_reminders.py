import json
import re
from datetime import datetime, timezone
from pathlib import Path


SOURCE = Path("data/creator-connections")
OUTPUT = Path("data/csv-reminders.json")
STAMP = re.compile(r"^(\d{8}T\d{9}Z)-")


def latest(suffix):
    matches = []
    for path in SOURCE.glob(f"*{suffix}"):
        match = STAMP.match(path.name)
        if match:
            matches.append(datetime.strptime(match.group(1), "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc))
    return max(matches).isoformat().replace("+00:00", "Z") if matches else None


OUTPUT.write_text(
    json.dumps(
        {
            "cc_updated_at": latest("-replacement-complete.csv"),
            "accepted_updated_at": latest("-accepted-history.csv"),
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
