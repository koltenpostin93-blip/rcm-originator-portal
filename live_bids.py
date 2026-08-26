"""Cached, page-facing access to RCM's live cash bids.

Bid history isn't tracked — every page just asks for the current feed. The
short TTL keeps repeated widget interactions on the same page from re-hitting
rcmcoop.com on every rerun, while still staying close to real-time.
"""
import streamlit as st

from rcm_scraper import parsed_bids_by_board


@st.cache_data(ttl=120, show_spinner="Fetching live RCM Co-op cash bids...")
def get_boards() -> dict[str, list[dict]]:
    """board id -> list of {commodity, basis, futures_month, futures_price, cash_price, ...}"""
    try:
        return parsed_bids_by_board()
    except Exception:
        return {}


def get_bids_for_location(feed_location_id: str | None, commodity: str | None = None) -> list[dict]:
    """Bids for one location's board, optionally filtered to one commodity."""
    if not feed_location_id:
        return []
    rows = get_boards().get(feed_location_id, [])
    if commodity:
        rows = [r for r in rows if r["commodity"] == commodity]
    return sorted(rows, key=lambda r: r["delivery_start"] or "")
