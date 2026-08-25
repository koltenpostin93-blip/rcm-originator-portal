"""One-time setup: create the first admin account.

Usage:
    python seed_admin.py
"""
import getpass

from auth import hash_password
from db import User, get_session, init_db


def main():
    init_db()
    session = get_session()
    try:
        if session.query(User).filter(User.role == "admin").first():
            print("An admin account already exists. Nothing to do.")
            return

        print("Create the first admin account for the RCM Originator Portal.")
        username = input("Username: ").strip()
        name = input("Full name: ").strip()
        email = input("Email: ").strip()
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")

        if not username or not name or not password:
            print("Username, name, and password are required.")
            return
        if password != confirm:
            print("Passwords did not match.")
            return

        session.add(
            User(
                username=username,
                name=name,
                email=email,
                password_hash=hash_password(password),
                role="admin",
            )
        )
        session.commit()
        print(f"Admin account '{username}' created.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
