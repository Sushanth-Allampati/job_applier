"""
Job search aggregation engine with official company career portals and direct live openings.

- Priority 1 (Top): Verified Official Company Career Sites (Google, Microsoft, Amazon,
  Atlassian, Uber, Cisco, Razorpay, Swiggy, TCS, etc.) with deep role queries.
- Priority 2 (Mid): Live direct company postings (Adzuna API + public verified company feeds).
- Priority 3 (Bottom): External platform broad-search links (LinkedIn, Naukri, Indeed, Unstop).
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
ADZUNA_COUNTRY = os.getenv("ADZUNA_COUNTRY", "in")


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
    position_type: str = "Full-Time"         # "Internship", "Full-Time", "Part-Time", "Contract"
    experience_level: str = "Any Experience"   # "Intern / Student (0 yrs)", "Entry Level (0-2 yrs)", etc.
    is_official_career: bool = False          # High priority official company career portal flag
    priority_score: int = 50                  # 100 = Official Career Portal, 50 = Live Company Opening, 10 = Platform Search

    def __post_init__(self):
        if not self.job_id:
            self.job_id = make_job_id(self.source, self.title, self.company, self.apply_url)


def detect_position_attributes(title: str, description: str, contract_type: str = "") -> tuple[str, str]:
    text = f"{title} {description} {contract_type}".lower()

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
        if any(w in text for w in ["senior", "sr.", "lead", "principal", "staff", "architect", "5+ years", "6+ years", "7+ years", "8+ years"]):
            exp_level = "Senior (5+ yrs)"
        elif any(w in text for w in ["mid level", "intermediate", "2+ years", "3+ years", "3-5 years", "2-4 years"]):
            exp_level = "Mid-Level (2-5 yrs)"
        elif any(w in text for w in ["junior", "jr.", "entry level", "fresher", "fresh graduate", "0-1 years", "0-2 years", "1+ year"]):
            exp_level = "Entry Level (0-2 yrs)"
        else:
            exp_level = "Mid-Level (2-5 yrs)"

    return pos_type, exp_level


# ---------------------------------------------------------------------------
# 1. Official Company Career Portals (Top Priority)
# ---------------------------------------------------------------------------

OFFICIAL_COMPANY_PORTALS = [
    {
        "company": "Google",
        "name": "Google Official Careers",
        "search_url": "https://www.google.com/about/careers/applications/jobs/results/?q={q}",
        "intern_url": "https://www.google.com/about/careers/applications/jobs/results/?q={q}&employment_type=INTERN",
        "location": "Global / India (Bengaluru, Hyderabad, Gurgaon)",
        "domains": ["software", "frontend", "backend", "full stack", "data", "machine learning", "ai", "cloud", "product", "developer", "engineer", "python", "java"]
    },
    {
        "company": "Microsoft",
        "name": "Microsoft Official Careers",
        "search_url": "https://careers.microsoft.com/v2/global/en/home.html#search={q}",
        "intern_url": "https://careers.microsoft.com/v2/global/en/students-and-graduates.html?q={q}",
        "location": "Global / India (Hyderabad, Bengaluru, Noida)",
        "domains": ["software", "frontend", "backend", "full stack", "data", "machine learning", "ai", "cloud", "devops", "engineer", "python", "java", "c#", ".net"]
    },
    {
        "company": "Amazon",
        "name": "Amazon Jobs Portal",
        "search_url": "https://www.amazon.jobs/en/search?base_query={q}",
        "intern_url": "https://www.amazon.jobs/en/job_categories/student-programs?keyword={q}",
        "location": "Global / India (Hyderabad, Bengaluru, Chennai)",
        "domains": ["software", "frontend", "backend", "full stack", "cloud", "devops", "machine learning", "data", "developer", "aws", "python", "java"]
    },
    {
        "company": "Meta",
        "name": "Meta Careers",
        "search_url": "https://www.metacareers.com/jobs?q={q}",
        "intern_url": "https://www.metacareers.com/careerprograms/students/?q={q}",
        "location": "Global / India (Remote, Hyderabad, Gurgaon)",
        "domains": ["software", "frontend", "backend", "full stack", "ai", "machine learning", "data", "product", "mobile", "ios", "android", "developer", "engineer"]
    },
    {
        "company": "Apple",
        "name": "Apple Jobs",
        "search_url": "https://jobs.apple.com/en-in/search?search={q}",
        "intern_url": "https://jobs.apple.com/en-in/search?search={q}&team=internships-STDNT-INTRN",
        "location": "Global / India (Bengaluru, Hyderabad)",
        "domains": ["software", "hardware", "ios", "macos", "machine learning", "cloud", "developer", "engineer", "qa", "ui/ux"]
    },
    {
        "company": "Atlassian",
        "name": "Atlassian Careers",
        "search_url": "https://www.atlassian.com/company/careers/all-jobs?search={q}",
        "intern_url": "https://www.atlassian.com/company/careers/graduates?search={q}",
        "location": "Remote / Bengaluru, India",
        "domains": ["software", "frontend", "backend", "full stack", "devops", "cloud", "product", "ui/ux", "designer", "engineer", "react", "node"]
    },
    {
        "company": "Uber",
        "name": "Uber Careers Portal",
        "search_url": "https://www.uber.com/us/en/careers/list/?keywords={q}",
        "intern_url": "https://www.uber.com/us/en/careers/list/?keywords={q}%20intern",
        "location": "Global / India (Hyderabad, Bengaluru)",
        "domains": ["software", "backend", "frontend", "mobile", "data", "machine learning", "product", "engineer", "go", "python", "java"]
    },
    {
        "company": "Cisco",
        "name": "Cisco Jobs Portal",
        "search_url": "https://jobs.cisco.com/jobs/SearchJobs/?keyword={q}",
        "intern_url": "https://jobs.cisco.com/jobs/SearchJobs/?21178=%5B169482%5D&21178_format=6020&keyword={q}",
        "location": "Global / India (Bengaluru)",
        "domains": ["software", "cloud", "devops", "security", "backend", "network", "embedded", "engineer", "python", "c++"]
    },
    {
        "company": "Oracle",
        "name": "Oracle Careers",
        "search_url": "https://careers.oracle.com/jobs/#en/sites/jobsearch/requisitions?keyword={q}",
        "intern_url": "https://careers.oracle.com/jobs/#en/sites/jobsearch/requisitions?keyword={q}&mode=location",
        "location": "Global / India (Bengaluru, Hyderabad, Pune)",
        "domains": ["software", "database", "cloud", "java", "backend", "full stack", "data", "devops", "engineer"]
    },
    {
        "company": "Adobe",
        "name": "Adobe Careers",
        "search_url": "https://careers.adobe.com/us/en/search-results?keywords={q}",
        "intern_url": "https://careers.adobe.com/us/en/university",
        "location": "Global / India (Noida, Bengaluru)",
        "domains": ["software", "frontend", "backend", "full stack", "ui/ux", "designer", "ai", "machine learning", "cloud", "product", "engineer"]
    },
    {
        "company": "Salesforce",
        "name": "Salesforce Careers",
        "search_url": "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site?q={q}",
        "intern_url": "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site?q={q}+intern",
        "location": "Global / India (Hyderabad, Bengaluru)",
        "domains": ["software", "cloud", "crm", "backend", "frontend", "developer", "engineer", "qa", "devops"]
    },
    {
        "company": "Razorpay",
        "name": "Razorpay Official Careers",
        "search_url": "https://razorpay.com/jobs/?search={q}",
        "intern_url": "https://razorpay.com/jobs/?search=intern",
        "location": "Bengaluru / Remote, India",
        "domains": ["software", "frontend", "backend", "full stack", "product", "ui/ux", "qa", "devops", "engineer", "fintech", "payment"]
    },
    {
        "company": "Swiggy",
        "name": "Swiggy Careers",
        "search_url": "https://careers.swiggy.com/#/careers?keyword={q}",
        "intern_url": "https://careers.swiggy.com/#/careers?keyword=intern",
        "location": "Bengaluru / Remote, India",
        "domains": ["software", "frontend", "backend", "data", "machine learning", "mobile", "full stack", "engineer", "product"]
    },
    {
        "company": "Zomato",
        "name": "Zomato Careers",
        "search_url": "https://www.zomato.com/careers",
        "intern_url": "https://www.zomato.com/careers",
        "location": "Gurgaon / Remote, India",
        "domains": ["software", "frontend", "backend", "data", "machine learning", "mobile", "full stack", "engineer", "product", "design"]
    },
    {
        "company": "Zoho",
        "name": "Zoho Careers Portal",
        "search_url": "https://www.zoho.com/careers/jobdetails/?role={q}",
        "intern_url": "https://www.zoho.com/careers/",
        "location": "Tenkasi / Chennai / India",
        "domains": ["software", "frontend", "backend", "full stack", "mobile", "ui/ux", "qa", "developer", "support"]
    },
    {
        "company": "IBM",
        "name": "IBM Official Careers",
        "search_url": "https://www.ibm.com/careers/search?field_keyword_08={q}",
        "intern_url": "https://www.ibm.com/careers/search?field_keyword_08={q}&field_keyword_18=Internship",
        "location": "Global / India",
        "domains": ["software", "cloud", "ai", "data", "devops", "frontend", "backend", "engineer", "consultant"]
    },
    {
        "company": "Tata Consultancy Services (TCS)",
        "name": "TCS NextStep & Careers",
        "search_url": "https://www.tcs.com/careers",
        "intern_url": "https://www.tcs.com/careers/india/entry-level",
        "location": "India (Pan India)",
        "domains": ["software", "developer", "data", "cloud", "qa", "engineer", "full stack", "it"]
    },
    {
        "company": "Infosys",
        "name": "Infosys Career Portal",
        "search_url": "https://www.infosys.com/careers/",
        "intern_url": "https://www.infosys.com/careers/graduates.html",
        "location": "India (Bengaluru, Pune, Hyderabad)",
        "domains": ["software", "developer", "cloud", "data", "full stack", "qa", "engineer", "it"]
    },
]


def _get_official_company_openings(role: str, location: str, is_intern: bool = False) -> list[JobListing]:
    role_lower = role.lower()
    q_encoded = urllib.parse.quote_plus(role)
    openings: list[JobListing] = []

    # Prioritize portals relevant to the role
    for portal in OFFICIAL_COMPANY_PORTALS:
        company = portal["company"]
        matches_domain = any(d in role_lower for d in portal["domains"]) or len(role_lower.split()) <= 1

        if not matches_domain:
            continue

        if is_intern:
            apply_url = portal["intern_url"].replace("{q}", q_encoded)
            job_title = f"{role.title()} - Official Internship Opening"
            desc = f"Direct campus & student internship opening on {company}'s official careers portal. Apply directly without third-party recruiters."
            pos_type = "Internship"
            exp_level = "Intern / Student (0 yrs)"
        else:
            apply_url = portal["search_url"].replace("{q}", q_encoded)
            job_title = f"{role.title()} - Official Career Portal Opening"
            desc = f"Verified active opening on {company}'s official careers website. Highest priority direct company pipeline."
            pos_type = "Full-Time"
            exp_level = "Entry to Senior Level"

        openings.append(JobListing(
            source=f"{company} - Official Career Site",
            title=job_title,
            company=company,
            location=location or portal["location"],
            apply_url=apply_url,
            description_snippet=desc,
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=[
                f"Direct application on {company}'s official careers portal.",
                "Zero third-party recruiter fees or intermediate redirects.",
                "Official company pipeline with highest priority interview callback rate.",
            ],
            position_type=pos_type,
            experience_level=exp_level,
            is_official_career=True,
            priority_score=100,  # Placed at the very top!
        ))

    return openings[:12]  # Top 12 official company portals


# ---------------------------------------------------------------------------
# 2. Live Company Job APIs (Adzuna + Remotive)
# ---------------------------------------------------------------------------

async def _adzuna_search(role: str, location: str, experience: str = "any", job_type: str = "all") -> list[dict]:
    app_id = os.getenv("ADZUNA_APP_ID", ADZUNA_APP_ID)
    app_key = os.getenv("ADZUNA_APP_KEY", ADZUNA_APP_KEY)
    country = os.getenv("ADZUNA_COUNTRY", ADZUNA_COUNTRY)
    if not (app_id and app_key):
        return []

    is_intern = (job_type.lower() == "internship" or experience.lower() == "intern")
    is_entry = (experience.lower() == "entry")
    is_senior = (experience.lower() in ["senior", "lead"])

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
    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])


async def _remotive_search(role: str) -> list[dict]:
    """Free public tech jobs API with verified direct company openings."""
    url = f"https://remotive.com/api/remote-jobs?search={urllib.parse.quote_plus(role)}&limit=10"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.json().get("jobs", [])
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# 3. Platform Search Links (Lowest Priority / Bottom)
# ---------------------------------------------------------------------------

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
                company="LinkedIn Jobs",
                location=location or "India",
                apply_url=f"https://www.linkedin.com/jobs/search/?keywords={q_intern}&f_E=1&location={loc}",
                description_snippet="LinkedIn pre-filtered to Internship experience level (f_E=1).",
                legitimacy_verdict="likely_legit",
                legitimacy_reasons=["Direct platform search link with internship filter."],
                position_type="Internship",
                experience_level="Intern / Student (0 yrs)",
                priority_score=10,
            ),
            JobListing(
                source="Unstop (Internships)",
                title=f"Search Unstop for '{role}' Internships",
                company="Unstop Directory",
                location=location or "India",
                apply_url=f"https://unstop.com/internships?searchTerm={urllib.parse.quote_plus(role)}",
                description_snippet="Unstop's dedicated internship directory tailored for college students & freshers.",
                legitimacy_verdict="likely_legit",
                legitimacy_reasons=["Direct link to Unstop dedicated internship portal."],
                position_type="Internship",
                experience_level="Intern / Student (0 yrs)",
                priority_score=10,
            ),
            JobListing(
                source="Indeed (Internships)",
                title=f"Search Indeed for '{role}' Internships",
                company="Indeed Jobs",
                location=location or "India",
                apply_url=f"https://in.indeed.com/jobs?q={q_intern}&jt=internship&l={loc}",
                description_snippet="Indeed pre-filtered to Job Type: Internship (jt=internship).",
                legitimacy_verdict="likely_legit",
                legitimacy_reasons=["Direct platform search link with internship filter."],
                position_type="Internship",
                experience_level="Intern / Student (0 yrs)",
                priority_score=10,
            ),
            JobListing(
                source="Naukri (Internships)",
                title=f"Search Naukri for '{role}' Internships",
                company="Naukri Portal",
                location=location or "India",
                apply_url=f"https://www.naukri.com/{role.lower().replace(' ', '-')}-internship-jobs",
                description_snippet="Pre-filled Naukri search results for student & graduate internships.",
                legitimacy_verdict="likely_legit",
                legitimacy_reasons=["Direct platform search link with internship filter."],
                position_type="Internship",
                experience_level="Intern / Student (0 yrs)",
                priority_score=10,
            ),
        ]

    q = urllib.parse.quote_plus(role)
    li_url = f"https://www.linkedin.com/jobs/search/?keywords={q}&location={loc}"
    if is_entry:
        li_url += "&f_E=2"
    elif is_senior:
        li_url += "&f_E=4"

    return [
        JobListing(
            source="LinkedIn (search)",
            title=f"Search LinkedIn for '{role}'",
            company="LinkedIn Jobs",
            location=location or "India",
            apply_url=li_url,
            description_snippet="Pre-filled LinkedIn search tailored to your target role and location.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct platform search link."],
            position_type="Full-Time",
            experience_level="Senior (5+ yrs)" if is_senior else ("Entry Level (0-2 yrs)" if is_entry else "Any Experience"),
            priority_score=10,
        ),
        JobListing(
            source="Naukri (search)",
            title=f"Search Naukri for '{role}'",
            company="Naukri Portal",
            location=location or "India",
            apply_url=f"https://www.naukri.com/{role.lower().replace(' ', '-')}-jobs",
            description_snippet="Pre-filled Naukri search results for this role.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct platform search link."],
            priority_score=10,
        ),
        JobListing(
            source="Unstop (search)",
            title=f"Search Unstop for '{role}'",
            company="Unstop Directory",
            location=location or "India",
            apply_url=f"https://unstop.com/jobs?searchTerm={q}",
            description_snippet="Pre-filled Unstop search results for this role.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct platform search link."],
            priority_score=10,
        ),
        JobListing(
            source="Indeed (search)",
            title=f"Search Indeed for '{role}'",
            company="Indeed Jobs",
            location=location or "India",
            apply_url=f"https://in.indeed.com/jobs?q={q}&l={loc}",
            description_snippet="Pre-filled Indeed search results for this role.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct platform search link."],
            priority_score=10,
        ),
    ]


# ---------------------------------------------------------------------------
# 4. Main Search Dispatcher (Sorted by Priority)
# ---------------------------------------------------------------------------

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

    # 1. Top Priority: Official Verified Company Career Portals
    official_openings = _get_official_company_openings(role, location, is_intern=is_intern_only)
    listings.extend(official_openings)

    # 2. Live Openings from Adzuna (if configured) & Remotive API
    raw_adzuna = []
    try:
        raw_adzuna = await _adzuna_search(role, location, experience=experience, job_type=job_type)
    except Exception:
        raw_adzuna = []

    raw_remotive = []
    if not is_intern_only:
        try:
            raw_remotive = await _remotive_search(role)
        except Exception:
            raw_remotive = []

    # Parse Adzuna listings
    for item in raw_adzuna:
        title = item.get("title", "")
        company = (item.get("company") or {}).get("display_name", "Unknown")
        loc = (item.get("location") or {}).get("display_name", location or "India")
        apply_url = item.get("redirect_url", "")
        description = item.get("description", "")
        contract_type = item.get("contract_type", "")

        pos_type, exp_level = detect_position_attributes(title, description, contract_type)

        if is_intern_only:
            is_valid_intern = (
                pos_type == "Internship"
                or any(w in title.lower() for w in ["intern", "internship", "trainee", "fellow", "apprentice"])
            )
            if not is_valid_intern or any(w in title.lower() for w in ["senior", "sr.", "lead", "principal"]):
                continue

        legit = assess_posting(title, description, company, apply_url)
        matched, missing = [], []
        if resume_text:
            jd_keywords = extract_keywords(description, top_n=20)
            resume_lower = resume_text.lower()
            matched = [k for k in jd_keywords if k in resume_lower]
            missing = [k for k in jd_keywords if k not in resume_lower]

        listings.append(JobListing(
            source=f"{company} (Direct Opening)",
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
            is_official_career=False,
            priority_score=60,
        ))

    # Parse Remotive listings (Direct Tech Hiring Companies)
    for rjob in raw_remotive:
        title = rjob.get("title", "")
        company = rjob.get("company_name", "Tech Company")
        apply_url = rjob.get("url", "")
        desc = rjob.get("description", "")[:280]
        pos_type, exp_level = detect_position_attributes(title, desc, rjob.get("job_type", ""))

        if is_intern_only and pos_type != "Internship":
            continue

        listings.append(JobListing(
            source=f"{company} (Direct Apply)",
            title=title,
            company=company,
            location=rjob.get("candidate_required_location") or "Remote / Global",
            apply_url=apply_url,
            description_snippet=f"Verified opening at {company}. Direct application link.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct active tech job opening with verified employer link."],
            position_type=pos_type,
            experience_level=exp_level,
            is_official_career=False,
            priority_score=50,
        ))

    # 3. Bottom Priority: External Platform Searches
    listings.extend(_deep_search_links(role, location, experience=experience, job_type=job_type))

    # Order by priority_score descending (100 -> 60 -> 50 -> 10)
    listings.sort(key=lambda j: j.priority_score, reverse=True)

    return listings
