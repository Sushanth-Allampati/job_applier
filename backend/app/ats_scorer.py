"""
ATS-style scoring: how well does a resume match a given job description or role,
plus basic formatting checks that mirror what real ATS parsers evaluate.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .keyword_extractor import extract_keywords, SKILL_DICTIONARY

REQUIRED_SECTIONS = [
    ("experience", ["experience", "work history", "employment"]),
    ("education", ["education", "academic"]),
    ("skills", ["skills", "technical skills", "core competencies"]),
]

CONTACT_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"(\+?\d[\d\-\s()]{8,}\d)"),
}

ROLE_SKILL_PATTERNS: dict[str, list[str]] = {
    "frontend": ["javascript", "typescript", "react", "html", "css", "vue", "angular", "rest api", "git", "ui/ux", "unit testing"],
    "react": ["react", "javascript", "typescript", "html", "css", "rest api", "git", "unit testing"],
    "backend": ["python", "java", "sql", "postgresql", "rest api", "docker", "fastapi", "django", "node.js", "microservices", "git", "redis"],
    "full stack": ["javascript", "typescript", "react", "node.js", "python", "sql", "html", "css", "git", "rest api", "docker"],
    "data science": ["python", "data analysis", "machine learning", "pandas", "numpy", "sql", "scikit-learn", "data science", "deep learning", "tableau"],
    "data analyst": ["sql", "data analysis", "excel", "power bi", "tableau", "python", "data engineering", "problem solving"],
    "data engineer": ["sql", "python", "etl", "data engineering", "spark", "hadoop", "airflow", "postgresql", "docker", "nosql"],
    "machine learning": ["python", "machine learning", "deep learning", "pytorch", "tensorflow", "nlp", "scikit-learn", "numpy", "pandas", "computer vision"],
    "ai": ["python", "machine learning", "deep learning", "pytorch", "tensorflow", "nlp", "scikit-learn", "algorithms", "rest api"],
    "devops": ["docker", "kubernetes", "aws", "ci/cd", "linux", "terraform", "git", "azure", "gcp", "agile", "microservices"],
    "cloud": ["aws", "azure", "gcp", "docker", "kubernetes", "terraform", "linux", "ci/cd", "microservices", "system design"],
    "mobile": ["react", "javascript", "typescript", "git", "rest api", "unit testing", "ui/ux", "agile"],
    "android": ["java", "rest api", "git", "unit testing", "ui/ux", "agile"],
    "ios": ["rest api", "git", "unit testing", "ui/ux", "agile"],
    "product": ["project management", "agile", "scrum", "leadership", "communication", "problem solving", "ui/ux", "figma"],
    "designer": ["figma", "ui/ux", "html", "css", "communication", "problem solving"],
    "qa": ["testing", "unit testing", "python", "javascript", "ci/cd", "git", "agile", "problem solving"],
    "security": ["linux", "python", "git", "docker", "cloud", "problem solving", "algorithms"],
    "software": ["algorithms", "data structures", "system design", "git", "object oriented", "unit testing", "sql", "rest api", "agile"],
    "python": ["python", "sql", "rest api", "git", "docker", "django", "flask", "fastapi", "unit testing"],
    "java": ["java", "spring", "sql", "microservices", "docker", "git", "rest api", "unit testing", "system design"],
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
            notes.append(f"No clear '{label.title()}' section header found — ATS parsers rely on section headers to bucket content correctly.")
    return notes


def _check_formatting(resume_text: str) -> list[str]:
    notes = []
    if not CONTACT_PATTERNS["email"].search(resume_text):
        notes.append("No email address detected — make sure it's in plain text, not inside an image or text box.")
    if not CONTACT_PATTERNS["phone"].search(resume_text):
        notes.append("No phone number detected in plain text.")
    if len(resume_text) < 800:
        notes.append("Resume text is quite short — it may be missing detail, or content may be trapped in a table/graphic.")
    lines = resume_text.splitlines()
    very_short_lines = sum(1 for l in lines if 0 < len(l.strip()) <= 3)
    if lines and very_short_lines / max(len(lines), 1) > 0.25:
        notes.append("Text extraction looks fragmented — multi-column layouts or tables can scramble parser output.")
    return notes


def _get_role_expected_skills(role: str) -> list[str]:
    role_lower = role.lower()
    skills: list[str] = []
    for key, expected in ROLE_SKILL_PATTERNS.items():
        if key in role_lower:
            for s in expected:
                if s not in skills:
                    skills.append(s)
    if not skills:
        skills = ["git", "rest api", "sql", "problem solving", "communication", "agile", "testing", "algorithms", "unit testing"]
    return skills


def score_resume(resume_text: str, job_description: str = "", role: str = "") -> ATSResult:
    resume_lower = resume_text.lower()
    jd_clean = job_description.strip()
    role_clean = role.strip()

    section_notes = _check_sections(resume_lower)
    formatting_notes = _check_formatting(resume_text)
    penalty = min(len(section_notes) * 5 + len(formatting_notes) * 3, 30)
    formatting_score = 30 - penalty

    if jd_clean:
        # 1. Targeted Job Description Match
        target_keywords = extract_keywords(jd_clean, top_n=30)
        matched = [kw for kw in target_keywords if kw in resume_lower]
        missing = [kw for kw in target_keywords if kw not in resume_lower]
        ratio = len(matched) / len(target_keywords) if target_keywords else 0.5
        keyword_score = round(ratio * 70)
    elif role_clean:
        # 2. Role-based Benchmark Match (Job Description omitted)
        expected_skills = _get_role_expected_skills(role_clean)
        matched = [kw for kw in expected_skills if kw in resume_lower]
        missing = [kw for kw in expected_skills if kw not in resume_lower]
        ratio = len(matched) / max(len(expected_skills), 1)
        keyword_score = round(ratio * 70)
    else:
        # 3. General ATS Health & Recognized Skills (Neither JD nor Role provided)
        found_skills = [skill for skill in sorted(SKILL_DICTIONARY) if skill in resume_lower]
        matched = found_skills[:20]
        common_must_haves = ["git", "rest api", "testing", "agile", "communication", "problem solving", "sql"]
        missing = [s for s in common_must_haves if s not in resume_lower]
        ratio = min(len(found_skills) / 8.0, 1.0)
        keyword_score = round(ratio * 70)

    total = max(0, min(100, keyword_score + formatting_score))

    return ATSResult(
        score=total,
        matched_keywords=matched,
        missing_keywords=missing,
        formatting_notes=formatting_notes,
        section_notes=section_notes,
    )
