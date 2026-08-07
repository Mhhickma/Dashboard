"""
Best Seller Deals Fetcher
-------------------------
Weekly: builds a watchlist from the top 200 Keepa best sellers in each configured category.
Hourly: checks the next saved ASINs with Amazon Creators API for live price, and uses
Keepa-style price-drop rules to decide what appears on the Best Seller Deals page.
"""

import json
import os
import re
import time
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import keepa
from amazon_creatorsapi import AmazonCreatorsApi, Country
from amazon_creatorsapi.models import GetItemsResource

KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")
CREDENTIAL_ID = os.getenv("CREATORS_CREDENTIAL_ID")
CREDENTIAL_SECRET = os.getenv("CREATORS_CREDENTIAL_SECRET")
PARTNER_TAG = os.getenv("AFFILIATE_TAG") or os.getenv("AMAZON_TAG") or "simplewoodsho-20"

CONFIG_FILE = "best_seller_categories.json"
WATCHLIST_FILE = "data/best_seller_watchlist.json"
STATE_FILE = "data/best_seller_state.json"
DEALS_FILE = "data/best_seller_deals.json"

AMAZON_BATCH_SIZE = 10
AMAZON_CONCURRENT_BATCHES = int(os.getenv("BEST_SELLER_AMAZON_CONCURRENT_BATCHES", "3"))
AMAZON_REQUEST_DELAY_SECONDS = float(os.getenv("BEST_SELLER_AMAZON_REQUEST_DELAY_SECONDS", "1"))

BAD_KEYWORDS = [
    "sex", "doll", "erotic", "fetish", "penis", "vagina", "dildo", "vibrator",
    "nude", "naked", "porn", "xxx", "bdsm", "bondage"
]

BLACKLISTED_ASINS = {
    "B0CNSFQ988", "B0CNSDDJ1C", "B0CNSDNT27", "B0CNSCN4KW", "B0CNSCZQ1W", "B0CNSBX4ZK"
}


def utc_now():
    return datetime.now(timezone.utc)


def iso_now():
    return utc_now().isoformat()


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"Warning: could not load {path}: {exc}")
        return default


def save_json(path, data):
    parent = Path(path).parent
    if str(parent) != ".":
        parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


PUBLIC_PRODUCT_FIELDS = (
    "asin", "title", "brand", "cat", "image", "image_candidates",
    "current_price", "avg_7_price", "min_7_price", "avg_30_price",
    "min_30_price", "drop_percent", "drop_30_percent", "price",
    "price_amount", "currency", "availability", "amazon_url", "link",
    "desc", "posted_at", "first_seen_at", "checked_at", "last_checked_at",
    "expires_at", "seen_at", "updated_at", "qualification_reasons",
)


def public_product(product):
    return {key: product.get(key) for key in PUBLIC_PRODUCT_FIELDS if product.get(key) is not None}


def compact_image_url(url, size=160):
    if not url:
        return None
    return re.sub(r"\._SL\d+_\.", f"._SL{size}_.", str(url))


def product_image(item, fallback=None):
    """Return the best available Creators API image without erasing a saved image."""
    try:
        primary = item.images.primary
        for size in ("large", "medium", "small", "hi_res"):
            image_size = getattr(primary, size, None)
            url = getattr(image_size, "url", None)
            if url:
                return compact_image_url(url)
    except Exception:
        pass
    return compact_image_url(fallback)


def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def float_or_none(value):
    try:
        number = float(value)
        return number if number == number else None
    except Exception:
        return None


def is_bad_title(title):
    if not title or len(title.strip()) < 3:
        return True
    lower = title.lower()
    return any(word in lower for word in BAD_KEYWORDS)


def load_config():
    config = load_json(CONFIG_FILE, {})
    if not config:
        raise RuntimeError(f"Missing {CONFIG_FILE}")
    return config


def refresh_needed(watchlist, refresh_hours):
    generated_at = parse_time(watchlist.get("generatedAt"))
    if not generated_at:
        return True
    return utc_now() - generated_at >= timedelta(hours=refresh_hours)


def build_watchlist(config):
    print("Building weekly best-seller ASIN watchlist from Keepa...")
    api = keepa.Keepa(KEEPA_API_KEY)
    top_per_category = int(config.get("topPerCategory", 200))
    domain = "US" if int(config.get("domainId", 1)) == 1 else "US"

    items_by_asin = {}
    categories = [c for c in config.get("categories", []) if c.get("enabled", True)]

    for category in categories:
        category_id = str(category["categoryId"])
        category_name = category.get("name", category_id)
        category_slug = category.get("slug", f"category-{category_id}")
        try:
            asins = api.best_sellers_query(category_id, domain=domain)
            top_asins = asins[:top_per_category]
            print(f"  {category_name}: {len(top_asins)} ASINs")
        except Exception as exc:
            print(f"  Failed to fetch {category_name} ({category_id}): {exc}")
            top_asins = []

        for rank, asin in enumerate(top_asins, start=1):
            if asin in BLACKLISTED_ASINS:
                continue
            if asin not in items_by_asin:
                items_by_asin[asin] = {
                    "asin": asin,
                    "categories": [],
                    "bestRank": rank,
                }
            items_by_asin[asin]["categories"].append({
                "categoryId": int(category_id),
                "name": category_name,
                "slug": category_slug,
                "rank": rank,
            })
            items_by_asin[asin]["bestRank"] = min(items_by_asin[asin]["bestRank"], rank)
        time.sleep(1)

    items = sorted(items_by_asin.values(), key=lambda x: (x.get("bestRank", 999999), x.get("asin", "")))
    watchlist = {
        "generatedAt": iso_now(),
        "source": "Keepa best_sellers_query",
        "topPerCategory": top_per_category,
        "count": len(items),
        "items": items,
    }
    save_json(WATCHLIST_FILE, watchlist)
    print(f"Saved {len(items)} unique ASINs to {WATCHLIST_FILE}")
    return watchlist


def get_amazon_resources():
    return [
        GetItemsResource.ITEM_INFO_DOT_TITLE,
        GetItemsResource.ITEM_INFO_DOT_BY_LINE_INFO,
        GetItemsResource.ITEM_INFO_DOT_CLASSIFICATIONS,
        GetItemsResource.IMAGES_DOT_PRIMARY_DOT_HIGH_RES,
        GetItemsResource.IMAGES_DOT_PRIMARY_DOT_LARGE,
        GetItemsResource.IMAGES_DOT_PRIMARY_DOT_MEDIUM,
        GetItemsResource.IMAGES_DOT_PRIMARY_DOT_SMALL,
        GetItemsResource.OFFERS_V2_DOT_LISTINGS_DOT_PRICE,
        GetItemsResource.OFFERS_V2_DOT_LISTINGS_DOT_AVAILABILITY,
        GetItemsResource.OFFERS_V2_DOT_LISTINGS_DOT_CONDITION,
        GetItemsResource.OFFERS_V2_DOT_LISTINGS_DOT_IS_BUY_BOX_WINNER,
        GetItemsResource.OFFERS_V2_DOT_LISTINGS_DOT_DEAL_DETAILS,
    ]


def fetch_amazon_batch(batch, batch_num, total_batches):
    print(f"  Amazon batch {batch_num}/{total_batches} ({len(batch)} ASINs)")
    amazon = AmazonCreatorsApi(
        credential_id=CREDENTIAL_ID,
        credential_secret=CREDENTIAL_SECRET,
        version="3.1",
        tag=PARTNER_TAG,
        country=Country.US,
    )
    return amazon.get_items(batch, resources=get_amazon_resources())


def get_amazon_items(asins):
    batches = [asins[i:i + AMAZON_BATCH_SIZE] for i in range(0, len(asins), AMAZON_BATCH_SIZE)]
    total_batches = len(batches)
    worker_count = max(1, min(AMAZON_CONCURRENT_BATCHES, total_batches))
    all_items = {}

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = []
        for idx, batch in enumerate(batches, start=1):
            futures.append(executor.submit(fetch_amazon_batch, batch, idx, total_batches))
            if AMAZON_REQUEST_DELAY_SECONDS > 0:
                time.sleep(AMAZON_REQUEST_DELAY_SECONDS)

        for future in as_completed(futures):
            try:
                items = future.result()
                for item in items:
                    all_items[item.asin] = item
            except Exception as exc:
                print(f"  Warning: Amazon batch failed: {exc}")
    return all_items


def get_keepa_stats(asins):
    print("Fetching Keepa stats for same deal-style qualification...")
    try:
        api = keepa.Keepa(KEEPA_API_KEY)
        products = api.query(asins, domain="US", stats=30, history=False, wait=True)
    except Exception as exc:
        print(f"Warning: Keepa stats query failed: {exc}")
        return {}
    return {p.get("asin"): p for p in products if p and p.get("asin")}


def cents_to_dollars(value):
    if value is None or value in (-1, 0):
        return None
    try:
        return round(float(value) / 100.0, 2)
    except Exception:
        return None


def stat_price(product, stat_name, price_index=0):
    try:
        stats = product.get("stats", {})
        value = stats.get(stat_name)
        if isinstance(value, list) and len(value) > price_index:
            return cents_to_dollars(value[price_index])
    except Exception:
        pass
    return None


def amazon_item_to_deal(asin, item, watch_meta, state_entry, keepa_product, min_drop_percent):
    try:
        title = item.item_info.title.display_value
    except Exception:
        title = None
    if is_bad_title(title):
        return None, state_entry

    try:
        listing = item.offers_v2.listings[0]
        price_amount = float(listing.price.money.amount)
        price_display = listing.price.money.display_amount
        currency = listing.price.money.currency
    except Exception:
        return None, state_entry

    try:
        condition = listing.condition.value
        if condition and condition.lower() != "new":
            return None, state_entry
    except Exception:
        pass

    try:
        brand = item.item_info.by_line_info.brand.display_value
    except Exception:
        brand = None

    try:
        raw_category = item.item_info.classifications.product_group.display_value
    except Exception:
        raw_category = None

    image = product_image(item, state_entry.get("image"))

    try:
        url = item.detail_page_url
    except Exception:
        url = f"https://www.amazon.com/dp/{asin}?tag={PARTNER_TAG}"

    try:
        availability = listing.availability.type
    except Exception:
        availability = None
    if str(availability or "").upper() == "UNAVAILABLE":
        return None, state_entry

    previous_price = state_entry.get("lastPrice")
    avg30 = stat_price(keepa_product, "avg30") if keepa_product else None
    avg7 = stat_price(keepa_product, "avg") if keepa_product else None
    min7 = stat_price(keepa_product, "minInInterval") if keepa_product else None

    drops = []
    pct_from_previous = 0
    pct_from_avg30 = 0

    if previous_price and previous_price > price_amount:
        pct_from_previous = round(((previous_price - price_amount) / previous_price) * 100)
        if pct_from_previous >= min_drop_percent:
            drops.append("saved_price_drop")

    if avg30 and avg30 > price_amount:
        pct_from_avg30 = round(((avg30 - price_amount) / avg30) * 100)
        if pct_from_avg30 >= min_drop_percent:
            drops.append("keepa_30_day_avg_drop")

    pct_from_avg7 = 0
    if avg7 and avg7 > price_amount:
        pct_from_avg7 = round(((avg7 - price_amount) / avg7) * 100)
        if pct_from_avg7 >= min_drop_percent:
            drops.append("keepa_7_day_avg_drop")

    savings_pct = 0
    was_display = None
    try:
        savings = listing.price.savings
        if savings:
            savings_pct = int(round(savings.percentage or 0))
            was_display = f"${round(price_amount + float(savings.money.amount), 2)}"
            if savings_pct >= min_drop_percent and drops:
                drops.append("amazon_savings_drop")
    except Exception:
        pass

    qualifies = bool(drops)
    pct_off = max(pct_from_previous, pct_from_avg30, pct_from_avg7)
    now_iso = iso_now()
    expires_at = (utc_now() + timedelta(hours=23)).isoformat()

    new_state = dict(state_entry or {})
    if not new_state.get("firstSeenAt"):
        new_state["firstSeenAt"] = iso_now()
    new_state["lastCheckedAt"] = iso_now()
    new_state["lastPrice"] = price_amount
    new_state["lastPriceDisplay"] = price_display
    new_state["lowestSeenPrice"] = min(price_amount, new_state.get("lowestSeenPrice", price_amount) or price_amount)
    new_state["highestSeenPrice"] = max(price_amount, new_state.get("highestSeenPrice", price_amount) or price_amount)
    new_state["title"] = title
    if image:
        new_state["image"] = image

    if not qualifies:
        return None, new_state

    primary_category = watch_meta.get("categories", [{}])[0]
    deal = {
        "asin": asin,
        "title": title,
        "brand": brand,
        "cat": primary_category.get("name") or raw_category or "Best Sellers",
        "image": image,
        "image_candidates": [image] if image else [],
        "current_price": price_amount,
        "avg_7_price": avg7 or previous_price or price_amount,
        "min_7_price": min7 or price_amount,
        "avg_30_price": avg30 or previous_price or price_amount,
        "min_30_price": None,
        "drop_percent": pct_from_avg7 or pct_from_previous or pct_from_avg30,
        "drop_30_percent": pct_from_avg30,
        "price": price_display,
        "price_amount": price_amount,
        "currency": currency,
        "availability": availability,
        "amazon_url": url,
        "link": url,
        "desc": brand or "Best seller product pick",
        "posted_at": new_state.get("dealSeenAt", now_iso),
        "first_seen_at": new_state.get("dealSeenAt", now_iso),
        "checked_at": now_iso,
        "last_checked_at": now_iso,
        "expires_at": expires_at,
        "seen_at": new_state.get("dealSeenAt", now_iso),
        "updated_at": now_iso,
        "qualification_reasons": drops,
    }
    new_state["dealSeenAt"] = new_state.get("dealSeenAt", now_iso)
    return deal, new_state


def purge_old_deals(deals, ttl_hours):
    cutoff = utc_now() - timedelta(hours=ttl_hours)
    kept = []
    for deal in deals:
        updated = parse_time(deal.get("updated_at") or deal.get("seen_at"))
        current = float_or_none(deal.get("current_price"))
        avg7 = float_or_none(deal.get("avg_7_price"))
        avg30 = float_or_none(deal.get("avg_30_price"))
        has_history_drop = (
            current is not None and (
                (avg7 is not None and avg7 > current) or
                (avg30 is not None and avg30 > current)
            )
        )
        if updated and updated >= cutoff and has_history_drop:
            kept.append(deal)
    return kept


def main():
    if not KEEPA_API_KEY:
        raise RuntimeError("Missing KEEPA_API_KEY")

    config = load_config()
    refresh_hours = int(config.get("refreshBestSellerListHours", 168))
    refresh_watchlist = env_bool("BEST_SELLER_REFRESH_WATCHLIST", False)
    watchlist_only = env_bool("BEST_SELLER_WATCHLIST_ONLY", False)

    watchlist = load_json(WATCHLIST_FILE, {})
    has_saved_watchlist = bool(watchlist.get("items"))
    should_refresh = refresh_watchlist and refresh_needed(watchlist, refresh_hours)

    if not has_saved_watchlist or should_refresh:
        watchlist = build_watchlist(config)
    elif refresh_needed(watchlist, refresh_hours):
        print("Saved best-seller watchlist is stale, but this run is configured to use the saved list.")
        print("Run the weekly refresh workflow to rebuild best_seller_watchlist.json.")

    if watchlist_only:
        print("Watchlist-only mode complete; skipping deal checks.")
        return

    if not CREDENTIAL_ID or not CREDENTIAL_SECRET:
        raise RuntimeError("Missing CREATORS_CREDENTIAL_ID or CREATORS_CREDENTIAL_SECRET")

    asins_per_run = int(os.getenv("BEST_SELLER_ASINS_PER_RUN", config.get("asinsPerRun", 125)))
    min_drop_percent = int(config.get("minDropPercent", 10))
    deal_ttl_hours = min(int(config.get("dealTtlHours", 23)), 23)

    items = watchlist.get("items", [])
    if not items:
        print("No watchlist items available yet.")
        save_json(DEALS_FILE, {"deals": [], "count": 0, "updatedAt": iso_now()})
        return

    state = load_json(STATE_FILE, {"cursor": 0, "asins": {}})
    cursor = int(state.get("cursor", 0))
    batch_meta = []
    for i in range(asins_per_run):
        idx = (cursor + i) % len(items)
        batch_meta.append(items[idx])
    next_cursor = (cursor + asins_per_run) % len(items)
    batch_asins = [item["asin"] for item in batch_meta]

    print(f"Checking {len(batch_asins)} ASINs. Cursor {cursor} -> {next_cursor} of {len(items)}.")

    amazon_items = get_amazon_items(batch_asins)
    keepa_stats = get_keepa_stats(batch_asins)

    existing_output = load_json(DEALS_FILE, {"deals": []})
    deals_by_asin = {d.get("asin"): d for d in purge_old_deals(existing_output.get("deals", []), deal_ttl_hours)}

    state_asins = state.setdefault("asins", {})

    for meta in batch_meta:
        asin = meta["asin"]
        item = amazon_items.get(asin)
        if not item:
            continue
        deal, new_state = amazon_item_to_deal(
            asin=asin,
            item=item,
            watch_meta=meta,
            state_entry=state_asins.get(asin, {}),
            keepa_product=keepa_stats.get(asin),
            min_drop_percent=min_drop_percent,
        )
        state_asins[asin] = new_state
        if deal:
            deals_by_asin[asin] = deal

    state["cursor"] = next_cursor
    state["lastRunAt"] = iso_now()
    state["watchlistCount"] = len(items)
    save_json(STATE_FILE, state)

    all_deals = [
        public_product(deal)
        for deal in sorted(deals_by_asin.values(), key=lambda d: d.get("updated_at", ""), reverse=True)
    ]
    output = {
        "pageTitle": "Amazon Best Seller Product Picks",
        "pageDescription": "Current product picks from popular Amazon categories.",
        "source": "Amazon Creators API",
        "count": len(all_deals),
        "deal_count": len(all_deals),
        "totalProducts": len(all_deals),
        "updatedAt": iso_now(),
        "updated_at": iso_now(),
        "deal_ttl_hours": deal_ttl_hours,
        "deals": all_deals,
    }
    save_json(DEALS_FILE, output)
    print(f"Saved {len(all_deals)} best-seller deals to {DEALS_FILE}")


if __name__ == "__main__":
    main()
