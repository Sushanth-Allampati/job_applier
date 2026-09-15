"""
Heuristic legitimacy filter for job postings.

This is NOT a guarantee — it's a set of red-flag checks based on common
patterns in job scams (especially prevalent in India-focused listings:
fake "registration fee" jobs, WFH-unlimited-earning schemes, etc).
Every posting gets a verdict of "likely_legit", "verify", or "high_risk"
plus the specific reasons, so the user can make the final call.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SCAM_PHRASES = [
    "registration fee", "processing fee", "security deposit",
    "pay to apply", "training fee", "refundable deposit",
    "unlimited earning", "earn from home guaranteed", "no interview required",
    "instant hiring", "franchise opportunity", "investment required",
    "whatsapp only", "telegram only", "dm for details", "limited seats hurry",
    "daily payout", "join now pay later",
]

VAGUE_TITLE_PHRASES = [
    "work from home job", "part time job for students", "data entry job",
    "online job no experience",
]

TRUSTED_ATS_DOMAINS = [
    "greenhouse.io", "lever.co", "myworkdayjobs.com", "smartrecruiters.com",
    "icims.com", "successfactors.com", "ashbyhq.com", "bamboohr.com",
    "workable.com",
]


@dataclass
class LegitimacyResult:
    verdict: str  # "likely_legit" | "verify" | "high_risk"
    reasons: list[str] = field(default_factory=list)


def assess_posting(title: str, description: str, company: str, apply_url: str) -> LegitimacyResult:
    text = f"{title} {description}".lower()
    reasons: list[str] = []
    risk_points = 0

    for phrase in SCAM_PHRASES:
        if phrase in text:
            risk_points += 3
            reasons.append(f"Contains common scam phrasing: \"{phrase}\"")

    for phrase in VAGUE_TITLE_PHRASES:
        if phrase in title.lower():
            risk_points += 1
            reasons.append(f"Vague/generic title pattern: \"{phrase}\"")

    if not company or company.strip().lower() in {"confidential", "reputed company", "leading company"}:
        risk_points += 2
        reasons.append("Company name is missing or deliberately vague.")

    if apply_url and any(domain in apply_url for domain in TRUSTED_ATS_DOMAINS):
        risk_points -= 3
        reasons.append("Apply link goes through a recognized applicant-tracking platform (positive signal).")

    if apply_url and not apply_url.startswith("http"):
        risk_points += 2
        reasons.append("Apply link is malformed or missing.")

    if risk_points >= 5:
        verdict = "high_risk"
    elif risk_points >= 2:
        verdict = "verify"
    else:
        verdict = "likely_legit"

    if not reasons:
        reasons.append("No red-flag patterns detected — still verify the company independently before applying.")

    return LegitimacyResult(verdict=verdict, reasons=reasons)
