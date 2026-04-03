"""
MTG card price fetcher using Scryfall API (https://scryfall.com/docs/api)
Free, public, no authentication required.
Rate limit: 50-100ms between requests recommended by Scryfall.
"""
import time
import requests

BASE_URL = "https://api.scryfall.com"
HEADERS = {
    "User-Agent": "CardPriceScraper/1.0 (personal use)",
    "Accept": "application/json",
}


def search_cards(query: str) -> list[dict]:
    """
    Search MTG cards by name using Scryfall fuzzy/full-text search.
    Returns list of card dicts with price data.
    """
    params = {
        "q": query,
        "unique": "prints",  # Show all printings for price comparison
    }

    try:
        resp = requests.get(f"{BASE_URL}/cards/search", headers=HEADERS, params=params, timeout=15)

        if resp.status_code == 404:
            return []

        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Scryfall API error: {e}")

    results = []
    for card in data.get("data", []):
        results.append(_parse_card(card))

    # Handle multi-page results (fetch first 2 pages max to avoid hammering)
    page = 2
    while data.get("has_more") and page <= 2:
        time.sleep(0.1)
        next_page = data.get("next_page", "")
        if not next_page:
            break
        try:
            resp = requests.get(next_page, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for card in data.get("data", []):
                results.append(_parse_card(card))
        except requests.RequestException:
            break
        page += 1

    # Polite delay per Scryfall guidelines
    time.sleep(0.1)
    return results


def get_card_by_name(name: str) -> dict | None:
    """
    Get a single card by exact/fuzzy name match.
    Uses Scryfall's /cards/named endpoint.
    """
    params = {"fuzzy": name}
    try:
        resp = requests.get(f"{BASE_URL}/cards/named", headers=HEADERS, params=params, timeout=15)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        time.sleep(0.1)
        return _parse_card(resp.json())
    except requests.RequestException as e:
        raise RuntimeError(f"Scryfall API error: {e}")


def _parse_card(card: dict) -> dict:
    prices = card.get("prices", {})
    return {
        "game": "MTG",
        "id": card.get("id", ""),
        "name": card.get("name", ""),
        "set": card.get("set_name", ""),
        "number": card.get("collector_number", ""),
        "rarity": card.get("rarity", ""),
        "price_type": "tcgplayer",
        "price_market_usd": _safe_float(prices.get("usd")),
        "price_low_usd": _safe_float(prices.get("usd_foil")),   # foil as secondary
        "price_mid_usd": None,
        "price_high_usd": None,
        "price_eur": _safe_float(prices.get("eur")),
        "source_url": card.get("scryfall_uri", ""),
        "currency": "USD/EUR",
    }


def _safe_float(val) -> float | None:
    try:
        return float(val) if val is not None else None
    except (ValueError, TypeError):
        return None
