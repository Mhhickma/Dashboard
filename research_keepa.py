"""Shared saved Keepa normalization for Film Research. No network requests."""
import argparse
import csv
import hashlib
import json
import math
import os
import random
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path



UTC = timezone.utc
EPOCH = datetime(2011, 1, 1, tzinfo=UTC).timestamp()
ASIN = re.compile(r"(?<![A-Z0-9])[A-Z0-9]{10}(?![A-Z0-9])")
DAY = 86400


def number(value):
    try:
        n = float(str(value).replace(",", "").replace("$", "").replace("%", "").strip())
        return n if math.isfinite(n) and n >= 0 else None
    except (TypeError, ValueError):
        return None


def date(value):
    text = str(value or "").strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%b %d, %Y", "%B %d, %Y"):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                pass
    return None


def normalized(row):
    return {re.sub(r"[^a-z0-9]", "", k.lower()): v for k, v in row.items() if k}


def campaign(row):
    r = normalized(row)
    def get(*keys):
        return next((r[k] for k in keys if r.get(k) not in (None, "")), "")
    commission = number(get("commissionrate", "commission", "commissionpercentage"))
    # A bare 0.10 is a fraction; explicit 0.10% remains 0.10 percent.
    if commission is not None and commission <= 1 and "%" not in str(get("commissionrate", "commission", "commissionpercentage")):
        commission *= 100
    result = dict(
        campaign_id=get("campaignid"), name=get("campaignname", "name"),
        brand=get("brandname", "brand"), commission=commission,
        start=date(get("campaignstartdate", "startdate")), end=date(get("campaignenddate", "enddate")),
        budget=number(get("campaignbudget", "budget")),
        budget_remaining=number(get("budgetremaining", "remainingbudget", "campaignbudgetremaining")),
        available_slots=number(get("availablecreatorslots", "availableslots", "availableslot", "creatorslotsavailable", "availablecreator slots")),
        total_slots=number(get("totalcreatorslots", "totalslots", "totalslot", "creatorslots")),
        recommended=str(get("recommended")).lower() in ("true", "yes", "1"),
        status=str(get("campaignstatus", "status")).strip().lower(),
    )
    identity = result["campaign_id"] or json.dumps([result[k] for k in ("name", "brand", "start", "end")])
    result["key"] = hashlib.sha256(identity.encode()).hexdigest()
    return result


def active(c, today):
    return bool(c["start"] and c["end"] and c["start"] <= today <= c["end"]
                and c["status"] not in {"inactive", "paused", "cancelled", "canceled", "ended", "expired", "closed", "upcoming"}
                and c["commission"] is not None and c["commission"] >= 10)


def connect(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript("""
      PRAGMA journal_mode=DELETE;
      CREATE TABLE IF NOT EXISTS sources(path TEXT PRIMARY KEY, digest TEXT, rownum INTEGER, complete INTEGER, priority TEXT);
      CREATE TABLE IF NOT EXISTS campaigns(source TEXT, id TEXT, payload TEXT, PRIMARY KEY(source,id));
      CREATE TABLE IF NOT EXISTS links(source TEXT, id TEXT, asin TEXT, PRIMARY KEY(source,id,asin));
      CREATE INDEX IF NOT EXISTS links_asin ON links(asin);
      CREATE INDEX IF NOT EXISTS links_id ON links(id);
      CREATE TABLE IF NOT EXISTS cache(asin TEXT PRIMARY KEY, fetched REAL, payload TEXT);
      CREATE TABLE IF NOT EXISTS selected(asin TEXT PRIMARY KEY);
      CREATE TABLE IF NOT EXISTS failures(asin TEXT PRIMARY KEY, code TEXT, attempts INTEGER, last_at REAL);
    """)
    return db


def digest_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def import_sources(db, paths, deadline):
    """Checkpoint logical CSV rows; never split multiline records or collect all ASINs."""
    csv.field_size_limit(16 * 1024 * 1024)
    names = {str(p.as_posix()) for p in paths}
    with db:
        for (old,) in db.execute("SELECT path FROM sources").fetchall():
            if old not in names:
                for table in ("campaigns", "links"):
                    db.execute(f"DELETE FROM {table} WHERE source=?", (old,))
                db.execute("DELETE FROM sources WHERE path=?", (old,))
    for path in paths:
        name, digest = path.as_posix(), digest_file(path)
        source = db.execute("SELECT digest,rownum,complete FROM sources WHERE path=?", (name,)).fetchone()
        if source and source[0] == digest and source[2]:
            continue
        if not source or source[0] != digest:
            with db:
                for table in ("campaigns", "links"):
                    db.execute(f"DELETE FROM {table} WHERE source=?", (name,))
                # New upload filenames contain an ISO-sortable UTC timestamp. Legacy paths sort first.
                db.execute("INSERT OR REPLACE INTO sources VALUES(?,?,0,0,?)", (name, digest, path.name if re.match(r"\d{8}T", path.name) else "0" + path.name))
            source = (digest, 0, 0)
        rownum = 0
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            headers = normalized({k: "" for k in reader.fieldnames or []})
            if "asinlist" not in headers:
                raise ValueError("CSV requires an ASIN List column")
            for rownum, row in enumerate(reader, 1):
                if rownum <= source[1]:
                    continue
                if None in row or any(v is None for v in row.values()):
                    raise ValueError("Malformed CSV row; import stopped without querying Keepa")
                c = campaign(row)
                db.execute("INSERT OR REPLACE INTO campaigns VALUES(?,?,?)", (name, c["key"], json.dumps(c)))
                for match in ASIN.finditer(str(normalized(row).get("asinlist", "")).upper()):
                    db.execute("INSERT OR IGNORE INTO links VALUES(?,?,?)", (name, c["key"], match.group()))
                if rownum % 500 == 0:
                    db.execute("UPDATE sources SET rownum=? WHERE path=?", (rownum, name))
                    db.commit()
                    if time.monotonic() >= deadline:
                        return False
        db.execute("UPDATE sources SET rownum=?,complete=1 WHERE path=?", (rownum, name))
        db.commit()
    return True


def eligible_index(db, today):
    db.executescript("DROP TABLE IF EXISTS temp.eligible; CREATE TEMP TABLE eligible(id TEXT PRIMARY KEY,source TEXT,payload TEXT);")
    # Repeated snapshots of one campaign are not separate campaigns. Latest file wins,
    # including a newer cancellation or commission reduction.
    query = """SELECT id,source,payload FROM (
      SELECT c.*, ROW_NUMBER() OVER(PARTITION BY c.id ORDER BY s.priority DESC,s.path DESC) AS n
      FROM campaigns c JOIN sources s ON c.source=s.path WHERE s.complete=1) WHERE n=1"""
    for cid, source, payload in db.execute(query):
        if active(json.loads(payload), today):
            db.execute("INSERT INTO eligible VALUES(?,?,?)", (cid, source, payload))


def campaigns_for(db, asin):
    return [json.loads(row[0]) for row in db.execute("""SELECT e.payload FROM eligible e
      JOIN links l ON l.id=e.id WHERE l.asin=? GROUP BY e.id ORDER BY e.id""", (asin,))]


def points(values):
    if not isinstance(values, list) or len(values) % 2:
        return []
    result = {}
    for i in range(0, len(values), 2):
        stamp, value = number(values[i]), number(values[i+1])
        if stamp is not None:
            result[EPOCH + stamp * 60] = value
    return sorted(result.items())


def average(values, now, days):
    """Time-weighted step history. Require an anchor and full valid window coverage."""
    history = [(t, v) for t, v in points(values) if t <= now]
    start = now - days * DAY
    anchors = [(t, v) for t, v in history if t <= start]
    if not anchors or anchors[-1][1] is None:
        return None
    prev, value, total = start, anchors[-1][1], 0
    for stamp, next_value in history:
        if stamp <= start:
            continue
        if value is None:
            return None
        total += (stamp - prev) * value
        prev, value = stamp, next_value
    if value is None:
        return None
    return (total + (now - prev) * value) / (days * DAY)


def book_asin(asin):
    # Amazon uses ISBN-10 identifiers for books. Validate the check digit.
    value = str(asin).upper()
    return bool(re.fullmatch(r"[0-9]{9}[0-9X]", value)) and sum(
        (10-i)*(10 if c == "X" else int(c)) for i,c in enumerate(value)) % 11 == 0


def books(p):
    nodes = p.get("categoryTree") or []
    return (book_asin(p.get("asin", "")) or str(p.get("rootCategory")) == "283155"
        or any(isinstance(n, dict) and (str(n.get("catId")) == "283155" or str(n.get("name", "")).lower() == "books") for n in nodes)
        or str(p.get("websiteDisplayGroup", "")).lower() in {"book", "books"})


def apparel(p):
    nodes = [str(n.get("name", "")).lower() for n in (p.get("categoryTree") or []) if isinstance(n, dict)]
    detail = " ".join(nodes[1:] + [str(p.get(k) or "").lower() for k in ("productGroup", "type", "itemTypeKeyword", "title")])
    product_type = str(p.get("type") or "").lower().replace("_", " ")
    if re.search(r"\b(ppe|personal protective|safety (?:vest|glasses|goggles|equipment|gloves|boots)|protective (?:coverall|clothing|gear|gloves)|welding (?:gloves|helmet|apron|jacket)|work gloves|respirator|hard hat|tool belt|fall protection|tactical vest)\b", detail) and product_type not in {"shirt", "t shirt", "sweatshirt"}:
        return False
    # Do not reject the broad Clothing, Shoes & Jewelry root or words like 'outdoors'.
    if any(n in {"clothing", "apparel", "shirts", "pants", "dresses", "underwear", "sleepwear", "socks", "jackets & coats", "fashion hoodies & sweatshirts"} for n in nodes):
        return True
    group = str(p.get("websiteDisplayGroupName") or p.get("binding") or "").lower()
    if group in {"apparel", "clothing"} or product_type in {"shirt", "pants", "dress", "skirt", "coat", "jacket", "sock", "underwear", "sweatshirt"}:
        return True
    broad_clothing = bool(nodes and "clothing" in nodes[0])
    if (not nodes or broad_clothing) and re.search(r"\b(t-shirt|tshirt|sweatshirt|hoodie|lingerie|pajamas|leggings|blouse|swimsuit)\b", detail):
        return True
    if broad_clothing and len(nodes) == 1:
        return None
    return False if nodes or group else None


def evaluate(p, campaigns, now, fetched, ttl_hours=24):
    campaigns = [c for c in campaigns if active(c, datetime.fromtimestamp(now, UTC).date().isoformat())]
    def stat(index):
        values = (p.get("stats") or {}).get("current") or []
        return number(values[index]) if len(values) > index else None
    current = number(p.get("monthlySold"))
    last_sold = number(p.get("lastSoldUpdate"))
    sold_fresh = last_sold is not None and 0 <= now - (EPOCH + last_sold * 60) <= 30 * DAY
    avg = average(p.get("monthlySoldHistory"), now, 90) if sold_fresh else None
    growth = (current / avg - 1) * 100 if current is not None and avg is not None and avg > 0 else None
    # Video metadata is independent of whether seller offers were retrieved.
    from research_model import KeepaVideos
    video = KeepaVideos().normalize(p)
    merchant = video['merchant_video']
    total = video['total_videos']
    influencers = video['influencer_videos']
    community = None
    main_video = p.get("hasMainVideo") is True or video['main_video'] is True
    rank = stat(3)
    csvs = p.get("csv") or []
    ranks = csvs[3] if len(csvs) > 3 else None
    refs = points(p.get("salesRankReferenceHistory"))
    ref = p.get("salesRankReference")
    comparable = not any(t >= now - 90 * DAY and v != ref for t, v in refs)
    bsr30 = average(ranks, now, 30) if comparable else None
    bsr90 = average(ranks, now, 90) if comparable else None
    best = max(campaigns, key=lambda c: (c["commission"], c["budget_remaining"] or 0, c["available_slots"] or 0)) if campaigns else {}
    price_value, price_source = None, None
    for index, label in ((18, "Buy Box including shipping"), (0, "Amazon"), (1, "New offer")):
        candidate = stat(index)
        if candidate is not None and candidate > 0:
            price_value, price_source = candidate / 100, label
            break
    clothing = apparel(p)
    checks = {
        "active_campaign_and_commission": bool(campaigns), "not_apparel": clothing is False, "not_books": not books(p),
        "merchant_video": merchant is True, "fewer_than_5_videos": total is not None and total < 5,
        "sales_growth": current is not None and avg is not None and avg > 0 and current * 10 >= 11 * avg,
        "fresh_cache": 0 <= now - fetched <= ttl_hours * 3600,
        "standard_product": p.get("productType") == 0,
    }
    result = dict(asin=p.get("asin"), title=p.get("title"), brand=p.get("brand") or best.get("brand"),
        category=" > ".join(n.get("name", "") for n in (p.get("categoryTree") or []) if isinstance(n, dict)),
        browse_nodes=p.get("categoryTree"), price=price_value, price_source=price_source,
        commission=best.get("commission"), monthly_sold=current, monthly_sold_90=avg, growth=growth,
        sales_trend="unavailable" if growth is None else "pass" if checks["sales_growth"] else "fail",
        bsr=rank, bsr30=(1-rank/bsr30)*100 if rank and bsr30 else None,
        bsr90=(1-rank/bsr90)*100 if rank and bsr90 else None,
        main_video=True if main_video else None, merchant_video=merchant, total_videos=total, influencer_videos=influencers, community_videos=community,
        video_scope="Keepa observed carousel/community videos; not a guaranteed Amazon-wide total",
        budget_remaining=best.get("budget_remaining"), available_slots=best.get("available_slots"),
        campaigns=campaigns, qualifying_campaign_count=len(campaigns), recommended=any(c["recommended"] for c in campaigns),
        checks=checks, qualified=all(checks.values()), fetched_at=fetched,
        failed_filters=[k for k, v in checks.items() if not v], score=None,
        valid_until=min([fetched+ttl_hours*3600] + [datetime.fromisoformat(c["end"]).replace(tzinfo=UTC).timestamp()+DAY for c in campaigns]))
    result["near_miss"] = (total in (5, 6) and main_video and all(v for k, v in checks.items() if k != "fewer_than_5_videos"))
    if result["qualified"]:
        result["score"] = round(25*min(math.log10(1+(current or 0))/4, 1) + 25*min(max(growth or 0, 0)/100, 1)
            + 20*(5-total)/5 + 15*min(best["commission"]/30, 1) + 5*min(price_value or 0, 200)/200
            + 5*min(best.get("budget_remaining") or 0, 10000)/10000
            + 5*min(best.get("available_slots") or 0, 100)/100, 2)
    return result


