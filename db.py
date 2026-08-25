"""Database engine, session, and models for the RCM Originator Portal.

Defaults to a local SQLite file so the app is fully self-contained and easy
to hand off. Set DATABASE_URL to point at a different server without
changing any code elsewhere in the app — e.g. a Postgres URL, or a Snowflake
SQLAlchemy URL: "snowflake://{user}:{password}@{account}/{database}/{schema}
?warehouse={warehouse}&role={role}" (requires snowflake-sqlalchemy).
"""
import datetime
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

load_dotenv()


def _database_url() -> str:
    """Local dev reads DATABASE_URL from .env. On Streamlit Cloud, the same
    key is set via the app's Secrets UI instead, exposed through st.secrets
    rather than the process environment — fall back to that when present.
    Scripts run outside Streamlit (the scraper's cron job) never reach the
    st.secrets branch, since importing streamlit there still works but
    st.secrets raises without a running app; os.getenv covers that case.
    """
    env_value = os.getenv("DATABASE_URL")
    if env_value:
        return env_value
    try:
        import streamlit as st
        return st.secrets["DATABASE_URL"]
    except Exception:
        pass
    return f"sqlite:///{Path(__file__).resolve().parent / 'rcm_portal.db'}"


DATABASE_URL = _database_url()

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


class Originator(Base):
    __tablename__ = "originators"

    id = Column(Integer, primary_key=True)
    company_name = Column(String(200), nullable=False)
    contact_name = Column(String(200))
    email = Column(String(200))
    phone = Column(String(50))
    city = Column(String(100))
    state = Column(String(50))
    commodities = Column(String(300))  # comma-separated, e.g. "Corn, Soybeans"
    notes = Column(Text)
    active = Column(Boolean, default=True)
    feed_location_id = Column(String(50))  # RCM Coop Barchart/AgriCharts board id, if fed by the scraper
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    users = relationship("User", back_populates="originator", cascade="all, delete-orphan")
    bids = relationship("Bid", back_populates="originator", cascade="all, delete-orphan")
    purchases = relationship("Purchase", back_populates="originator", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    originator_id = Column(Integer, ForeignKey("originators.id"), nullable=True)
    username = Column(String(100), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    email = Column(String(200))
    password_hash = Column(String(200), nullable=False)
    role = Column(String(20), nullable=False, default="originator")  # "admin" or "originator"
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    originator = relationship("Originator", back_populates="users")


class Bid(Base):
    __tablename__ = "bids"

    id = Column(Integer, primary_key=True)
    originator_id = Column(Integer, ForeignKey("originators.id"), nullable=False)
    commodity = Column(String(50), nullable=False)
    location = Column(String(200))
    basis = Column(Float)
    futures_month = Column(String(20))
    futures_price = Column(Float)  # $/bu — derived so overrides can recompute flat price without a live quote
    delivery_start = Column(DateTime)  # for sorting delivery windows chronologically ("Sep 2026" < "Dec 2026")
    cash_price = Column(Float)
    bid_date = Column(DateTime, default=datetime.datetime.utcnow)
    notes = Column(Text)
    source = Column(String(20), nullable=False, default="manual")  # "manual" or "scraper"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    originator = relationship("Originator", back_populates="bids")


class Purchase(Base):
    """A grain purchase entered against a customer at one of RCM's locations."""
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True)
    originator_id = Column(Integer, ForeignKey("originators.id"), nullable=False)
    entry_date = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    commodity = Column(String(50), nullable=False)
    delivery_window = Column(String(50))  # e.g. "Sep 2026" — the quoted board's basis month
    customer_name = Column(String(200), nullable=False)
    bushels = Column(Float, nullable=False)
    basis = Column(Float)  # cents vs. futures
    basis_overridden = Column(Boolean, default=False)
    futures_month = Column(String(20))
    futures_price = Column(Float)  # $/bu
    futures_overridden = Column(Boolean, default=False)
    flat_price = Column(Float)  # $/bu = futures_price + basis/100
    created_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_by = Column(String(100))
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    originator = relationship("Originator", back_populates="purchases")


def init_db():
    Base.metadata.create_all(engine)


def get_session():
    return SessionLocal()
