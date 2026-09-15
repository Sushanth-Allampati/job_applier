from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    applied_jobs = relationship("AppliedJob", back_populates="user", cascade="all, delete-orphan")


class AppliedJob(Base):
    """
    One row per job a user has marked as applied. job_id is a stable hash
    of (source, title, company, apply_url) computed by job_search.py, so
    the same posting is recognized as 'already applied' on future searches
    even though job boards don't give us a consistent ID across queries.
    """
    __tablename__ = "applied_jobs"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_user_job"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(String, nullable=False, index=True)

    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    apply_url = Column(Text, nullable=False)
    source = Column(String, nullable=False)

    applied_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="applied_jobs")
