import datetime

import pandas as pd
import streamlit as st

from auth import logout_button, require_login
from branding import LOGO_PATH, apply_logo
from db import Bid, Originator, get_session

st.set_page_config(page_title="Bids | RCM Originator Portal", page_icon=LOGO_PATH, layout="wide")
apply_logo()

user = require_login()
logout_button()

st.title("Bids")

session = get_session()
try:
    if user.role == "admin":
        originators = session.query(Originator).filter(Originator.active.is_(True)).order_by(Originator.company_name).all()
        options = {o.company_name: o.id for o in originators}
        choice = st.selectbox("Originator", ["All"] + list(options.keys()))
        target_originator_id = None if choice == "All" else options[choice]
    else:
        target_originator_id = user.originator_id

    with st.expander("Submit a new bid", expanded=(user.role != "admin")):
        with st.form("new_bid_form", clear_on_submit=True):
            commodity = st.selectbox("Commodity", ["Corn", "Soybeans", "Wheat", "Grain Sorghum", "Other"])
            location = st.text_input("Location")
            c1, c2, c3 = st.columns(3)
            basis = c1.number_input("Basis (cents, vs. futures)", value=0.0, step=0.25, format="%.2f")
            futures_month = c2.text_input("Futures month (e.g. Dec26)")
            cash_price = c3.number_input("Cash price ($/bu)", value=0.0, step=0.01, format="%.4f")
            bid_date = st.date_input("Bid date", value=datetime.date.today())
            notes = st.text_area("Notes", height=80)
            submitted = st.form_submit_button("Submit bid")

            if submitted:
                originator_id = user.originator_id if user.role != "admin" else target_originator_id
                if not originator_id:
                    st.error("Select an originator before submitting a bid.")
                else:
                    bid = Bid(
                        originator_id=originator_id,
                        commodity=commodity,
                        location=location,
                        basis=basis,
                        futures_month=futures_month,
                        cash_price=cash_price,
                        bid_date=datetime.datetime.combine(bid_date, datetime.time()),
                        notes=notes,
                    )
                    session.add(bid)
                    session.commit()
                    st.success("Bid submitted.")
                    st.rerun()

    st.divider()
    st.subheader("Live RCM cash bids")
    st.caption("Auto-imported from RCM Co-op's cash bids feed. Refreshed periodically — an admin can also refresh on demand from the Admin page.")

    live_query = session.query(Bid).filter(Bid.source == "scraper")
    if target_originator_id:
        live_query = live_query.filter(Bid.originator_id == target_originator_id)
    live_bids = live_query.order_by(Bid.commodity).all()

    if not live_bids:
        st.info("No live bids yet. An admin needs to seed locations and run the scraper.")
    else:
        rows = []
        for b in live_bids:
            row = {
                "Commodity": b.commodity,
                "Basis": b.basis,
                "Futures Month": b.futures_month,
                "Cash Price": b.cash_price,
                "Updated": b.bid_date.strftime("%Y-%m-%d %H:%M") if b.bid_date else None,
            }
            if user.role == "admin":
                row = {"Location": b.originator.company_name, **row}
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Submitted bids")

    query = session.query(Bid).filter(Bid.source == "manual")
    if target_originator_id:
        query = query.filter(Bid.originator_id == target_originator_id)
    bids = query.order_by(Bid.bid_date.desc()).all()

    if not bids:
        st.info("No manually submitted bids on file yet.")
    else:
        rows = []
        for b in bids:
            row = {
                "Date": b.bid_date.date() if b.bid_date else None,
                "Commodity": b.commodity,
                "Location": b.location,
                "Basis": b.basis,
                "Futures Month": b.futures_month,
                "Cash Price": b.cash_price,
                "Notes": b.notes,
            }
            if user.role == "admin":
                row = {"Originator": b.originator.company_name, **row}
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
finally:
    session.close()
