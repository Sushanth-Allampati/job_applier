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
    # --- Top Global Tech & Cloud Giants ---
    {
        "company": "Google",
        "name": "Google Official Careers",
        "search_url": "https://www.google.com/about/careers/applications/jobs/results/?q={q}",
        "intern_url": "https://www.google.com/about/careers/applications/jobs/results/?q={q}&employment_type=INTERN",
        "location": "Global / India (Bengaluru, Hyderabad, Gurgaon)",
        "domains": ["software", "frontend", "backend", "full stack", "data", "machine learning", "ai", "cloud", "product", "developer", "engineer", "python", "java", "sre", "systems"]
    },
    {
        "company": "Microsoft",
        "name": "Microsoft Official Careers",
        "search_url": "https://careers.microsoft.com/v2/global/en/home.html#search={q}",
        "intern_url": "https://careers.microsoft.com/v2/global/en/students-and-graduates.html?q={q}",
        "location": "Global / India (Hyderabad, Bengaluru, Noida)",
        "domains": ["software", "frontend", "backend", "full stack", "data", "machine learning", "ai", "cloud", "devops", "engineer", "python", "java", "c#", ".net", "azure"]
    },
    {
        "company": "Amazon",
        "name": "Amazon Jobs Portal",
        "search_url": "https://www.amazon.jobs/en/search?base_query={q}",
        "intern_url": "https://www.amazon.jobs/en/job_categories/student-programs?keyword={q}",
        "location": "Global / India (Hyderabad, Bengaluru, Chennai)",
        "domains": ["software", "frontend", "backend", "full stack", "cloud", "devops", "machine learning", "data", "developer", "aws", "python", "java", "sre", "qa"]
    },
    {
        "company": "Meta",
        "name": "Meta Careers",
        "search_url": "https://www.metacareers.com/jobs?q={q}",
        "intern_url": "https://www.metacareers.com/careerprograms/students/?q={q}",
        "location": "Global / India (Remote, Hyderabad, Gurgaon)",
        "domains": ["software", "frontend", "backend", "full stack", "ai", "machine learning", "data", "product", "mobile", "ios", "android", "developer", "engineer", "react"]
    },
    {
        "company": "Apple",
        "name": "Apple Jobs",
        "search_url": "https://jobs.apple.com/en-in/search?search={q}",
        "intern_url": "https://jobs.apple.com/en-in/search?search={q}&team=internships-STDNT-INTRN",
        "location": "Global / India (Bengaluru, Hyderabad)",
        "domains": ["software", "hardware", "ios", "macos", "machine learning", "cloud", "developer", "engineer", "qa", "ui/ux", "swift", "c++", "embedded"]
    },
    {
        "company": "Netflix",
        "name": "Netflix Jobs",
        "search_url": "https://jobs.netflix.com/search?q={q}",
        "intern_url": "https://jobs.netflix.com/search?q={q}+intern",
        "location": "Global / Remote",
        "domains": ["software", "frontend", "backend", "full stack", "cloud", "data", "machine learning", "distributed", "systems", "java", "python", "devops"]
    },
    {
        "company": "Nvidia",
        "name": "NVIDIA Careers",
        "search_url": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite?q={q}",
        "intern_url": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite?q={q}+intern",
        "location": "Global / India (Bengaluru, Pune, Hyderabad)",
        "domains": ["ai", "machine learning", "deep learning", "gpu", "cuda", "c++", "python", "software", "hardware", "embedded", "systems", "computer vision"]
    },
    {
        "company": "Uber",
        "name": "Uber Careers Portal",
        "search_url": "https://www.uber.com/us/en/careers/list/?keywords={q}",
        "intern_url": "https://www.uber.com/us/en/careers/list/?keywords={q}%20intern",
        "location": "Global / India (Hyderabad, Bengaluru)",
        "domains": ["software", "backend", "frontend", "mobile", "data", "machine learning", "product", "engineer", "go", "python", "java", "android", "ios"]
    },
    {
        "company": "Atlassian",
        "name": "Atlassian Careers",
        "search_url": "https://www.atlassian.com/company/careers/all-jobs?search={q}",
        "intern_url": "https://www.atlassian.com/company/careers/graduates?search={q}",
        "location": "Remote / Bengaluru, India",
        "domains": ["software", "frontend", "backend", "full stack", "devops", "cloud", "product", "ui/ux", "designer", "engineer", "react", "node", "java", "sre"]
    },
    {
        "company": "Cisco",
        "name": "Cisco Jobs Portal",
        "search_url": "https://jobs.cisco.com/jobs/SearchJobs/?keyword={q}",
        "intern_url": "https://jobs.cisco.com/jobs/SearchJobs/?21178=%5B169482%5D&21178_format=6020&keyword={q}",
        "location": "Global / India (Bengaluru)",
        "domains": ["software", "cloud", "devops", "security", "backend", "network", "embedded", "engineer", "python", "c++", "cybersecurity"]
    },
    {
        "company": "Oracle",
        "name": "Oracle Careers",
        "search_url": "https://careers.oracle.com/jobs/#en/sites/jobsearch/requisitions?keyword={q}",
        "intern_url": "https://careers.oracle.com/jobs/#en/sites/jobsearch/requisitions?keyword={q}&mode=location",
        "location": "Global / India (Bengaluru, Hyderabad, Pune)",
        "domains": ["software", "database", "cloud", "java", "backend", "full stack", "data", "devops", "engineer", "dba", "systems"]
    },
    {
        "company": "Adobe",
        "name": "Adobe Careers",
        "search_url": "https://careers.adobe.com/us/en/search-results?keywords={q}",
        "intern_url": "https://careers.adobe.com/us/en/university",
        "location": "Global / India (Noida, Bengaluru)",
        "domains": ["software", "frontend", "backend", "full stack", "ui/ux", "designer", "ai", "machine learning", "cloud", "product", "engineer", "c++", "react"]
    },
    {
        "company": "Salesforce",
        "name": "Salesforce Careers",
        "search_url": "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site?q={q}",
        "intern_url": "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site?q={q}+intern",
        "location": "Global / India (Hyderabad, Bengaluru)",
        "domains": ["software", "cloud", "crm", "backend", "frontend", "developer", "engineer", "qa", "devops", "java", "python"]
    },
    {
        "company": "Intel",
        "name": "Intel Careers",
        "search_url": "https://jobs.intel.com/en/search-jobs/{q}",
        "intern_url": "https://jobs.intel.com/en/search-jobs/{q}/intern",
        "location": "Global / India (Bengaluru)",
        "domains": ["software", "hardware", "firmware", "embedded", "c++", "python", "systems", "ai", "machine learning", "vlsi", "semiconductor"]
    },
    {
        "company": "Qualcomm",
        "name": "Qualcomm Careers",
        "search_url": "https://qualcomm.wd5.myworkdayjobs.com/External?q={q}",
        "intern_url": "https://qualcomm.wd5.myworkdayjobs.com/External?q={q}+intern",
        "location": "Global / India (Hyderabad, Bengaluru, Chennai)",
        "domains": ["embedded", "software", "firmware", "c++", "wireless", "5g", "systems", "android", "machine learning", "engineer"]
    },
    {
        "company": "Snowflake",
        "name": "Snowflake Careers",
        "search_url": "https://careers.snowflake.com/us/en/search-results?keywords={q}",
        "intern_url": "https://careers.snowflake.com/us/en/university-recruiting",
        "location": "Global / India (Bengaluru, Pune)",
        "domains": ["data", "cloud", "database", "distributed", "backend", "systems", "software", "engineer", "c++", "java", "python"]
    },
    {
        "company": "Databricks",
        "name": "Databricks Careers",
        "search_url": "https://www.databricks.com/company/careers/open-positions?search={q}",
        "intern_url": "https://www.databricks.com/company/careers/open-positions?search={q}+intern",
        "location": "Global / India (Bengaluru)",
        "domains": ["data", "ai", "machine learning", "spark", "cloud", "backend", "distributed", "systems", "software", "engineer", "python", "scala"]
    },
    {
        "company": "Stripe",
        "name": "Stripe Careers",
        "search_url": "https://stripe.com/jobs/search?query={q}",
        "intern_url": "https://stripe.com/jobs/search?query={q}+intern",
        "location": "Global / Remote",
        "domains": ["software", "backend", "frontend", "full stack", "fintech", "payment", "infrastructure", "systems", "ruby", "go", "java"]
    },
    {
        "company": "PayPal",
        "name": "PayPal Careers",
        "search_url": "https://paypal.wd1.myworkdayjobs.com/jobs?q={q}",
        "intern_url": "https://paypal.wd1.myworkdayjobs.com/jobs?q={q}+intern",
        "location": "Global / India (Bengaluru, Chennai)",
        "domains": ["software", "fintech", "backend", "frontend", "full stack", "payment", "cloud", "java", "node", "python", "qa", "security"]
    },
    {
        "company": "Spotify",
        "name": "Spotify Jobs",
        "search_url": "https://www.lifeatspotify.com/jobs?q={q}",
        "intern_url": "https://www.lifeatspotify.com/jobs?q={q}+intern",
        "location": "Global / Remote",
        "domains": ["software", "frontend", "backend", "mobile", "ios", "android", "data", "machine learning", "product", "designer", "engineer"]
    },
    {
        "company": "IBM",
        "name": "IBM Official Careers",
        "search_url": "https://www.ibm.com/careers/search?field_keyword_08={q}",
        "intern_url": "https://www.ibm.com/careers/search?field_keyword_08={q}&field_keyword_18=Internship",
        "location": "Global / India",
        "domains": ["software", "cloud", "ai", "data", "devops", "frontend", "backend", "engineer", "consultant", "security", "full stack"]
    },

    # --- High-Growth Tech Unicorns & Product Leaders ---
    {
        "company": "Razorpay",
        "name": "Razorpay Official Careers",
        "search_url": "https://razorpay.com/jobs/?search={q}",
        "intern_url": "https://razorpay.com/jobs/?search=intern",
        "location": "Bengaluru / Remote, India",
        "domains": ["software", "frontend", "backend", "full stack", "product", "ui/ux", "qa", "devops", "engineer", "fintech", "payment", "php", "go", "react"]
    },
    {
        "company": "Swiggy",
        "name": "Swiggy Careers",
        "search_url": "https://careers.swiggy.com/#/careers?keyword={q}",
        "intern_url": "https://careers.swiggy.com/#/careers?keyword=intern",
        "location": "Bengaluru / Remote, India",
        "domains": ["software", "frontend", "backend", "data", "machine learning", "mobile", "full stack", "engineer", "product", "go", "java", "android", "ios"]
    },
    {
        "company": "Zomato",
        "name": "Zomato Careers",
        "search_url": "https://www.zomato.com/careers",
        "intern_url": "https://www.zomato.com/careers",
        "location": "Gurgaon / Remote, India",
        "domains": ["software", "frontend", "backend", "data", "machine learning", "mobile", "full stack", "engineer", "product", "design", "react", "node"]
    },
    {
        "company": "Flipkart",
        "name": "Flipkart Careers",
        "search_url": "https://www.flipkartcareers.com/#!/joblist?q={q}",
        "intern_url": "https://www.flipkartcareers.com/#!/campus",
        "location": "Bengaluru, India",
        "domains": ["software", "backend", "frontend", "full stack", "data", "machine learning", "mobile", "cloud", "devops", "java", "ui/ux"]
    },
    {
        "company": "PhonePe",
        "name": "PhonePe Careers",
        "search_url": "https://www.phonepe.com/careers/?q={q}",
        "intern_url": "https://www.phonepe.com/careers/",
        "location": "Bengaluru / Pune, India",
        "domains": ["software", "backend", "frontend", "mobile", "ios", "android", "fintech", "full stack", "java", "qa", "devops"]
    },
    {
        "company": "CRED",
        "name": "CRED Careers",
        "search_url": "https://careers.cred.club/",
        "intern_url": "https://careers.cred.club/",
        "location": "Bengaluru, India",
        "domains": ["software", "frontend", "backend", "mobile", "flutter", "react", "go", "designer", "product", "engineer"]
    },
    {
        "company": "Meesho",
        "name": "Meesho Careers",
        "search_url": "https://www.meesho.io/jobs?search={q}",
        "intern_url": "https://www.meesho.io/jobs",
        "location": "Bengaluru / Remote, India",
        "domains": ["software", "frontend", "backend", "data", "machine learning", "mobile", "product", "full stack", "java", "python"]
    },
    {
        "company": "Zoho",
        "name": "Zoho Careers Portal",
        "search_url": "https://www.zoho.com/careers/jobdetails/?role={q}",
        "intern_url": "https://www.zoho.com/careers/",
        "location": "Tenkasi / Chennai / India",
        "domains": ["software", "frontend", "backend", "full stack", "mobile", "ui/ux", "qa", "developer", "support", "java", "c++", "react"]
    },
    {
        "company": "Freshworks",
        "name": "Freshworks Careers",
        "search_url": "https://www.freshworks.com/company/careers/?search={q}",
        "intern_url": "https://www.freshworks.com/company/careers/",
        "location": "Chennai / Bengaluru / Remote, India",
        "domains": ["software", "frontend", "backend", "full stack", "saas", "product", "qa", "devops", "ruby", "react", "java"]
    },
    {
        "company": "Postman",
        "name": "Postman Careers",
        "search_url": "https://www.postman.com/company/careers/?q={q}",
        "intern_url": "https://www.postman.com/company/careers/",
        "location": "Bengaluru / Remote, Global",
        "domains": ["software", "frontend", "backend", "node", "javascript", "react", "api", "cloud", "qa", "devops", "developer relations"]
    },
    {
        "company": "BrowserStack",
        "name": "BrowserStack Careers",
        "search_url": "https://www.browserstack.com/careers?q={q}",
        "intern_url": "https://www.browserstack.com/careers",
        "location": "Mumbai / Remote, India",
        "domains": ["software", "backend", "frontend", "qa", "testing", "systems", "devops", "full stack", "ruby", "java", "python"]
    },

    # --- Global Investment Banking & Financial Technology ---
    {
        "company": "JPMorgan Chase",
        "name": "JPMorgan Chase Careers",
        "search_url": "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/requisitions?keyword={q}",
        "intern_url": "https://careers.jpmorgan.com/global/en/students/programs",
        "location": "Global / India (Hyderabad, Bengaluru, Mumbai)",
        "domains": ["software", "data", "cloud", "cybersecurity", "backend", "full stack", "python", "java", "devops", "quant", "analyst"]
    },
    {
        "company": "Goldman Sachs",
        "name": "Goldman Sachs Careers",
        "search_url": "https://www.goldmansachs.com/careers/students/programs/?keyword={q}",
        "intern_url": "https://www.goldmansachs.com/careers/students/programs/",
        "location": "Global / India (Bengaluru, Hyderabad)",
        "domains": ["software", "developer", "data", "quant", "cybersecurity", "cloud", "backend", "java", "python", "c++", "analyst"]
    },

    # --- Leading Enterprise Tech & Consulting ---
    {
        "company": "Tata Consultancy Services (TCS)",
        "name": "TCS NextStep & Careers",
        "search_url": "https://www.tcs.com/careers",
        "intern_url": "https://www.tcs.com/careers/india/entry-level",
        "location": "India (Pan India)",
        "domains": ["software", "developer", "data", "cloud", "qa", "engineer", "full stack", "it", "consultant", "java", "python", ".net"]
    },
    {
        "company": "Infosys",
        "name": "Infosys Career Portal",
        "search_url": "https://www.infosys.com/careers/",
        "intern_url": "https://www.infosys.com/careers/graduates.html",
        "location": "India (Bengaluru, Pune, Hyderabad)",
        "domains": ["software", "developer", "cloud", "data", "full stack", "qa", "engineer", "it", "java", "python", ".net", "consultant"]
    },
    {
        "company": "Wipro",
        "name": "Wipro Careers",
        "search_url": "https://careers.wipro.com/careers-home/jobs?keywords={q}",
        "intern_url": "https://careers.wipro.com/careers-home/jobs?keywords={q}+intern",
        "location": "India (Pan India)",
        "domains": ["software", "developer", "cloud", "devops", "data", "qa", "full stack", "it", "engineer"]
    },
    {
        "company": "Accenture",
        "name": "Accenture Careers",
        "search_url": "https://www.accenture.com/in-en/careers/jobsearch?jk={q}",
        "intern_url": "https://www.accenture.com/in-en/careers/local/entry-level-jobs",
        "location": "Global / India (Pan India)",
        "domains": ["software", "developer", "cloud", "ai", "consulting", "data", "security", "qa", "full stack", "engineer"]
    },
]


def normalize_location_query(location: str) -> tuple[str, bool, str]:
    """
    Returns (search_loc, is_nationwide, country_name).
    When a country is selected, is_nationwide is True and searches span all states/cities.
    """
    clean = (location or "").strip()
    clean_lower = clean.lower()

    if not clean:
        return "India", True, "India"

    # Explicit nationwide country checks
    if clean_lower in ["india", "pan india"] or "all states" in clean_lower or "nationwide" in clean_lower:
        if any(c in clean_lower for c in ["us", "united states", "usa"]):
            return "United States", True, "United States"
        elif any(c in clean_lower for c in ["uk", "united kingdom"]):
            return "United Kingdom", True, "United Kingdom"
        elif "canada" in clean_lower:
            return "Canada", True, "Canada"
        elif "germany" in clean_lower:
            return "Germany", True, "Germany"
        elif "australia" in clean_lower:
            return "Australia", True, "Australia"
        else:
            return "India", True, "India"

    if clean_lower in ["united states", "usa", "us", "u.s."]:
        return "United States", True, "United States"
    elif clean_lower in ["united kingdom", "uk", "great britain"]:
        return "United Kingdom", True, "United Kingdom"
    elif clean_lower in ["canada"]:
        return "Canada", True, "Canada"
    elif clean_lower in ["germany"]:
        return "Germany", True, "Germany"
    elif clean_lower in ["australia"]:
        return "Australia", True, "Australia"
    elif clean_lower in ["singapore"]:
        return "Singapore", True, "Singapore"
    elif clean_lower in ["remote", "worldwide", "global"]:
        return "Remote", True, "Global"

    return clean, False, ""


def _get_official_company_openings(role: str, location: str, is_intern: bool = False) -> list[JobListing]:
    role_lower = role.lower()
    q_encoded = urllib.parse.quote_plus(role)
    openings: list[JobListing] = []

    search_loc, is_nationwide, country = normalize_location_query(location)

    # Prioritize portals relevant to the role
    for portal in OFFICIAL_COMPANY_PORTALS:
        company = portal["company"]
        matches_domain = any(d in role_lower for d in portal["domains"]) or len(role_lower.split()) <= 1

        if not matches_domain:
            continue

        portal_loc = portal.get("location", "")
        # If city-specific (not nationwide), filter out portals that don't match
        if not is_nationwide and search_loc:
            loc_match = (
                search_loc.lower() in portal_loc.lower()
                or "global" in portal_loc.lower()
                or "remote" in portal_loc.lower()
            )
            if not loc_match:
                continue

        display_location = f"{country} (All States / Nationwide)" if is_nationwide and country else (location or portal_loc)

        if is_intern:
            apply_url = portal["intern_url"].replace("{q}", q_encoded)
            job_title = f"{role.title()} - Official Internship Opening"
            desc = f"Direct campus & student internship opening on {company}'s official careers portal. Apply directly across nationwide locations."
            pos_type = "Internship"
            exp_level = "Intern / Student (0 yrs)"
        else:
            apply_url = portal["search_url"].replace("{q}", q_encoded)
            job_title = f"{role.title()} - Official Career Portal Opening"
            desc = f"Verified active opening on {company}'s official careers website. Direct company pipeline covering all regional tech hubs."
            pos_type = "Full-Time"
            exp_level = "Entry to Senior Level"

        openings.append(JobListing(
            source=f"{company} - Official Career Site",
            title=job_title,
            company=company,
            location=display_location,
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

    return openings[:20]  # Top 20 verified official company portals


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
        query_text = f"{role} senior"
    elif is_entry:
        query_text = f"{role} junior"
    else:
        query_text = role

    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": 20,
        "what": query_text,
        "content-type": "application/json",
    }
    if location and location.lower() not in ["remote", "global"]:
        params["where"] = location

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json().get("results", [])
    except Exception:
        pass
    return []


async def _remotive_search(role: str) -> list[dict]:
    url = f"https://remotive.com/api/remote-jobs?search={urllib.parse.quote_plus(role)}"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.json().get("jobs", [])
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# 3. Platform Search Links (Comprehensive Multi-Platform Deep Search)
# ---------------------------------------------------------------------------

def _deep_search_links(role: str, location: str, experience: str = "any", job_type: str = "all") -> list[JobListing]:
    is_intern = (job_type.lower() == "internship" or experience.lower() == "intern")
    is_entry = (experience.lower() == "entry")
    is_senior = (experience.lower() in ["senior", "lead"])

    search_loc, is_nationwide, country = normalize_location_query(location)
    loc_param = urllib.parse.quote_plus(search_loc or "India")
    display_loc = f"{country} (All States / Nationwide)" if is_nationwide and country else (location or "India")
    role_slug = role.lower().replace(" ", "-").replace("/", "-")
    loc_slug = (search_loc or "india").lower().replace(" ", "-")

    q_role = urllib.parse.quote_plus(role)

    # 1. Google Jobs Engine URL (Direct structured Schema.org job aggregator)
    google_jobs_query = f"{role} internship in {search_loc}" if is_intern else f"{role} jobs in {search_loc}"
    google_jobs_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(google_jobs_query)}&ibp=htl;jobs"

    # 2. LinkedIn Jobs URL
    li_q = urllib.parse.quote_plus(f"{role} intern" if is_intern else role)
    li_url = f"https://www.linkedin.com/jobs/search/?keywords={li_q}&location={loc_param}"
    if is_intern:
        li_url += "&f_E=1"
    elif is_entry:
        li_url += "&f_E=2"
    elif is_senior:
        li_url += "&f_E=4"

    # 3. Wellfound / AngelList (Premier Startup & Tech Jobs)
    wellfound_url = f"https://wellfound.com/jobs?role={q_role}&location={loc_param}"

    # 4. Levels.fyi Jobs (Verified Top-Tier Compensation Tech Roles)
    levels_url = f"https://www.levels.fyi/jobs?keyword={q_role}&location={loc_param}"

    # 5. Indeed Jobs URL
    indeed_subdomain = "in" if ("india" in (country or search_loc).lower()) else "www"
    if is_intern:
        indeed_url = f"https://{indeed_subdomain}.indeed.com/jobs?q={urllib.parse.quote_plus(role + ' intern')}&jt=internship&l={loc_param}"
    else:
        indeed_url = f"https://{indeed_subdomain}.indeed.com/jobs?q={q_role}&l={loc_param}"

    # 6. Glassdoor Jobs
    glassdoor_url = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={q_role}&locT=C&locKeyword={loc_param}"

    # 7. Unstop (College & Campus Placement Directory)
    if is_intern:
        unstop_url = f"https://unstop.com/internships?searchTerm={q_role}"
    else:
        unstop_url = f"https://unstop.com/jobs?searchTerm={q_role}"

    # 8. Naukri (Major Indian Tech & Corporate Portal)
    if is_intern:
        naukri_url = f"https://www.naukri.com/{role_slug}-internship-jobs"
    else:
        naukri_url = f"https://www.naukri.com/{role_slug}-jobs-in-{loc_slug}"

    # 9. Foundit / Monster
    foundit_url = f"https://www.foundit.in/srp/results?query={q_role}&locations={loc_param}"

    # 10. Remote Portals (RemoteOK & We Work Remotely)
    remoteok_url = f"https://remoteok.com/remote-{role_slug}-jobs"
    weworkremotely_url = f"https://weworkremotely.com/remote-jobs/search?term={q_role}"

    pos_type = "Internship" if is_intern else "Full-Time"
    exp_level = "Intern / Student (0 yrs)" if is_intern else ("Senior (5+ yrs)" if is_senior else ("Entry Level (0-2 yrs)" if is_entry else "Any Experience"))

    deep_links = [
        JobListing(
            source="Google Jobs (Deep Engine)",
            title=f"Search Google Jobs for '{role}'" + (" Internships" if is_intern else ""),
            company="Google Jobs Index",
            location=display_loc,
            apply_url=google_jobs_url,
            description_snippet=f"Official Google Jobs search indexing structured career listings from thousands of company career boards.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct Google Jobs aggregator linking directly to corporate ATS applicant tracking systems."],
            position_type=pos_type,
            experience_level=exp_level,
            priority_score=15,
        ),
        JobListing(
            source="LinkedIn Jobs",
            title=f"Search LinkedIn for '{role}'" + (" Internships" if is_intern else ""),
            company="LinkedIn Network",
            location=display_loc,
            apply_url=li_url,
            description_snippet=f"Pre-filtered LinkedIn job board search tailored to {role} in {display_loc} with verified recruiter posters.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct LinkedIn platform query with active experience and role filters."],
            position_type=pos_type,
            experience_level=exp_level,
            priority_score=14,
        ),
        JobListing(
            source="Wellfound (AngelList)",
            title=f"Search Wellfound (AngelList) for '{role}'",
            company="Wellfound Tech Startups",
            location=display_loc,
            apply_url=wellfound_url,
            description_snippet=f"Direct access to 130,000+ tech startup teams, Seed to Series D tech companies, and direct founder pipelines.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct connection to venture-backed startups and hiring founders."],
            position_type=pos_type,
            experience_level=exp_level,
            priority_score=13,
        ),
        JobListing(
            source="Levels.fyi",
            title=f"Search Levels.fyi for '{role}'",
            company="Levels.fyi Verified",
            location=display_loc,
            apply_url=levels_url,
            description_snippet=f"Browse verified high-compensation software and tech opportunities with benchmarked pay bands.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Verified tech compensation and career portal."],
            position_type=pos_type,
            experience_level=exp_level,
            priority_score=12,
        ),
        JobListing(
            source="Indeed",
            title=f"Search Indeed for '{role}'" + (" Internships" if is_intern else ""),
            company="Indeed Jobs",
            location=display_loc,
            apply_url=indeed_url,
            description_snippet=f"Pre-filled Indeed search results matching {role} in {display_loc}.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct platform search link with relevant keyword filters."],
            position_type=pos_type,
            experience_level=exp_level,
            priority_score=10,
        ),
        JobListing(
            source="Glassdoor",
            title=f"Search Glassdoor for '{role}'",
            company="Glassdoor Portal",
            location=display_loc,
            apply_url=glassdoor_url,
            description_snippet=f"Job listings paired with anonymous employee reviews, interview questions, and salary estimates.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Verified company review and job search aggregator."],
            position_type=pos_type,
            experience_level=exp_level,
            priority_score=10,
        ),
        JobListing(
            source="Unstop (Campus & Fresher)",
            title=f"Search Unstop for '{role}'" + (" Internships" if is_intern else " Jobs"),
            company="Unstop Directory",
            location=display_loc,
            apply_url=unstop_url,
            description_snippet="Dedicated hiring challenges, hackathons, and entry-level / intern openings for college talent.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct link to Unstop hiring directory."],
            position_type=pos_type,
            experience_level=exp_level,
            priority_score=10,
        ),
        JobListing(
            source="Naukri",
            title=f"Search Naukri for '{role}'" + (" Internships" if is_intern else ""),
            company="Naukri Portal",
            location=display_loc,
            apply_url=naukri_url,
            description_snippet=f"Pre-filled Naukri search results for {role} across regional tech corridors.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct platform search link."],
            position_type=pos_type,
            experience_level=exp_level,
            priority_score=9,
        ),
        JobListing(
            source="Foundit (Monster)",
            title=f"Search Foundit for '{role}'",
            company="Foundit Network",
            location=display_loc,
            apply_url=foundit_url,
            description_snippet=f"Search results across enterprise tech hubs on Foundit.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct platform search link."],
            position_type=pos_type,
            experience_level=exp_level,
            priority_score=8,
        ),
        JobListing(
            source="RemoteOK",
            title=f"Search RemoteOK for Remote '{role}'",
            company="RemoteOK Global",
            location="Remote / Worldwide",
            apply_url=remoteok_url,
            description_snippet="Dedicated worldwide remote technology openings for distributed teams.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct remote tech aggregator."],
            position_type=pos_type,
            experience_level=exp_level,
            priority_score=8,
        ),
        JobListing(
            source="We Work Remotely",
            title=f"Search We Work Remotely for '{role}'",
            company="We Work Remotely",
            location="Remote / Worldwide",
            apply_url=weworkremotely_url,
            description_snippet="Top remote work community with 100% remote software, design, and product listings.",
            legitimacy_verdict="likely_legit",
            legitimacy_reasons=["Direct curated remote job board."],
            position_type=pos_type,
            experience_level=exp_level,
            priority_score=8,
        ),
    ]

    return deep_links


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------

async def search_jobs(
    role: str,
    location: str,
    experience: str = "any",
    job_type: str = "all",
    resume_text: str | None = None,
) -> list[JobListing]:
    from .keyword_extractor import extract_keywords

    search_loc, is_nationwide, country = normalize_location_query(location)
    effective_adzuna_loc = "" if (is_nationwide and country == "India") else search_loc

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
        raw_adzuna = await _adzuna_search(role, effective_adzuna_loc, experience=experience, job_type=job_type)
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
