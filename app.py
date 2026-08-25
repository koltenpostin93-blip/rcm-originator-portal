import datetime

import streamlit as st

from auth import logout_button, require_login
from branding import LOGO_PATH, apply_logo
from db import Bid, Purchase, init_db, get_session

st.set_page_config(page_title="RCM Originator Portal", page_icon=LOGO_PATH, layout="wide")
apply_logo()

init_db()
user = require_login()
logout_button()

header_logo, header_title = st.columns([1, 6], vertical_alignment="center")
header_logo.image(LOGO_PATH, width=90)
with header_title:
    st.title("RCM Originator Portal")
    st.caption(f"Welcome, {user.name} ({'Administrator' if user.role == 'admin' else 'Originator'})")

today_start = datetime.datetime.combine(datetime.date.today(), datetime.time())
today_end = today_start + datetime.timedelta(days=1)

session = get_session()
try:
    if user.role == "admin":
        bid_count = session.query(Bid).count()
        purchases_today = session.query(Purchase).filter(
            Purchase.entry_date >= today_start, Purchase.entry_date < today_end
        ).count()
        bushels_today = sum(
            p.bushels or 0
            for p in session.query(Purchase).filter(
                Purchase.entry_date >= today_start, Purchase.entry_date < today_end
            ).all()
        )
    else:
        bid_count = session.query(Bid).filter(Bid.originator_id == user.originator_id).count()
        todays_purchases = session.query(Purchase).filter(
            Purchase.originator_id == user.originator_id,
            Purchase.entry_date >= today_start,
            Purchase.entry_date < today_end,
        ).all()
        purchases_today = len(todays_purchases)
        bushels_today = sum(p.bushels or 0 for p in todays_purchases)
finally:
    session.close()

col1, col2, col3 = st.columns(3)
col1.metric("Live bids on file", bid_count)
col2.metric("Purchases entered today", purchases_today)
col3.metric("Bushels purchased today", f"{bushels_today:,.0f}")

st.divider()
st.markdown(
    """
Use the sidebar to:
- **Bids** — review live basis/bid levels pulled from RCM Co-op
- **Purchases** — enter and edit today's grain purchases
- **Profile** — keep your company information current
"""
    + ("\n- **Admin** — manage originator accounts" if user.role == "admin" else "")
)
