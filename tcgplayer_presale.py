"""
tcgplayer_presale.py
--------------------
Searches TCGPlayer for presale sealed product listings priced above MIN_PRICE.
Cases are excluded. Results are sorted highest market price first.

Outputs:
  - docs/data/results.json   (read by GitHub Pages site)
  - stdout summary

Uses TCGPlayer's internal search API (no API key required):
  POST https://mp-search-api.tcgplayer.com/v1/search/request
"""

import json
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from fake_useragent import UserAgent

# ─── CONFIG ─────────────────────────────────────────────────────────────────
SEARCH_QUERY     = "booster box"
MIN_PRICE        = 150.0        # market price threshold
PAGE_SIZE        = 24           # max TCGPlayer allows per request
MAX_PAGES        = 200          # safety cap; auto-stops when all pages fetched

EXCLUDE_KEYWORDS = ["case"]     # skip any listing whose name contains these
# At least one of these must appear in the product name (prevents false positives
# like prerelease packs, commander decks, bundles, etc.)
REQUIRE_KEYWORDS = ["booster"]

OUTPUT_PATH      = Path("docs/data/results.json")
# ────────────────────────────────────────────────────────────────────────────

API_URL = "https://mp-search-api.tcgplayer.com/v1/search/request"
TODAY   = datetime.now(timezone.utc)

ua = UserAgent()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "User-Agent":      ua.random,
        "Content-Type":    "application/json",
        "Accept":          "application/json, text/plain, */*",
        "Origin":          "https://www.tcgplayer.com",
        "Referer":         "https://www.tcgplayer.com/",
        "Accept-Language": "en-US,en;q=0.9",
    }


def _build_payload(offset: int) -> dict:
    return {
        "from":  offset,
        "size":  PAGE_SIZE,
        "query": SEARCH_QUERY,
        "filters": {
            "term":  {"sealed": ["true"]},
            "range": {"marketPrice": {"gte": MIN_PRICE}},
        },
    }


def _is_presale(product: dict) -> bool:
    """True only when the product's release date is still in the future."""
    attrs       = product.get("customAttributes") or {}
    release_str = attrs.get("releaseDate")
    if not release_str:
        return False
    try:
        release_dt = datetime.fromisoformat(release_str.replace("Z", "+00:00"))
        return release_dt > TODAY
    except ValueError:
        return False


def _is_excluded(name: str) -> bool:
    name_lower = name.lower()
    return any(kw in name_lower for kw in EXCLUDE_KEYWORDS)


def _is_required(name: str) -> bool:
    """Return True only if the name contains at least one required keyword."""
    name_lower = name.lower()
    return any(kw in name_lower for kw in REQUIRE_KEYWORDS)


def _image_url(product_id: int) -> str:
    """TCGPlayer CDN image URL for a product."""
    return f"https://tcgplayer-cdn.tcgplayer.com/product/{product_id}_200w.jpg"


def _product_url(product: dict) -> str:
    pid  = int(product.get("productId", 0))
    slug = product.get("productUrlName", "")
    if pid and slug:
        slug = slug.replace(" ", "-").lower()
        return f"https://www.tcgplayer.com/product/{pid}/{slug}"
    return "https://www.tcgplayer.com"


# ── Fetching ─────────────────────────────────────────────────────────────────

def fetch_all_products() -> list[dict]:
    session     = requests.Session()
    all_products: list[dict] = []
    offset      = 0

    print(f"Fetching presale listings (market price ≥ ${MIN_PRICE:.0f}) from TCGPlayer…\n")

    for page in range(1, MAX_PAGES + 1):
        time.sleep(random.uniform(0.5, 1.2))
        payload = _build_payload(offset)

        try:
            resp = session.post(API_URL, headers=_headers(), json=payload, timeout=20)
        except Exception as exc:
            print(f"  [page {page}] Request error: {exc}")
            break

        if resp.status_code != 200:
            print(f"  [page {page}] HTTP {resp.status_code} — stopping.")
            break

        data         = resp.json()
        group        = (data.get("results") or [{}])[0]
        products     = group.get("results") or []
        total        = int(group.get("totalResults") or 0)
        pages_needed = (total + PAGE_SIZE - 1) // PAGE_SIZE

        print(f"  Page {page:>3}/{pages_needed} — {len(products)} products  (total: {total})", end="", flush=True)

        if not products:
            print()
            break

        all_products.extend(products)
        offset += PAGE_SIZE

        presale_so_far = sum(1 for p in all_products if _is_presale(p))
        print(f"  [presale found: {presale_so_far}]", flush=True)

        if offset >= total:
            print("  All pages fetched.")
            break

    return all_products


# ── Filtering ─────────────────────────────────────────────────────────────────

def filter_results(products: list[dict]) -> list[dict]:
    """Keep presale, non-excluded items above MIN_PRICE. Deduplicate by productId."""
    kept:     list[dict] = []
    seen_ids: set[int]   = set()

    for p in products:
        name = p.get("productName") or ""
        pid  = int(p.get("productId") or 0)

        if pid and pid in seen_ids:
            continue
        if not _is_required(name):
            continue
        if _is_excluded(name):
            continue
        if not _is_presale(p):
            continue

        market = p.get("marketPrice")
        lowest = p.get("lowestPrice")

        # Primary sort/threshold key is market price
        price = market or lowest
        if price is None:
            continue
        try:
            price = float(price)
        except (TypeError, ValueError):
            continue

        if price < MIN_PRICE:
            continue

        if pid:
            seen_ids.add(pid)

        attrs = p.get("customAttributes") or {}

        kept.append({
            "id":           pid,
            "name":         name,
            "product_line": p.get("productLineName") or "—",
            "set":          p.get("setName")         or "—",
            "release_date": attrs.get("releaseDate", "")[:10],
            "market_price": round(float(market), 2) if market else None,
            "lowest_price": round(float(lowest), 2) if lowest else None,
            "image_url":    _image_url(pid) if pid else "",
            "url":          _product_url(p),
        })

    return sorted(kept, key=lambda x: (x["market_price"] or 0), reverse=True)


# ── Output ────────────────────────────────────────────────────────────────────

def save_json(results: list[dict]):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": TODAY.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count":        len(results),
        "items":        results,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"\n  Saved {len(results)} items → {OUTPUT_PATH}")


def display(results: list[dict]):
    if not results:
        print("\n  No presale items found above the price threshold.\n")
        return

    col_w = 52
    print()
    print("─" * 78)
    print(f"  {'PRESALE BOOSTER BOXES (>$' + str(int(MIN_PRICE)) + ')':<{col_w}}  {'MKT $':>8}  {'LOW $':>8}")
    print("─" * 78)

    for item in results:
        name_line = item["name"]
        if len(name_line) > col_w:
            name_line = name_line[:col_w - 1] + "…"
        mkt = f"{item['market_price']:.2f}" if item["market_price"] else "  —  "
        low = f"{item['lowest_price']:.2f}"  if item["lowest_price"] else "  —  "
        print(f"  {name_line:<{col_w}}  ${mkt:>7}  ${low:>7}")
        print(f"  {'':4}{item['product_line']} · {item['set']} · Releases {item['release_date'] or 'TBA'}")
        print(f"  {'':4}{item['url']}")
        print()

    print("─" * 78)
    print(f"  {len(results)} item(s) found\n")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    raw      = fetch_all_products()
    filtered = filter_results(raw)
    display(filtered)
    save_json(filtered)
