from __future__ import annotations

import os
from dataclasses import asdict

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .database import get_db, init_db
from .models import User, AppliedJob
from .auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_current_user_optional,
)
from .resume_parser import extract_resume_text
from .ats_scorer import score_resume
from .job_search import search_jobs
from .keyword_extractor import extract_keywords

app = FastAPI(title="Job Application Assistant API", version="2.0.0")

allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "*")
if allowed_origins_raw.strip() == "*":
    allowed_origins = ["*"]
else:
    allowed_origins = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


# ---------- Schemas ----------

class ScoreResponse(BaseModel):
    score: int
    matched_keywords: list[str]
    missing_keywords: list[str]
    formatting_notes: list[str]
    section_notes: list[str]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MarkAppliedRequest(BaseModel):
    job_id: str
    title: str
    company: str
    apply_url: str
    source: str


# ---------- Health ----------

@app.get("/")
def health_check():
    return {"status": "ok", "service": "job-application-assistant"}


# ---------- Auth ----------

@app.post("/api/auth/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
    db.refresh(user)

    token = create_access_token({"sub": user.email})
    return TokenResponse(access_token=token)


@app.post("/api/auth/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # form_data.username holds the email (OAuth2 spec calls it 'username')
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    token = create_access_token({"sub": user.email})
    return TokenResponse(access_token=token)


@app.get("/api/auth/me")
def read_me(current_user: User = Depends(get_current_user)):
    return {"email": current_user.email}


# ---------- Resume scoring ----------

@app.post("/api/score-resume", response_model=ScoreResponse)
async def api_score_resume(
    resume: UploadFile = File(...),
    job_description: str = Form(...),
):
    file_bytes = await resume.read()
    try:
        resume_text = extract_resume_text(file_bytes, resume.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    result = score_resume(resume_text, job_description)
    return ScoreResponse(**asdict(result))


# ---------- Job search (auth optional — logged-out users just don't get applied-tracking) ----------

@app.post("/api/search-jobs")
async def api_search_jobs(
    role: str = Form(...),
    location: str = Form(""),
    resume: UploadFile | None = File(None),
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    resume_text = None
    if resume is not None:
        file_bytes = await resume.read()
        try:
            resume_text = extract_resume_text(file_bytes, resume.filename or "")
        except ValueError:
            resume_text = None  # non-fatal — search still works without it

    listings = await search_jobs(role=role, location=location, resume_text=resume_text)

    applied_ids: set[str] = set()
    if current_user is not None:
        applied_ids = {
            row.job_id for row in
            db.query(AppliedJob.job_id).filter(AppliedJob.user_id == current_user.id).all()
        }

    to_apply, applied = [], []
    for listing in listings:
        listing.already_applied = listing.job_id in applied_ids
        (applied if listing.already_applied else to_apply).append(asdict(listing))

    return {
        "to_apply_count": len(to_apply),
        "applied_count": len(applied),
        "to_apply": to_apply,
        "applied": applied,
        "logged_in": current_user is not None,
    }


# ---------- Applied-jobs tracking (requires login) ----------

@app.post("/api/applications")
def mark_applied(
    payload: MarkAppliedRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.query(AppliedJob).filter(
        AppliedJob.user_id == current_user.id,
        AppliedJob.job_id == payload.job_id,
    ).first()
    if existing:
        return {"status": "already_marked"}

    row = AppliedJob(
        user_id=current_user.id,
        job_id=payload.job_id,
        title=payload.title,
        company=payload.company,
        apply_url=payload.apply_url,
        source=payload.source,
    )
    db.add(row)
    db.commit()
    return {"status": "marked_applied"}


@app.delete("/api/applications/{job_id}")
def unmark_applied(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(AppliedJob).filter(
        AppliedJob.user_id == current_user.id,
        AppliedJob.job_id == job_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found in your applied list.")
    db.delete(row)
    db.commit()
    return {"status": "unmarked"}


@app.get("/api/applications")
def list_applications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(AppliedJob).filter(AppliedJob.user_id == current_user.id).order_by(AppliedJob.applied_at.desc()).all()
    return {
        "count": len(rows),
        "results": [
            {
                "job_id": r.job_id,
                "title": r.title,
                "company": r.company,
                "apply_url": r.apply_url,
                "source": r.source,
                "applied_at": r.applied_at.isoformat(),
            }
            for r in rows
        ],
    }


# ---------- Standalone keyword extraction ----------

@app.post("/api/keywords")
async def api_keywords(text: str = Form(...)):
    return {"keywords": extract_keywords(text, top_n=25)}
