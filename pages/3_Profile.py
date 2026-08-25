import streamlit as st

from auth import logout_button, require_login
from branding import LOGO_PATH, apply_logo
from db import Originator, get_session

st.set_page_config(page_title="Profile | RCM Originator Portal", page_icon=LOGO_PATH, layout="wide")
apply_logo()

user = require_login()
logout_button()

st.title("Company Profile")

if user.role == "admin" and not user.originator_id:
    st.info("Admin accounts aren't tied to a single originator. Manage originator profiles from the Admin page.")
    st.stop()

session = get_session()
try:
    originator = session.query(Originator).filter(Originator.id == user.originator_id).first()
    if not originator:
        st.error("No originator profile is linked to this account. Contact RCM staff.")
        st.stop()

    with st.form("profile_form"):
        company_name = st.text_input("Company name", value=originator.company_name or "")
        contact_name = st.text_input("Contact name", value=originator.contact_name or "")
        c1, c2 = st.columns(2)
        email = c1.text_input("Email", value=originator.email or "")
        phone = c2.text_input("Phone", value=originator.phone or "")
        c3, c4 = st.columns(2)
        city = c3.text_input("City", value=originator.city or "")
        state = c4.text_input("State", value=originator.state or "")
        commodities = st.text_input("Commodities handled (comma-separated)", value=originator.commodities or "")
        notes = st.text_area("Notes", value=originator.notes or "", height=100)
        submitted = st.form_submit_button("Save changes")

        if submitted:
            originator.company_name = company_name
            originator.contact_name = contact_name
            originator.email = email
            originator.phone = phone
            originator.city = city
            originator.state = state
            originator.commodities = commodities
            originator.notes = notes
            session.commit()
            st.success("Profile updated.")
finally:
    session.close()
