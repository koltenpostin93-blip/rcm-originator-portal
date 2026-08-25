"""Scraper for RCM Co-op's live cash bids (rcmcoop.com).

RCM's site is powered by the same Barchart/AgriCharts cash-bids widget used
elsewhere in JSA's tooling (see basis-tracker-streamlit/agricharts_scraper.py).
Their own domain exposes the underlying JSON feed directly at
`/inc/cashbids/cashbids-js.php`, grouped by "board" (a board can cover more
than one physical elevator).

Board -> elevator mapping was confirmed by reading the `l=<id>` cash-chart
link embedded on each elevator's own page at rcmcoop.com. Note: Richland,
Pleasant Plains, and Ashland all currently link to the Culver/Burtonview
board (12023) rather than the "RPA" board (4453) that also exists in the
feed — that looks like a stale link on RCM's own site (RPA = Richland/
Pleasant Plains/Ashland by name and shares its city). Flagged in the mapping
below; confirm with RCM if the RPA board should be used instead.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import requests

FEED_URL = "https://www.rcmcoop.com/inc/cashbids/cashbids-js.php"
_QS = ("?filter=all&location=&commodity=&groupby=location&format=table"
       "&fields=name,delivery_start,delivery_end,basismonth,futures,futureschange,basis,price"
       "&bidsort=commodity&dateformat=%25m/%25d/%25Y&months=11")
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JPSI basis tracker; kpostin@jpsi.com)",
            "Accept": "text/javascript, */*"}
_BIDS_RE = re.compile(r"var bids\s*=\s*(\[.*?\]);", re.DOTALL)

# feed board id -> list of elevator names on the /locations page that link to it.
BOARD_TO_ELEVATORS = {
    "12023": ["Culver", "Barr", "Sweetwater", "Williamsville", "Burtonview",
              "Pleasant Plains", "Richland", "Ashland"],
    "12024": ["Mechanicsburg", "Edinburg", "Dawson"],
    "76126": ["Riverton"],
    # No elevator page currently links here; kept for visibility only.
    "4453": [],
}


def fetch_rcm_boards() -> list[dict]:
    """Return each board's raw feed dict: {id, name, city, state, cashbids: [...]}"""
    r = requests.get(FEED_URL + _QS, headers=_HEADERS, timeout=30)
    r.raise_for_status()
    m = _BIDS_RE.search(r.text)
    if not m:
        return []
    return json.loads(m.group(1))


def parsed_bids_by_board() -> dict[str, list[dict]]:
    """board id -> list of {commodity, basis, futures_month, cash_price, delivery_start, delivery_end}"""
    out: dict[str, list[dict]] = {}
    for board in fetch_rcm_boards():
        board_id = str(board.get("id") or "")
        rows = []
        for b in board.get("cashbids") or []:
            price_str = (b.get("cashpricebushel") or b.get("price") or "").replace("$", "").strip()
            try:
                cash_price = float(price_str) if price_str else None
            except ValueError:
                cash_price = None
            basis = b.get("basis")
            # The feed gives the final cash price and the basis (cents/bu); back out the
            # flat futures price in $/bu rather than parsing CBOT points notation ("493-2").
            futures_price = (cash_price - (basis or 0) / 100) if cash_price is not None else None
            delivery_start_raw = b.get("delivery_start_raw") or ""
            try:
                delivery_start = datetime.strptime(delivery_start_raw, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                delivery_start = None
            rows.append({
                "commodity": b.get("short_name") or b.get("name") or "",
                "basis": basis,
                "futures_month": b.get("basismonth") or "",
                "futures_price": futures_price,
                "cash_price": cash_price,
                "delivery_start": delivery_start,
                "delivery_end": b.get("delivery_end_raw") or b.get("delivery_end") or "",
            })
        # The feed occasionally lists more than one contract quote under the same
        # commodity+basismonth label (e.g. two symbols for one nominal window). Our
        # Bid table keys on (commodity, futures_month), so keep only the last one —
        # otherwise the upsert below inserts a duplicate instead of updating in place.
        deduped = {}
        for row in rows:
            deduped[(row["commodity"], row["futures_month"])] = row
        out[board_id] = list(deduped.values())
    return out


def refresh_bids_in_db():
    """Upsert scraper-sourced Bid rows for every Originator with a feed_location_id.

    Returns (updated_count, skipped_boards) for reporting in the UI.
    """
    import datetime as _dt

    from db import Bid, Originator, get_session

    boards = parsed_bids_by_board()
    session = get_session()
    updated = 0
    try:
        originators = session.query(Originator).filter(Originator.feed_location_id.isnot(None)).all()
        for o in originators:
            rows = boards.get(o.feed_location_id, [])
            for row in rows:
                existing = (
                    session.query(Bid)
                    .filter(
                        Bid.originator_id == o.id,
                        Bid.source == "scraper",
                        Bid.commodity == row["commodity"],
                        Bid.futures_month == row["futures_month"],
                    )
                    .first()
                )
                bid_date = _dt.datetime.now(timezone.utc).replace(tzinfo=None)
                if existing:
                    existing.basis = row["basis"]
                    existing.futures_price = row["futures_price"]
                    existing.cash_price = row["cash_price"]
                    existing.delivery_start = row["delivery_start"]
                    existing.bid_date = bid_date
                else:
                    session.add(
                        Bid(
                            originator_id=o.id,
                            commodity=row["commodity"],
                            location=o.company_name,
                            basis=row["basis"],
                            futures_month=row["futures_month"],
                            futures_price=row["futures_price"],
                            delivery_start=row["delivery_start"],
                            cash_price=row["cash_price"],
                            bid_date=bid_date,
                            source="scraper",
                            notes="Auto-imported from RCM Co-op cash bids feed",
                        )
                    )
                updated += 1
        session.commit()
    finally:
        session.close()
    return updated


if __name__ == "__main__":
    count = refresh_bids_in_db()
    print(f"Updated/inserted {count} scraped bid rows.")
