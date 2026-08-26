import pandas as pd
import streamlit as st

from auth import hash_password, logout_button, require_admin, require_login
from branding import LOGO_PATH, apply_logo
from db import Originator, User, get_session
from live_bids import get_boards
from seed_locations import seed_locations

st.set_page_config(page_title="Admin | RCM Originator Portal", page_icon=LOGO_PATH, layout="wide")
apply_logo()

user = require_login()
logout_button()
require_admin(user)

st.title("Admin")

session = get_session()
try:
    tab_users, tab_originators, tab_feed = st.tabs(["User accounts", "Originators", "Live bids feed"])

    with tab_originators:
        st.subheader("Add a new originator")
        with st.form("new_originator_form", clear_on_submit=True):
            company_name = st.text_input("Company name")
            contact_name = st.text_input("Contact name")
            c1, c2 = st.columns(2)
            email = c1.text_input("Email")
            phone = c2.text_input("Phone")
            c3, c4 = st.columns(2)
            city = c3.text_input("City")
            state = c4.text_input("State")
            commodities = st.text_input("Commodities handled (comma-separated)")
            submitted = st.form_submit_button("Add originator")
            if submitted:
                if not company_name:
                    st.error("Company name is required.")
                else:
                    session.add(
                        Originator(
                            company_name=company_name,
                            contact_name=contact_name,
                            email=email,
                            phone=phone,
                            city=city,
                            state=state,
                            commodities=commodities,
                        )
                    )
                    session.commit()
                    st.success(f"Added {company_name}.")
                    st.rerun()

        st.divider()
        st.subheader("Existing originators")
        originators = session.query(Originator).order_by(Originator.company_name).all()
        if originators:
            df = pd.DataFrame(
                [
                    {
                        "Company": o.company_name,
                        "Contact": o.contact_name,
                        "Email": o.email,
                        "Phone": o.phone,
                        "City": o.city,
                        "State": o.state,
                        "Commodities": o.commodities,
                        "Active": o.active,
                    }
                    for o in originators
                ]
            )
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.subheader("Deactivate / reactivate an originator")
            opt = {f"{o.company_name} ({'active' if o.active else 'inactive'})": o.id for o in originators}
            pick = st.selectbox("Originator", list(opt.keys()))
            colA, colB = st.columns(2)
            if colA.button("Toggle active status"):
                target = session.query(Originator).filter(Originator.id == opt[pick]).first()
                target.active = not target.active
                session.commit()
                st.rerun()
        else:
            st.info("No originators yet — add one above.")

    with tab_users:
        st.subheader("Create a user account")
        originators = session.query(Originator).filter(Originator.active.is_(True)).order_by(Originator.company_name).all()
        with st.form("new_user_form", clear_on_submit=True):
            username = st.text_input("Username")
            name = st.text_input("Full name")
            email = st.text_input("Email")
            role = st.selectbox("Role", ["originator", "admin"])
            originator_choice = None
            if role == "originator":
                opt = {o.company_name: o.id for o in originators}
                if opt:
                    originator_choice = st.selectbox("Linked originator", list(opt.keys()))
                else:
                    st.warning("Add an originator company first.")
            password = st.text_input("Temporary password", type="password")
            submitted = st.form_submit_button("Create account")

            if submitted:
                if not username or not name or not password:
                    st.error("Username, name, and password are required.")
                elif session.query(User).filter(User.username == username).first():
                    st.error("That username is already taken.")
                elif role == "originator" and not originator_choice:
                    st.error("Select an originator to link this account to.")
                else:
                    new_user = User(
                        username=username,
                        name=name,
                        email=email,
                        password_hash=hash_password(password),
                        role=role,
                        originator_id=opt[originator_choice] if role == "originator" else None,
                    )
                    session.add(new_user)
                    session.commit()
                    st.success(f"Created account for {username}.")
                    st.rerun()

        st.divider()
        st.subheader("Existing accounts")
        users = session.query(User).order_by(User.username).all()
        if users:
            df = pd.DataFrame(
                [
                    {
                        "Username": u.username,
                        "Name": u.name,
                        "Role": u.role,
                        "Originator": u.originator.company_name if u.originator else "—",
                        "Active": u.active,
                    }
                    for u in users
                ]
            )
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.subheader("Deactivate / reactivate an account")
            opt2 = {f"{u.username} ({'active' if u.active else 'inactive'})": u.id for u in users if u.id != user.id}
            if opt2:
                pick2 = st.selectbox("Account", list(opt2.keys()), key="user_toggle")
                if st.button("Toggle active status", key="toggle_user_btn"):
                    target = session.query(User).filter(User.id == opt2[pick2]).first()
                    target.active = not target.active
                    session.commit()
                    st.rerun()

            st.subheader("Reset a password")
            opt3 = {u.username: u.id for u in users}
            pick3 = st.selectbox("Account", list(opt3.keys()), key="pw_reset")
            new_pw = st.text_input("New password", type="password", key="new_pw")
            if st.button("Reset password"):
                if not new_pw:
                    st.error("Enter a new password.")
                else:
                    target = session.query(User).filter(User.id == opt3[pick3]).first()
                    target.password_hash = hash_password(new_pw)
                    session.commit()
                    st.success(f"Password reset for {pick3}.")
        else:
            st.info("No accounts yet — create one above.")

    with tab_feed:
        st.subheader("RCM Co-op live cash bids")
        st.caption(
            "Bids & Purchases pull this feed live (cached up to 2 minutes) — there's nothing to "
            "refresh or keep in sync here. This tab is just for checking the location → board "
            "mapping and previewing what the feed currently returns."
        )
        linked = (
            session.query(Originator)
            .filter(Originator.feed_location_id.isnot(None))
            .order_by(Originator.company_name)
            .all()
        )
        if linked:
            st.dataframe(
                pd.DataFrame(
                    [{"Location": o.company_name, "Feed board id": o.feed_location_id} for o in linked]
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning("No locations are linked to a feed board yet.")
            if st.button("Seed the 12 RCM Co-op locations"):
                added = seed_locations(session)
                session.commit()
                st.success(f"Seeded {added} locations.")
                st.rerun()

        if st.button("Preview live feed now"):
            boards = get_boards()
            rows = [
                {"Board": board_id, "Commodity": b["commodity"], "Futures Month": b["futures_month"],
                 "Basis": b["basis"], "Futures Price": b["futures_price"]}
                for board_id, bids in boards.items() for b in bids
            ]
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.error("The feed returned nothing — RCM's site may be unreachable right now.")
finally:
    session.close()
