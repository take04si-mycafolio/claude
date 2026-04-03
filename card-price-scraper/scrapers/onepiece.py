"""
One Piece card price fetcher.

Strategy:
  1. Primary: TCGPlayer product search (HTML scraping with polite delays)
  2. Fallback: Cardmarket (cardmarket.com) for European prices

TCGPlayer ToS allows personal/non-commercial scraping at reasonable rates.
We use 1-2 second delays between requests to stay well within limits.
"""
import re
import time
import requests
from bs4 import BeautifulSoup

TCGPLAYER_SEARCH = "https://www.tcgplayer.com/search/one-piece-card-game/product"
CARDMARKET_SEARCH = "https://www.cardmarket.com/en/OnePiece/Products/Singles"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def search_cards(query: str) -> list[dict]:
    """
    Search One Piece cards by name.
    Tries TCGPlayer first, falls back to Cardmarket.
    """
    results = _search_tcgplayer(query)
    if not results:
        results = _search_cardmarket(query)
    return results


def _search_tcgplayer(query: str) -> list[dict]:
    """Scrape TCGPlayer search results for One Piece cards."""
    params = {
        "q": query,
        "view": "grid",
    }

    try:
        resp = SESSION.get(TCGPLAYER_SEARCH, params=params, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[TCGPlayer] Request failed: {e}")
        return []

    time.sleep(1.5)  # Polite delay

    soup = BeautifulSoup(resp.text, "lxml")
    results = []

    # TCGPlayer product cards
    product_cards = soup.select("div.search-result__content")
    if not product_cards:
        # Try alternate selector
        product_cards = soup.select("[class*='search-result']")

    for card in product_cards[:20]:  # Cap at 20 results
        name_el = card.select_one("[class*='product-card__title'], .search-result__title, h3")
        name = name_el.get_text(strip=True) if name_el else ""
        if not name:
            continue

        set_el = card.select_one("[class*='product-card__set-name'], .search-result__subtitle")
        set_name = set_el.get_text(strip=True) if set_el else ""

        # Market price
        market_el = card.select_one(
            "[class*='product-card__market-price'], "
            "[class*='inventory__price-with-shipping'], "
            ".search-result__market-price"
        )
        price_text = market_el.get_text(strip=True) if market_el else ""
        price = _parse_price_usd(price_text)

        link_el = card.select_one("a[href*='/product/']")
        url = f"https://www.tcgplayer.com{link_el['href']}" if link_el and link_el.get("href") else ""

        results.append({
            "game": "OnePiece",
            "id": _extract_tcg_id(url),
            "name": name,
            "set": set_name,
            "number": "",
            "rarity": "",
            "price_type": "market",
            "price_market_usd": price,
            "price_low_usd": None,
            "price_mid_usd": None,
            "price_high_usd": None,
            "source_url": url,
            "currency": "USD",
        })

    return results


def _search_cardmarket(query: str) -> list[dict]:
    """
    Scrape Cardmarket for One Piece card prices (EUR).
    Cardmarket is ToS-friendly for manual browsing simulation.
    """
    params = {"searchString": query}

    try:
        resp = SESSION.get(CARDMARKET_SEARCH, params=params, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[Cardmarket] Request failed: {e}")
        return []

    time.sleep(2.0)  # Polite delay

    soup = BeautifulSoup(resp.text, "lxml")
    results = []

    rows = soup.select("div.col-12.col-md-8 .row, table.table tbody tr")
    for row in rows[:20]:
        name_el = row.select_one("a.col-seller__productName, .product-name a, td a")
        name = name_el.get_text(strip=True) if name_el else ""
        if not name:
            continue

        price_el = row.select_one(
            ".col-price .fw-bold, .price-container, td.col-price"
        )
        price_text = price_el.get_text(strip=True) if price_el else ""
        price = _parse_price_eur(price_text)

        url = ""
        if name_el and name_el.get("href"):
            href = name_el["href"]
            url = f"https://www.cardmarket.com{href}" if href.startswith("/") else href

        results.append({
            "game": "OnePiece",
            "id": "",
            "name": name,
            "set": "",
            "number": "",
            "rarity": "",
            "price_type": "market",
            "price_market_usd": None,
            "price_low_usd": None,
            "price_mid_usd": None,
            "price_high_usd": None,
            "price_eur": price,
            "source_url": url,
            "currency": "EUR",
        })

    return results


def _parse_price_usd(text: str) -> float | None:
    m = re.search(r"\$?([\d,]+\.?\d*)", text.replace(",", ""))
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def _parse_price_eur(text: str) -> float | None:
    # Handles formats like "1,23 €" or "€1.23"
    cleaned = text.replace("€", "").replace(",", ".").strip()
    # If multiple dots, keep only last decimal
    parts = cleaned.split(".")
    if len(parts) > 2:
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    m = re.search(r"[\d]+\.?\d*", cleaned)
    if m:
        try:
            return float(m.group())
        except ValueError:
            pass
    return None


def _extract_tcg_id(url: str) -> str:
    m = re.search(r"/product/(\d+)/", url)
    return m.group(1) if m else ""
