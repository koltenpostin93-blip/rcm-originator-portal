"""Seed the 12 RCM Co-op elevator locations from rcmcoop.com/locations.

Each is tagged with the feed_location_id of the Barchart/AgriCharts cash-bids
board that covers it (see rcm_scraper.py for how that mapping was derived).
Safe to re-run: existing rows are matched by company_name and updated in place.

Usage:
    python seed_locations.py
"""
from db import Originator, get_session, init_db

LOCATIONS = [
    dict(company_name="Culver Elevator", phone="217-636-7171",
         street="26352 Quarry Ave.", city="Athens", state="IL",
         commodities="Corn, Soybeans", feed_location_id="12023"),
    dict(company_name="Barr Elevator", phone="217-636-7184",
         street="2175 W State Route 29", city="Athens", state="IL",
         commodities="Corn, Soybeans", feed_location_id="12023"),
    dict(company_name="Sweetwater Elevator", phone="217-968-2211",
         street="20341 Engel St.", city="Greenview", state="IL",
         commodities="Corn, Soybeans", feed_location_id="12023"),
    dict(company_name="Williamsville Elevator", phone="217-566-3321",
         street="201 W. Jones", city="Williamsville", state="IL",
         commodities="Corn, Soybeans", feed_location_id="12023"),
    dict(company_name="Mechanicsburg Elevator", phone="217-364-4438",
         street="305 North 1st", city="Mechanicsburg", state="IL",
         commodities="Corn, Soybeans", feed_location_id="12024"),
    dict(company_name="Riverton", phone="217-629-5971",
         street="8233 Sherman Rd", city="Riverton", state="IL",
         commodities="Corn, Soybeans", feed_location_id="76126"),
    dict(company_name="Edinburg Elevator", phone="217-364-4439",
         street="208 North Grant", city="Edinburg", state="IL",
         commodities="Corn, Soybeans", feed_location_id="12024"),
    dict(company_name="Dawson Elevator", phone="217-364-4621",
         street="200 East Main", city="Dawson", state="IL",
         commodities="Corn, Soybeans", feed_location_id="12024"),
    dict(company_name="Pleasant Plains Elevator", phone="217-626-1331",
         street="300 N Washington St", city="Pleasant Plains", state="IL",
         commodities="Corn, Soybeans", feed_location_id="12023"),
    dict(company_name="Richland Elevator", phone="217-626-1551",
         street="3090 Richland Elevator Rd", city="Pleasant Plains", state="IL",
         commodities="Corn, Soybeans", feed_location_id="12023"),
    dict(company_name="Ashland Elevator", phone="217-626-4204",
         street="220 North Niagara St.", city="Ashland", state="IL",
         commodities="Corn, Soybeans", feed_location_id="12023"),
    dict(company_name="Burtonview Elevator", phone="217-735-1575",
         street="601 State Route 10B", city="Lincoln", state="IL",
         commodities="Corn, Soybeans", feed_location_id="12023"),
]


def seed_locations(session) -> int:
    """Upsert the 12 RCM Co-op locations using the given session (caller commits/closes)."""
    for loc in LOCATIONS:
        existing = session.query(Originator).filter(Originator.company_name == loc["company_name"]).first()
        if existing:
            existing.phone = loc["phone"]
            existing.city = loc["city"]
            existing.state = loc["state"]
            existing.commodities = loc["commodities"]
            existing.feed_location_id = loc["feed_location_id"]
            existing.notes = loc["street"]
        else:
            session.add(
                Originator(
                    company_name=loc["company_name"],
                    phone=loc["phone"],
                    city=loc["city"],
                    state=loc["state"],
                    commodities=loc["commodities"],
                    feed_location_id=loc["feed_location_id"],
                    notes=loc["street"],
                )
            )
    return len(LOCATIONS)


def main():
    init_db()
    session = get_session()
    try:
        count = seed_locations(session)
        session.commit()
        print(f"Seeded/updated {count} RCM Co-op locations.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
