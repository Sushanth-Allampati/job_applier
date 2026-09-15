"""
ATS-style scoring: how well does a resume match a given job description,
plus basic formatting checks that mirror what real ATS parsers choke on.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .keyword_extractor import extract_keywords

REQUIRED_SECTIONS = [
    ("experience", ["experience", "work history", "employment"]),
    ("education", ["education", "academic"]),
    ("skills", ["skills", "technical skills", "core competencies"]),
]

CONTACT_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"(\+?\d[\d\-\s()]{8,}\d)"),
}


@dataclass
class ATSResult:
    score: int
    matched_keywords: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    formatting_notes: list[str] = field(default_factory=list)
    section_notes: list[str] = field(default_factory=list)


def _check_sections(resume_text_lower: str) -> list[str]:
    notes = []
    for label, variants in REQUIRED_SECTIONS:
        if not any(v in resume_text_lower for v in variants):
            notes.append(f"No clear '{label.title()}' section header found — ATS parsers rely on section headers to bucket your content correctly.")
    return notes


def _check_formatting(resume_text: str) -> list[str]:
    notes = []
    if not CONTACT_PATTERNS["email"].search(resume_text):
        notes.append("No email address detected — make sure it's in plain text, not inside an image or text box.")
    if not CONTACT_PATTERNS["phone"].search(resume_text):
        notes.append("No phone number detected in plain text.")
    if len(resume_text) < 800:
        notes.append("Resume text is quite short — it may be missing detail, or content may be trapped in a table/graphic an ATS can't read.")
    # crude heuristic for likely table/column layouts producing jumbled text
    lines = resume_text.splitlines()
    very_short_lines = sum(1 for l in lines if 0 < len(l.strip()) <= 3)
    if lines and very_short_lines / max(len(lines), 1) > 0.25:
        notes.append("Text extraction looks fragmented — this often happens with multi-column layouts or tables, which many ATS parsers scramble.")
    return notes


def score_resume(resume_text: str, job_description: str) -> ATSResult:
    resume_lower = resume_text.lower()
    jd_keywords = extract_keywords(job_description, top_n=30)

    matched = [kw for kw in jd_keywords if kw in resume_lower]
    missing = [kw for kw in jd_keywords if kw not in resume_lower]

    keyword_ratio = len(matched) / len(jd_keywords) if jd_keywords else 0
    keyword_score = round(keyword_ratio * 70)  # keywords = 70% of score

    section_notes = _check_sections(resume_lower)
    formatting_notes = _check_formatting(resume_text)

    penalty = min(len(section_notes) * 5 + len(formatting_notes) * 3, 30)
    formatting_score = 30 - penalty

    total = max(0, min(100, keyword_score + formatting_score))

    return ATSResult(
        score=total,
        matched_keywords=matched,
        missing_keywords=missing,
        formatting_notes=formatting_notes,
        section_notes=section_notes,
    )
