"""
Job search aggregation.

- Real listings: pulled from Adzuna's public Job Search API (free tier,
  requires an app_id/app_key — see README). Adzuna covers India and
  aggregates from many boards + company sites, and its `redirect_url`
  often points at the original posting/company site.
- Platform deep links: LinkedIn, Naukri, Unstop, and Indeed do not offer
  free public search APIs, and scraping logged-in/search-result pages
  violates their Terms of Service. Instead we generate a pre-filled
  search URL for each — the user clicks through and applies themselves.
- Official careers page: we generate a targeted Google search link
  ("<company> careers <role>") rather than guessing/scraping a URL,
  since company career-page structures vary too much to reliably infer.
"""
from __future__ import annotations

import hashlib
import os
import urllib.parse
from dataclasses import dataclass, field

import httpx

from .legitimacy import assess_posting


def make_job_id(source: str, title: str, company: str, apply_url: str) -> str:
    """
    Stable ID for a posting, used to recognize 'already applied' across
    separate searches (job boards don't give us a consistent ID we can rely on).
    """
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

    def __post_init__(self):
        if not self.job_id:
            self.job_id = make_job_id(self.source, self.title, self.company, self.apply_url)


def _deep_search_links(role: str, location: str) -> list[JobListing]:
    q = urllib.parse.quote_plus(role)
    loc = urllib.parse.quote_plus(location or "India")
    return [
        JobListing(
            source="LinkedIn (search)",
            title=f"Search LinkedIn for '{role}'",
            company="—",
            location=location or "India",
            apply_url=f"https://www.linkedin.com/jobs/search/?keywords={q}&location={loc}",
            description_snippet="LinkedIn doesn't allow automated applications — this opens a pre-filled search so you can review and apply manually.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct platform search link."],
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


async def _adzuna_search(role: str, location: str) -> list[dict]:
    app_id = os.getenv("ADZUNA_APP_ID", ADZUNA_APP_ID)
    app_key = os.getenv("ADZUNA_APP_KEY", ADZUNA_APP_KEY)
    country = os.getenv("ADZUNA_COUNTRY", ADZUNA_COUNTRY)
    if not (app_id and app_key):
        return []
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": role,
        "where": location or "",
        "results_per_page": 20,
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


async def search_jobs(role: str, location: str, resume_text: str | None = None) -> list[JobListing]:
    from .keyword_extractor import extract_keywords

    listings: list[JobListing] = []

    try:
        raw_results = await _adzuna_search(role, location)
    except httpx.HTTPError:
        raw_results = []

    for item in raw_results:
        title = item.get("title", "")
        company = (item.get("company") or {}).get("display_name", "Unknown")
        loc = (item.get("location") or {}).get("display_name", location or "India")
        apply_url = item.get("redirect_url", "")
        description = item.get("description", "")

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
        ))

        # Also surface an official-careers-page search link alongside it.
        listings.append(JobListing(
            source=f"{company} — official careers page (search)",
            title=f"Find '{title}' directly on {company}'s site",
            company=company,
            location=loc,
            apply_url=_careers_page_search_link(company, role),
            description_snippet="Applying directly on the company's own careers page is often preferred over third-party job boards.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Points to a search for the company's own domain, not a third-party listing."],
        ))

    listings.extend(_deep_search_links(role, location))
    return listings
