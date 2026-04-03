"""
Pokemon card price fetcher using the Pokemon TCG API (api.pokemontcg.io)
Free to use. API key optional but increases rate limits.
"""
import time
import requests

BASE_URL = "https://api.pokemontcg.io/v2"
HEADERS = {
    "User-Agent": "CardPriceScraper/1.0 (personal use)",
}


def search_cards(query: str, api_key: str = "") -> list[dict]:
    """
    Search Pokemon cards by name.
    Returns list of card dicts with price data.
    """
    if api_key:
        HEADERS["X-Api-Key"] = api_key

    params = {
        "q": f'name:"{query}"',
        "select": "id,name,set,number,rarity,tcgplayer",
        "pageSize": 50,
    }

    try:
        resp = requests.get(f"{BASE_URL}/cards", headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Pokemon TCG API error: {e}")

    results = []
    for card in data.get("data", []):
        prices = _extract_prices(card)
        results.append({
            "game": "Pokemon",
            "id": card.get("id", ""),
            "name": card.get("name", ""),
            "set": card.get("set", {}).get("name", ""),
            "number": card.get("number", ""),
            "rarity": card.get("rarity", ""),
            **prices,
        })

    # Polite delay
    time.sleep(0.3)
    return results


def _extract_prices(card: dict) -> dict:
    tcgplayer = card.get("tcgplayer", {})
    prices_raw = tcgplayer.get("prices", {})

    # Priority order for price variants
    variants = ["holofoil", "reverseHolofoil", "normal", "1stEditionHolofoil", "1stEditionNormal"]

    market = None
    low = None
    mid = None
    high = None
    price_type = ""

    for variant in variants:
        if variant in prices_raw:
            p = prices_raw[variant]
            market = p.get("market")
            low = p.get("low")
            mid = p.get("mid")
            high = p.get("high")
            price_type = variant
            if market is not None:
                break

    return {
        "price_type": price_type,
        "price_market_usd": market,
        "price_low_usd": low,
        "price_mid_usd": mid,
        "price_high_usd": high,
        "source_url": tcgplayer.get("url", ""),
        "currency": "USD",
    }


def get_sets() -> list[dict]:
    """Return list of all Pokemon TCG sets."""
    try:
        resp = requests.get(f"{BASE_URL}/sets", headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json().get("data", [])
    except requests.RequestException as e:
        raise RuntimeError(f"Pokemon TCG API error: {e}")
