"""
Database setup. Uses SQLite by default (a single local file, zero setup) —
plenty for a personal tool. Set DATABASE_URL in .env to point at Postgres
or another SQLAlchemy-supported database if you outgrow SQLite.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./job_assistant.db")

# Render and other cloud providers supply PostgreSQL URLs starting with 'postgres://',
# but SQLAlchemy 1.4+ / 2.0+ requires 'postgresql://'.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine_kwargs = {
    "connect_args": connect_args,
}
if not is_sqlite:
    # Recycles stale connections in cloud PostgreSQL environments like Render
    engine_kwargs["pool_pre_ping"] = True

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401 — ensures models are registered before create_all
    Base.metadata.create_all(bind=engine)
