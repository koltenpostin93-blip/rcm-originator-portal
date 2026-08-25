"""Authentication helpers built on streamlit-authenticator.

Credentials are rebuilt from the database on every run so that accounts
created via the Admin page take effect immediately, without restarting
the app or editing a config file.
"""
import bcrypt
import streamlit as st
import streamlit_authenticator as stauth

from db import User, get_session

COOKIE_NAME = "rcm_originator_portal"
COOKIE_KEY = "rcm_originator_portal_signature_key"
COOKIE_EXPIRY_DAYS = 7


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _build_credentials():
    session = get_session()
    try:
        users = session.query(User).filter(User.active.is_(True)).all()
        credentials = {"usernames": {}}
        for u in users:
            credentials["usernames"][u.username] = {
                "name": u.name,
                "email": u.email or "",
                "password": u.password_hash,
            }
        return credentials
    finally:
        session.close()


def get_authenticator():
    """Reuse one Authenticate instance across reruns.

    stauth.Authenticate creates its own CookieManager component internally;
    building a fresh instance on every script run gives that component a new
    identity each time and the cookie round-trip never resolves (the login
    widget hangs on "Running..." forever). Instead, create it once per
    browser session and just refresh its credentials dict in place.
    """
    credentials = _build_credentials()
    if "authenticator" not in st.session_state:
        st.session_state["authenticator"] = stauth.Authenticate(
            credentials,
            COOKIE_NAME,
            COOKIE_KEY,
            COOKIE_EXPIRY_DAYS,
        )
    else:
        # Authenticate has no .credentials of its own — the real copy lives on
        # its internal AuthenticationHandler. Update that in place so accounts
        # created/edited via the Admin page take effect without a full reset.
        st.session_state["authenticator"].authentication_handler.credentials = credentials
    return st.session_state["authenticator"]


def current_user():
    """Return the logged-in User row, or None."""
    username = st.session_state.get("username")
    if not username:
        return None
    session = get_session()
    try:
        user = session.query(User).filter(User.username == username).first()
        if user:
            session.expunge(user)
        return user
    finally:
        session.close()


def require_login():
    """Render the login form; stop the page if not authenticated.

    Returns the logged-in User row on success.
    """
    authenticator = get_authenticator()
    authenticator.login(location="main")

    auth_status = st.session_state.get("authentication_status")

    if auth_status is False:
        st.error("Username or password is incorrect.")
        st.stop()
    elif auth_status is None:
        st.info("Please log in to continue.")
        st.stop()

    user = current_user()
    if user is None or not user.active:
        st.error("This account is no longer active. Contact RCM staff.")
        st.stop()

    st.session_state["authenticator"] = authenticator
    st.session_state["current_role"] = user.role
    st.session_state["current_originator_id"] = user.originator_id
    return user


def require_admin(user):
    if user.role != "admin":
        st.error("You don't have access to this page.")
        st.stop()


def logout_button():
    authenticator = st.session_state.get("authenticator")
    if authenticator:
        authenticator.logout("Log out", "sidebar")
