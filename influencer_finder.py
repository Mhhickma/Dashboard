"""Bounded Finder shortlist, stored in the same checkpoint as product results."""
import hashlib
import json
import math
import time
import requests


def shortlist(db, api, limit):
    selection = {"categories_exclude": [283155], "productType": [0],
        "videoCount_gte": 1, "videoCount_lte": 6, "hasMainVideo": True,
        "monthlySold_gte": 1, "sort": [["monthlySold", "desc"], ["current_SALES", "asc"]],
        "perPage": max(50, limit), "page": 0}
    key = hashlib.sha256(json.dumps(selection, sort_keys=True).encode()).hexdigest()
    db.execute("CREATE TABLE IF NOT EXISTS finder_shortlists(key TEXT PRIMARY KEY, fetched REAL, asins TEXT)")
    saved = db.execute("SELECT asins FROM finder_shortlists WHERE key=?", (key,)).fetchone()
    if saved:
        return json.loads(saved[0]), None
    for attempt in range(3):
        reserve = 10 + math.ceil(selection["perPage"] / 100)
        if api.reserved + reserve > api.budget or time.monotonic()+100 >= api.deadline:
            return [], "paused_finder_budget_or_time"
        api.reserved += reserve
        try:
            response = api.session.post("https://api.keepa.com/query", params={"key":api.key,"domain":1}, json=selection, timeout=(10,90))
            payload = response.json()
            used = payload.get("tokensConsumed")
            if isinstance(used, (int,float)):
                api.consumed += used
            else:
                api.usage_unknown = True
            api.balance = payload.get("tokensLeft", api.balance)
            api.refill = payload.get("refillRate", api.refill)
            if response.status_code == 200 and not payload.get("error") and isinstance(payload.get("asinList"),list):
                asins = list(dict.fromkeys(a for a in payload["asinList"] if isinstance(a,str) and len(a)==10 and a.isalnum()))[:limit]
                with db:
                    db.execute("INSERT OR REPLACE INTO finder_shortlists VALUES(?,?,?)", (key,time.time(),json.dumps(asins)))
                return asins, None
            if response.status_code not in (429,500,502,503,504):
                return [], "finder_http_"+str(response.status_code)
        except (requests.RequestException,ValueError,TypeError):
            api.usage_unknown = True
        delay = 2**(attempt+1)
        if time.monotonic()+delay+100 >= api.deadline:
            break
        time.sleep(delay)
    return [], "paused_finder_retry"
