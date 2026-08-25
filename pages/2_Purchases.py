import datetime

import pandas as pd
import streamlit as st

from auth import logout_button, require_login
from branding import LOGO_PATH, apply_logo
from db import Bid, Originator, Purchase, User, get_session

st.set_page_config(page_title="Purchases | RCM Originator Portal", page_icon=LOGO_PATH, layout="wide")
apply_logo()

user = require_login()
logout_button()

st.title("Purchases")

COMMODITIES = ["Corn", "Soybeans", "Wheat"]


def visible_locations(session, user):
    q = session.query(Originator).filter(Originator.active.is_(True))
    if user.role != "admin":
        q = q.filter(Originator.id == user.originator_id)
    return q.order_by(Originator.company_name).all()


def user_names(session):
    """username -> display name, so lists can show who entered each purchase."""
    return {u.username: u.name for u in session.query(User).all()}


def window_options(session, originator_id, commodity):
    """Live scraped bids for this location/commodity, one per delivery window."""
    return (
        session.query(Bid)
        .filter(Bid.originator_id == originator_id, Bid.commodity == commodity, Bid.source == "scraper")
        .order_by(Bid.delivery_start)
        .all()
    )


def render_purchase_form(session, user, locations, purchase=None):
    """Shared entry/edit form. Pass an existing Purchase to edit it in place."""
    is_edit = purchase is not None
    if is_edit:
        prefix = f"edit_{purchase.id}"
    else:
        # A fresh key per submission so Customer Name / Bushels start blank again —
        # Streamlit forbids clearing a widget's session_state after it's been
        # instantiated in the same run, so we rotate the key instead.
        nonce = st.session_state.get("purchase_form_nonce", 0)
        prefix = f"new_{nonce}"

    loc_by_name = {o.company_name: o.id for o in locations}
    if not loc_by_name:
        st.warning("No active locations available.")
        return False

    default_loc_name = None
    if is_edit:
        default_loc_name = next((n for n, i in loc_by_name.items() if i == purchase.originator_id), None)
    loc_names = list(loc_by_name.keys())
    loc_index = loc_names.index(default_loc_name) if default_loc_name in loc_names else 0

    c1, c2 = st.columns(2)
    commodity = c1.selectbox(
        "Commodity", COMMODITIES,
        index=COMMODITIES.index(purchase.commodity) if is_edit and purchase.commodity in COMMODITIES else 0,
        key=f"{prefix}_commodity",
    )
    location_name = c2.selectbox("Location", loc_names, index=loc_index, key=f"{prefix}_location")
    location_id = loc_by_name[location_name]

    bids = window_options(session, location_id, commodity)
    window_labels = {
        f"{b.futures_month} — basis {b.basis:+.2f}¢ / fut ${b.futures_price:.4f}": b
        for b in bids if b.futures_month
    }

    manual_mode = not window_labels
    matched_bid = None
    if manual_mode:
        st.info("No live delivery windows for this commodity at this location — enter basis and futures manually.")
    else:
        default_window_label = None
        if is_edit:
            default_window_label = next(
                (lbl for lbl, b in window_labels.items() if b.futures_month == purchase.futures_month), None
            )
        labels = list(window_labels.keys())
        w_index = labels.index(default_window_label) if default_window_label in labels else 0
        selected_label = st.selectbox("Delivery Window", labels, index=w_index, key=f"{prefix}_window")
        matched_bid = window_labels[selected_label]

    c3, c4 = st.columns(2)
    entry_date = c3.date_input(
        "Date", value=purchase.entry_date.date() if is_edit else datetime.date.today(), key=f"{prefix}_date"
    )
    customer_name = c4.text_input(
        "Customer Name", value=purchase.customer_name if is_edit else "", key=f"{prefix}_customer"
    )
    bushels = st.number_input(
        "Bushels", value=float(purchase.bushels) if is_edit else 0.0, step=1000.0, format="%.0f",
        key=f"{prefix}_bushels",
    )

    c5, c6 = st.columns(2)
    override_basis = c5.checkbox(
        "Override basis", value=purchase.basis_overridden if is_edit else False, key=f"{prefix}_override_basis"
    )
    override_futures = c6.checkbox(
        "Override futures month", value=purchase.futures_overridden if is_edit else False,
        key=f"{prefix}_override_futures",
    )

    basis_key = f"{prefix}_basis_value"
    if not override_basis:
        st.session_state[basis_key] = matched_bid.basis if matched_bid else (purchase.basis if is_edit else 0.0)
    elif basis_key not in st.session_state:
        st.session_state[basis_key] = purchase.basis if is_edit else 0.0
    basis_value = st.number_input(
        "Basis (cents vs. futures)", key=basis_key, disabled=not override_basis, step=0.25, format="%.2f"
    )

    futmonth_key = f"{prefix}_futmonth_value"
    futprice_key = f"{prefix}_futprice_value"
    if not override_futures:
        st.session_state[futmonth_key] = matched_bid.futures_month if matched_bid else (purchase.futures_month if is_edit else "")
        st.session_state[futprice_key] = matched_bid.futures_price if matched_bid else (purchase.futures_price if is_edit else 0.0)
    else:
        if futmonth_key not in st.session_state:
            st.session_state[futmonth_key] = purchase.futures_month if is_edit else ""
        if futprice_key not in st.session_state:
            st.session_state[futprice_key] = purchase.futures_price if is_edit else 0.0

    c7, c8 = st.columns(2)
    futures_month = c7.text_input("Futures Month", key=futmonth_key, disabled=not override_futures)
    futures_price = c8.number_input(
        "Futures Price ($/bu)", key=futprice_key, disabled=not override_futures, step=0.0025, format="%.4f",
        help="Only needed when overriding the futures month — the flat price is calculated from this.",
    )

    flat_price = (futures_price or 0.0) + (basis_value or 0.0) / 100
    st.metric("Flat Price ($/bu)", f"${flat_price:.4f}")

    button_label = "Save changes" if is_edit else "Submit Purchase"
    if st.button(button_label, key=f"{prefix}_submit", type="primary"):
        if not customer_name.strip():
            st.error("Customer name is required.")
            return False
        if not bushels:
            st.error("Bushels is required.")
            return False
        if manual_mode and not futures_month.strip():
            st.error("No live delivery window is available — enter a futures month manually.")
            return False

        if purchase is None:
            purchase = Purchase(created_by=user.username)
            session.add(purchase)
        purchase.originator_id = location_id
        purchase.entry_date = datetime.datetime.combine(entry_date, datetime.time())
        purchase.commodity = commodity
        purchase.delivery_window = matched_bid.futures_month if matched_bid else futures_month
        purchase.customer_name = customer_name.strip()
        purchase.bushels = bushels
        purchase.basis = basis_value
        purchase.basis_overridden = override_basis
        purchase.futures_month = futures_month
        purchase.futures_price = futures_price
        purchase.futures_overridden = override_futures
        purchase.flat_price = flat_price
        purchase.updated_by = user.username
        session.commit()

        st.success(
            f"{'Updated' if is_edit else 'Submitted'} purchase: {customer_name.strip()} — "
            f"{bushels:,.0f} bu {commodity} @ ${flat_price:.4f} ({location_name})"
        )
        if not is_edit:
            st.session_state["purchase_form_nonce"] = st.session_state.get("purchase_form_nonce", 0) + 1
        return True
    return False


session = get_session()
try:
    locations = visible_locations(session, user)
    names = user_names(session)
    location_ids = [o.id for o in locations]

    tab_entry, tab_list, tab_summary, tab_archive = st.tabs(
        ["Enter Purchase", "Today's Purchases", "Summary", "Archive"]
    )

    with tab_entry:
        if render_purchase_form(session, user, locations):
            st.rerun()

    view_date = st.session_state.get("view_date", datetime.date.today())
    day_start = datetime.datetime.combine(view_date, datetime.time())
    day_end = day_start + datetime.timedelta(days=1)
    purchases = (
        session.query(Purchase)
        .filter(
            Purchase.originator_id.in_(location_ids) if location_ids else False,
            Purchase.entry_date >= day_start,
            Purchase.entry_date < day_end,
        )
        .order_by(Purchase.created_at.desc())
        .all()
    )

    with tab_list:
        view_date = st.date_input("View date", value=datetime.date.today(), key="view_date")

        if not purchases:
            st.info(f"No purchases entered for {view_date.strftime('%B %d, %Y')}.")
        else:
            rows = [
                {
                    "Location": p.originator.company_name,
                    "Customer": p.customer_name,
                    "Commodity": p.commodity,
                    "Bushels": p.bushels,
                    "Delivery Window": p.delivery_window,
                    "Basis": p.basis,
                    "Futures Month": p.futures_month,
                    "Flat Price": p.flat_price,
                    "Entered by": names.get(p.created_by, p.created_by),
                }
                for p in purchases
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            total_bushels = sum(p.bushels or 0 for p in purchases)
            st.caption(f"{len(purchases)} purchase(s) — {total_bushels:,.0f} total bushels")

        st.divider()
        with st.expander("Edit an existing purchase"):
            all_visible = (
                session.query(Purchase)
                .filter(Purchase.originator_id.in_(location_ids) if location_ids else False)
                .order_by(Purchase.entry_date.desc())
                .limit(200)
                .all()
            )
            if not all_visible:
                st.info("No purchases to edit yet.")
            else:
                labels = {
                    f"{p.entry_date.date()} — {p.customer_name} — {p.commodity} — {p.bushels:,.0f} bu "
                    f"({p.originator.company_name})": p.id
                    for p in all_visible
                }
                pick = st.selectbox("Purchase", list(labels.keys()), key="edit_pick")
                selected = session.query(Purchase).filter(Purchase.id == labels[pick]).first()
                if selected and render_purchase_form(session, user, locations, purchase=selected):
                    st.rerun()

    with tab_summary:
        st.caption(f"Summary for {view_date.strftime('%B %d, %Y')}")
        if not purchases:
            st.info(f"No purchases entered for {view_date.strftime('%B %d, %Y')}.")
        else:
            total_bushels = sum(p.bushels or 0 for p in purchases)
            st.metric("Total bushels purchased", f"{total_bushels:,.0f}")

            summary_rows = {}
            for p in purchases:
                key = (p.commodity, p.delivery_window or "—")
                bucket = summary_rows.setdefault(key, {"bushels": 0.0, "count": 0})
                bucket["bushels"] += p.bushels or 0
                bucket["count"] += 1
            summary_df = pd.DataFrame(
                [
                    {
                        "Commodity": commodity,
                        "Delivery Window": window,
                        "Total Bushels": v["bushels"],
                        "Purchases": v["count"],
                    }
                    for (commodity, window), v in sorted(summary_rows.items())
                ]
            )
            st.dataframe(summary_df, use_container_width=True, hide_index=True)

    with tab_archive:
        st.caption("Browse and summarize purchase history across any date range.")
        earliest = session.query(Purchase.entry_date).order_by(Purchase.entry_date).first()
        default_start = earliest[0].date() if earliest else datetime.date.today()

        c1, c2 = st.columns(2)
        start_date = c1.date_input("From", value=default_start, key="archive_start")
        end_date = c2.date_input("To", value=datetime.date.today(), key="archive_end")

        loc_by_name_archive = {o.company_name: o.id for o in locations}
        filter_cols = st.columns(2)
        commodity_filter = filter_cols[0].selectbox("Commodity", ["All"] + COMMODITIES, key="archive_commodity")
        if user.role == "admin":
            location_filter = filter_cols[1].selectbox(
                "Location", ["All"] + list(loc_by_name_archive.keys()), key="archive_location"
            )
        else:
            location_filter = "All"

        if start_date > end_date:
            st.error("\"From\" date must be on or before \"To\" date.")
        else:
            range_start = datetime.datetime.combine(start_date, datetime.time())
            range_end = datetime.datetime.combine(end_date, datetime.time()) + datetime.timedelta(days=1)
            query = session.query(Purchase).filter(
                Purchase.originator_id.in_(location_ids) if location_ids else False,
                Purchase.entry_date >= range_start,
                Purchase.entry_date < range_end,
            )
            if commodity_filter != "All":
                query = query.filter(Purchase.commodity == commodity_filter)
            if location_filter != "All":
                query = query.filter(Purchase.originator_id == loc_by_name_archive[location_filter])
            archive_purchases = query.order_by(Purchase.entry_date.desc()).all()

            if not archive_purchases:
                st.info("No purchases found for this range.")
            else:
                total_bushels = sum(p.bushels or 0 for p in archive_purchases)
                st.metric("Total bushels in range", f"{total_bushels:,.0f}")

                st.subheader("Daily summary")
                summary_rows = {}
                for p in archive_purchases:
                    key = (p.entry_date.date(), p.commodity, p.delivery_window or "—")
                    bucket = summary_rows.setdefault(key, {"bushels": 0.0, "count": 0})
                    bucket["bushels"] += p.bushels or 0
                    bucket["count"] += 1
                summary_df = pd.DataFrame(
                    [
                        {
                            "Date": date,
                            "Commodity": commodity,
                            "Delivery Window": window,
                            "Total Bushels": v["bushels"],
                            "Purchases": v["count"],
                        }
                        for (date, commodity, window), v in sorted(summary_rows.items(), reverse=True)
                    ]
                )
                st.dataframe(summary_df, use_container_width=True, hide_index=True)

                st.subheader("All purchases in range")
                rows = [
                    {
                        "Date": p.entry_date.date(),
                        "Location": p.originator.company_name,
                        "Customer": p.customer_name,
                        "Commodity": p.commodity,
                        "Bushels": p.bushels,
                        "Delivery Window": p.delivery_window,
                        "Basis": p.basis,
                        "Futures Month": p.futures_month,
                        "Flat Price": p.flat_price,
                        "Entered by": names.get(p.created_by, p.created_by),
                    }
                    for p in archive_purchases
                ]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
finally:
    session.close()
