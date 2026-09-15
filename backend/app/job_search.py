"""
Job search aggregation.

- Real listings: pulled from Adzuna's public Job Search API (free tier).
- Experience & Position Type filtering: Filters by Internship (0 yrs), Entry Level (0-2 yrs),
  Mid-Level (2-5 yrs), Senior Level (5+ yrs), plus contract/part-time.
- If 'intern' is selected, only genuine internships are surfaced and deep links
  target dedicated internship boards (e.g. Unstop internships, LinkedIn f_E=1, Indeed jt=internship).
"""
from __future__ import annotations

import hashlib
import os
import urllib.parse
from dataclasses import dataclass, field

import httpx

from .legitimacy import assess_posting


def make_job_id(source: str, title: str, company: str, apply_url: str) -> str:
    raw = f"{source}|{title}|{company}|{apply_url}".lower().strip()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")
ADZUNA_COUNTRY = os.getenv("ADZUNA_COUNTRY", "in")  # 'in' = India


@dataclass
class JobListing:
    source: str
    title: str
    company: str
    location: str
    apply_url: str
    description_snippet: str
    legitimacy_verdict: str
    legitimacy_reasons: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    job_id: str = ""
    already_applied: bool = False
    position_type: str = "Full-Time"       # "Internship", "Full-Time", "Part-Time", "Contract"
    experience_level: str = "Any Experience" # "Intern / Student (0 yrs)", "Entry Level (0-2 yrs)", etc.

    def __post_init__(self):
        if not self.job_id:
            self.job_id = make_job_id(self.source, self.title, self.company, self.apply_url)


def detect_position_attributes(title: str, description: str, contract_type: str = "") -> tuple[str, str]:
    """
    Infers position type (e.g., Internship, Full-Time) and experience level from
    job title, description, and metadata.
    """
    text = f"{title} {description} {contract_type}".lower()

    # 1. Position Type
    is_intern = any(w in text for w in ["intern", "internship", "trainee", "apprentice", "fellowship", "co-op", "summer intern"])
    is_contract = any(w in text for w in ["contract", "contractor", "freelance", "temporary", "consultant"])
    is_part_time = any(w in text for w in ["part-time", "part time"])

    if is_intern:
        pos_type = "Internship"
        exp_level = "Intern / Student (0 yrs)"
    elif is_contract:
        pos_type = "Contract"
        exp_level = "Flexible"
    elif is_part_time:
        pos_type = "Part-Time"
        exp_level = "Flexible"
    else:
        pos_type = "Full-Time"

        # 2. Experience Level detection
        if any(w in text for w in ["senior", "sr.", "lead", "principal", "staff", "architect", "5+ years", "6+ years", "7+ years", "8+ years"]):
            exp_level = "Senior (5+ yrs)"
        elif any(w in text for w in ["mid level", "intermediate", "2+ years", "3+ years", "3-5 years", "2-4 years"]):
            exp_level = "Mid-Level (2-5 yrs)"
        elif any(w in text for w in ["junior", "jr.", "entry level", "fresher", "fresh graduate", "0-1 years", "0-2 years", "1+ year"]):
            exp_level = "Entry Level (0-2 yrs)"
        else:
            exp_level = "Mid-Level (2-5 yrs)"

    return pos_type, exp_level


def _deep_search_links(role: str, location: str, experience: str = "any", job_type: str = "all") -> list[JobListing]:
    is_intern = (job_type.lower() == "internship" or experience.lower() == "intern")
    is_entry = (experience.lower() == "entry")
    is_senior = (experience.lower() in ["senior", "lead"])

    loc = urllib.parse.quote_plus(location or "India")

    if is_intern:
        q_intern = urllib.parse.quote_plus(f"{role} intern")
        return [
            JobListing(
                source="LinkedIn (Internships)",
                title=f"Search LinkedIn for '{role}' Internships",
                company="—",
                location=location or "India",
                apply_url=f"https://www.linkedin.com/jobs/search/?keywords={q_intern}&f_E=1&location={loc}",
                description_snippet="LinkedIn pre-filtered to Internship experience level (f_E=1).",
                legitimacy_verdict="likely_legit",
                legitimacy_reasons=["Direct platform search link with internship filter."],
                position_type="Internship",
                experience_level="Intern / Student (0 yrs)",
            ),
            JobListing(
                source="Unstop (Internships)",
                title=f"Search Unstop for '{role}' Internships",
                company="—",
                location=location or "India",
                apply_url=f"https://unstop.com/internships?searchTerm={urllib.parse.quote_plus(role)}",
                description_snippet="Unstop's dedicated internship directory tailored for college students & freshers.",
                legitimacy_verdict="likely_legit",
                legitimacy_reasons=["Direct link to Unstop dedicated internship portal."],
                position_type="Internship",
                experience_level="Intern / Student (0 yrs)",
            ),
            JobListing(
                source="Indeed (Internships)",
                title=f"Search Indeed for '{role}' Internships",
                company="—",
                location=location or "India",
                apply_url=f"https://in.indeed.com/jobs?q={q_intern}&jt=internship&l={loc}",
                description_snippet="Indeed pre-filtered to Job Type: Internship (jt=internship).",
                legitimacy_verdict="likely_legit",
                legitimacy_reasons=["Direct platform search link with internship filter."],
                position_type="Internship",
                experience_level="Intern / Student (0 yrs)",
            ),
            JobListing(
                source="Naukri (Internships)",
                title=f"Search Naukri for '{role}' Internships",
                company="—",
                location=location or "India",
                apply_url=f"https://www.naukri.com/{role.lower().replace(' ', '-')}-internship-jobs",
                description_snippet="Pre-filled Naukri search results for student & graduate internships.",
                legitimacy_verdict="likely_legit",
                legitimacy_reasons=["Direct platform search link with internship filter."],
                position_type="Internship",
                experience_level="Intern / Student (0 yrs)",
            ),
        ]

    # Standard / Experienced Search Links
    q = urllib.parse.quote_plus(role)
    li_url = f"https://www.linkedin.com/jobs/search/?keywords={q}&location={loc}"
    if is_entry:
        li_url += "&f_E=2" # Entry level
    elif is_senior:
        li_url += "&f_E=4" # Mid-Senior

    return [
        JobListing(
            source="LinkedIn (search)",
            title=f"Search LinkedIn for '{role}'",
            company="—",
            location=location or "India",
            apply_url=li_url,
            description_snippet="Pre-filled LinkedIn search tailored to your target role and location.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct platform search link."],
            position_type="Full-Time" if not is_intern else "Internship",
            experience_level="Senior (5+ yrs)" if is_senior else ("Entry Level (0-2 yrs)" if is_entry else "Any Experience"),
        ),
        JobListing(
            source="Naukri (search)",
            title=f"Search Naukri for '{role}'",
            company="—",
            location=location or "India",
            apply_url=f"https://www.naukri.com/{role.lower().replace(' ', '-')}-jobs",
            description_snippet="Pre-filled Naukri search results for this role.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct platform search link."],
        ),
        JobListing(
            source="Unstop (search)",
            title=f"Search Unstop for '{role}'",
            company="—",
            location=location or "India",
            apply_url=f"https://unstop.com/jobs?searchTerm={q}",
            description_snippet="Pre-filled Unstop search results for this role.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct platform search link."],
        ),
        JobListing(
            source="Indeed (search)",
            title=f"Search Indeed for '{role}'",
            company="—",
            location=location or "India",
            apply_url=f"https://in.indeed.com/jobs?q={q}&l={loc}",
            description_snippet="Pre-filled Indeed search results for this role.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct platform search link."],
        ),
    ]


async def _adzuna_search(role: str, location: str, experience: str = "any", job_type: str = "all") -> list[dict]:
    app_id = os.getenv("ADZUNA_APP_ID", ADZUNA_APP_ID)
    app_key = os.getenv("ADZUNA_APP_KEY", ADZUNA_APP_KEY)
    country = os.getenv("ADZUNA_COUNTRY", ADZUNA_COUNTRY)
    if not (app_id and app_key):
        return []

    is_intern = (job_type.lower() == "internship" or experience.lower() == "intern")
    is_entry = (experience.lower() == "entry")
    is_senior = (experience.lower() in ["senior", "lead"])

    # Adapt query based on role and position type
    if is_intern:
        query_text = f"{role} intern"
    elif is_senior:
        query_text = f"senior {role}"
    elif is_entry:
        query_text = f"junior {role}"
    else:
        query_text = role

    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": query_text,
        "where": location or "",
        "results_per_page": 25,
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])


def _careers_page_search_link(company: str, role: str) -> str:
    q = urllib.parse.quote_plus(f"{company} careers {role}")
    return f"https://www.google.com/search?q={q}"


async def search_jobs(
    role: str,
    location: str,
    experience: str = "any",
    job_type: str = "all",
    resume_text: str | None = None,
) -> list[JobListing]:
    from .keyword_extractor import extract_keywords

    is_intern_only = (job_type.lower() == "internship" or experience.lower() == "intern")
    is_entry_only = (experience.lower() == "entry")
    is_senior_only = (experience.lower() in ["senior", "lead"])

    listings: list[JobListing] = []

    try:
        raw_results = await _adzuna_search(role, location, experience=experience, job_type=job_type)
    except httpx.HTTPError:
        raw_results = []

    for item in raw_results:
        title = item.get("title", "")
        company = (item.get("company") or {}).get("display_name", "Unknown")
        loc = (item.get("location") or {}).get("display_name", location or "India")
        apply_url = item.get("redirect_url", "")
        description = item.get("description", "")
        contract_type = item.get("contract_type", "")

        pos_type, exp_level = detect_position_attributes(title, description, contract_type)

        # STRICT FILTERING when user selects 'Intern' or 'Internship'
        if is_intern_only:
            # If user selected Intern, only allow internships / trainees and exclude senior/lead
            is_valid_intern = (
                pos_type == "Internship"
                or any(w in title.lower() for w in ["intern", "internship", "trainee", "fellow", "apprentice"])
                or any(w in description.lower() for w in ["internship", "intern position", "summer intern", "hiring interns"])
            )
            is_senior_title = any(w in title.lower() for w in ["senior", "sr.", "lead", "principal", "director", "manager"])
            if not is_valid_intern or is_senior_title:
                continue

        elif is_entry_only:
            # Filter out Senior / Lead roles when user requests Entry Level
            if any(w in title.lower() for w in ["senior", "sr.", "lead", "principal", "director", "architect"]):
                continue

        elif is_senior_only:
            # Filter out Junior / Intern roles when user requests Senior Level
            if any(w in title.lower() for w in ["junior", "jr.", "intern", "internship", "trainee"]):
                continue

        legit = assess_posting(title, description, company, apply_url)

        matched, missing = [], []
        if resume_text:
            jd_keywords = extract_keywords(description, top_n=20)
            resume_lower = resume_text.lower()
            matched = [k for k in jd_keywords if k in resume_lower]
            missing = [k for k in jd_keywords if k not in resume_lower]

        listings.append(JobListing(
            source="Adzuna aggregator",
            title=title,
            company=company,
            location=loc,
            apply_url=apply_url,
            description_snippet=description[:280],
            legitimacy_verdict=legit.verdict,
            legitimacy_reasons=legit.reasons,
            matched_keywords=matched,
            missing_keywords=missing,
            position_type=pos_type,
            experience_level=exp_level,
        ))

        # Official careers page search link
        search_term = f"{role} intern" if is_intern_only else role
        listings.append(JobListing(
            source=f"{company} — official careers page",
            title=f"Find '{title}' directly on {company}'s site",
            company=company,
            location=loc,
            apply_url=_careers_page_search_link(company, search_term),
            description_snippet=f"Apply directly on {company}'s official careers portal.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Points to a search for the company's official domain."],
            position_type=pos_type,
            experience_level=exp_level,
        ))

    # Add targeted platform deep search links
    listings.extend(_deep_search_links(role, location, experience=experience, job_type=job_type))
    return listings
