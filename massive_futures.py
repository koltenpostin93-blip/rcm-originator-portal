"""Live futures prices from the Massive.com Futures REST API (api.massive.com).

Used only when a user overrides the futures month on a Purchase to something
RCM's own board doesn't quote — this looks up the real CME/CBOT price for
that specific contract instead of requiring a manually typed price.
"""
import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://api.massive.com/futures/v1"

ROOT_SYMBOL = {"Corn": "ZC", "Soybeans": "ZS", "Wheat": "ZW"}

# CBOT month codes, standard futures letter per calendar month.
_MONTH_CODE = {1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
               7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z"}
_MONTH_NAME = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
               7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"}

# Which months actually trade for each commodity (standard CBOT ag contract cycle).
CONTRACT_MONTHS = {
    "Corn": [3, 5, 7, 9, 12],
    "Soybeans": [1, 3, 5, 7, 8, 9, 11],
    "Wheat": [3, 5, 7, 9, 12],
}


def month_options(commodity: str) -> list[tuple[int, str]]:
    """[(month_number, month_name), ...] for the months that actually trade."""
    return [(m, _MONTH_NAME[m]) for m in CONTRACT_MONTHS.get(commodity, [])]


def build_ticker(commodity: str, month: int, year: int) -> str | None:
    root = ROOT_SYMBOL.get(commodity)
    if not root:
        return None
    return f"{root}{_MONTH_CODE[month]}{year % 10}"


def _api_key() -> str | None:
    """Local dev reads MASSIVE_API_KEY from .env; Streamlit Cloud exposes the
    same key via st.secrets instead (see db.py's _database_url for the same
    pattern, including why the st.secrets branch is safe to attempt even
    outside a running Streamlit app)."""
    env_value = os.getenv("MASSIVE_API_KEY")
    if env_value:
        return env_value
    try:
        return st.secrets["MASSIVE_API_KEY"]
    except Exception:
        return None


@st.cache_data(ttl=60, show_spinner="Looking up live futures price...")
def get_futures_price(commodity: str, month: int, year: int) -> dict | None:
    """Returns {"ticker", "price", "bid", "ask"} in $/bu, or None if unavailable."""
    ticker = build_ticker(commodity, month, year)
    if not ticker:
        return None
    api_key = _api_key()
    if not api_key:
        return None
    try:
        r = requests.get(
            f"{API_BASE}/quotes/{ticker}",
            params={"limit": 1},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        r.raise_for_status()
        results = r.json().get("results") or []
        if not results:
            return None
        bid = results[0].get("bid_price")
        ask = results[0].get("ask_price")
        if bid is None or ask is None:
            return None
        mid_cents = (bid + ask) / 2
        return {"ticker": ticker, "price": mid_cents / 100, "bid": bid / 100, "ask": ask / 100}
    except Exception:
        return None
