"""
collector.py — the FREE auto-pull for TikTok trends.

We use TikTok's *Creative Center*, a public marketing site that lists trending
hashtags. It has a behind-the-scenes web address (an "API") that returns the
list as data. No login or paid key.

HONEST CAVEAT: TikTok can change or lock this down at any time. So this code is
"best-effort": it TRIES, and if it can't get data it returns a clear status
message instead of crashing. The dashboard and the manual 'log a trend' form
keep working no matter what.
"""

import time
import xml.etree.ElementTree as ET

import requests

import db

# Words that mark a trend as clothing/fashion related, so they stand out.
FASHION_WORDS = (
    "fashion", "outfit", "dress", "jeans", "denim", "coat", "jacket", "shoe",
    "sneaker", "boot", "bag", "purse", "skirt", "top", "shirt", "hoodie",
    "leggings", "style", "wardrobe", "thrift", "vintage", "y2k", "aesthetic",
    "nike", "adidas", "zara", "shein", "uniqlo", "gucci", "prada", "trend",
    "mob wife", "coquette", "clean girl", "leopard", "fur", "knit", "cargo",
)


def looks_fashion(text):
    """True if the trend text mentions anything clothing/style related."""
    low = (text or "").lower()
    return any(w in low for w in FASHION_WORDS)

# The public Creative Center endpoint that powers their "Trending hashtags" page.
HASHTAG_URL = "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list"

# We pretend to be a normal browser. Creative Center checks for this.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en",
    "Origin": "https://ads.tiktok.com",
}


def fetch_tiktok_hashtags(country_code="US", period=7, limit=20):
    """
    Try to fetch trending hashtags from TikTok Creative Center.

    period: 7, 30, or 120 (days)
    Returns (rows_saved, status_message).
    """
    params = {
        "page": 1,
        "limit": limit,
        "period": period,
        "country_code": country_code,
        "sort_by": "popular",
    }

    try:
        resp = requests.get(HASHTAG_URL, params=params, headers=HEADERS, timeout=20)
    except Exception as e:
        return 0, f"Could not reach TikTok ({e.__class__.__name__}). Try again later."

    if resp.status_code != 200:
        return 0, (
            f"TikTok returned status {resp.status_code}. "
            "Their free endpoint may be temporarily blocking us — "
            "the manual 'log a trend' form still works."
        )

    try:
        data = resp.json()
    except Exception:
        return 0, "TikTok replied but not with readable data (likely a block page)."

    # The list lives at data["data"]["list"] when it works.
    items = (data or {}).get("data", {}).get("list")
    if not items:
        return 0, (
            "TikTok replied but sent no hashtag list — their endpoint likely "
            "changed or needs a token now. The manual form still works."
        )

    saved = 0
    for i, item in enumerate(items, start=1):
        name = item.get("hashtag_name") or item.get("hashtag") or ""
        if not name:
            continue
        if not name.startswith("#"):
            name = "#" + name
        publish_cnt = item.get("publish_cnt") or item.get("video_views")
        rank = item.get("rank") or i
        db.add_trend(
            source="tiktok",
            category="hashtag",
            name=name,
            detail=f"TikTok Creative Center — {country_code}, last {period}d",
            metric=publish_cnt,
            metric_label="videos",
            rank=rank,
            url=f"https://www.tiktok.com/tag/{name.lstrip('#')}",
        )
        saved += 1

    return saved, f"Saved {saved} trending TikTok hashtags ({country_code}, {period}d)."


# ----------------------------------------------------------------------------
# Google Trends — the RELIABLE free auto-engine (no key, no token).
# Returns the day's trending searches. We flag the clothing-related ones.
# ----------------------------------------------------------------------------
GOOGLE_RSS = "https://trends.google.com/trending/rss"
NS = {"ht": "https://trends.google.com/trending/rss"}


def fetch_google_trends(geo="US"):
    """Pull today's trending searches from Google Trends RSS. Returns (saved, msg)."""
    try:
        resp = requests.get(
            GOOGLE_RSS, params={"geo": geo},
            headers={"User-Agent": HEADERS["User-Agent"]}, timeout=20,
        )
    except Exception as e:
        return 0, f"Could not reach Google Trends ({e.__class__.__name__})."

    if resp.status_code != 200:
        return 0, f"Google Trends returned status {resp.status_code}."

    try:
        root = ET.fromstring(resp.text)
    except Exception:
        return 0, "Google Trends sent data we couldn't read."

    saved = 0
    for i, item in enumerate(root.iter("item"), start=1):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        traffic = item.findtext("ht:approx_traffic", default="", namespaces=NS).strip()
        # A linked news headline gives helpful context on WHY it's trending.
        news = item.find("ht:news_item", NS)
        note = ""
        if news is not None:
            note = (news.findtext("ht:news_item_title", default="", namespaces=NS) or "").strip()
        metric = None
        if traffic:
            # "2,000+" -> 2000
            digits = "".join(c for c in traffic if c.isdigit())
            metric = float(digits) if digits else None

        category = "clothes" if looks_fashion(title + " " + note) else "search"
        db.add_trend(
            source="google",
            category=category,
            name=title,
            detail=(f"[{geo}] " + note) if note else f"trending search ({geo})",
            metric=metric,
            metric_label="searches",
            rank=i,
            url=f"https://www.google.com/search?q={title.replace(' ', '+')}",
        )
        saved += 1
    return saved, f"Saved {saved} Google trending searches ({geo})."


def run_collection():
    """
    Called by the dashboard's 'Refresh' button.
    Runs every free source we have and reports what each one did.
    """
    db.init_db()
    messages = []
    total = 0

    # 1) Google Trends — reliable, gives data today.
    for geo in ("US", "GB"):
        saved, msg = fetch_google_trends(geo)
        total += saved
        messages.append(msg)
        time.sleep(1)

    # 2) TikTok Creative Center — best-effort; may be blocked.
    for country in ("US", "GB"):
        saved, msg = fetch_tiktok_hashtags(country_code=country, period=7)
        total += saved
        messages.append(msg)
        time.sleep(1)  # be polite, don't hammer their server

    return total, " | ".join(messages)


if __name__ == "__main__":
    # Lets you test the collector straight from the terminal:
    #   python3 collector.py
    total, msg = run_collection()
    print(f"Done. {total} rows saved.\n{msg}")
