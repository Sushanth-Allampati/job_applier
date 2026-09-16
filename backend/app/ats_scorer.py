"""
ATS-style scoring engine matching recruiter-grade evaluation rubrics (Workday, Greenhouse, Taleo, Ashby).
Evaluates four core pillars:
1. Technical & Domain Skills Match (40%)
2. Quantified Impact & STAR Metrics (25%)
3. Action Verbs & Power Phrasing (20%)
4. ATS Parseability & Structural Health (15%)

Generates copy-pasteable STAR bullet points with missing keywords so candidates can pass screening filters.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .keyword_extractor import extract_keywords, SKILL_DICTIONARY, SKILL_ALIASES, normalize_skill

REQUIRED_SECTIONS = [
    ("experience", ["experience", "work history", "employment", "professional background"]),
    ("education", ["education", "academic", "degrees"]),
    ("skills", ["skills", "technical skills", "core competencies", "technologies", "proficiencies"]),
]

OPTIONAL_RECOMMENDED_SECTIONS = [
    ("projects", ["projects", "personal projects", "open source"]),
    ("certifications", ["certifications", "licenses", "certificates"]),
]

CONTACT_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"(\+?\d[\d\-\s()]{8,}\d)"),
    "linkedin": re.compile(r"(linkedin\.com/in/|github\.com/)", re.IGNORECASE),
}

# High-impact active verbs favored by recruiters and scoring algorithms
POWER_VERBS = {
    "accelerated", "accomplished", "achieved", "acquired", "administered", "advanced",
    "analyzed", "architected", "automated", "built", "centralized", "championed",
    "coached", "collaborated", "constructed", "created", "decreased", "delivered",
    "deployed", "designed", "developed", "devised", "eliminated", "engineered",
    "established", "executed", "expanded", "expedited", "formulated", "founded",
    "generated", "guided", "implemented", "improved", "increased", "initiated",
    "innovated", "inspected", "integrated", "launched", "lead", "led", "leveraged",
    "maximized", "mentored", "minimized", "modernized", "negotiated", "optimized",
    "orchestrated", "overhauled", "pioneered", "planned", "produced", "programmed",
    "reduced", "refactored", "resolved", "restructured", "revamped", "scaled",
    "simplified", "solved", "spearheaded", "standardized", "streamlined", "strengthened",
    "transformed", "upgraded", "validated", "yielded"
}

# Weak passive phrasing to eliminate from resumes with recruiter-grade alternatives
WEAK_PHRASES_MAP = {
    "responsible for": "Spearheaded / Delivered / Directed",
    "assisted with": "Engineered / Collaborated on / Accelerated",
    "helped to": "Co-engineered / Implemented / Optimized",
    "worked on": "Designed and deployed / Engineered / Built",
    "duties included": "Executed / Oversaw / Delivered",
    "participated in": "Contributed directly to / Developed",
    "tasked with": "Successfully executed / Orchestrated",
    "handled": "Administered / Resolved / Optimized",
}

# Pre-crafted STAR bullet templates for popular skills
STAR_BULLET_TEMPLATES = {
    "docker": "Containerized microservices and production workflows using Docker, accelerating CI/CD build speeds by 40% and eliminating environment discrepancies.",
    "kubernetes": "Orchestrated container deployments with Kubernetes (K8s), maintaining 99.95% service availability and automating autoscaling for high-traffic workloads.",
    "aws": "Architected cloud infrastructure on AWS leveraging ECS, S3, RDS, and Lambda, reducing monthly hosting overhead by 28% while improving fault tolerance.",
    "azure": "Deployed resilient enterprise solutions across Microsoft Azure utilizing AKS and App Services, cutting provisioning latency by 35%.",
    "gcp": "Engineered scalable cloud services on Google Cloud Platform (GCP) with BigQuery and Cloud Run, boosting batch analytics throughput by 50%.",
    "ci/cd": "Constructed automated CI/CD pipelines via GitHub Actions, accelerating release cycles from bi-weekly sprints to multiple daily zero-downtime releases.",
    "unit testing": "Authored comprehensive unit and integration testing suites achieving 88%+ code coverage, decreasing post-release regression defects by 45%.",
    "testing": "Implemented automated end-to-end and regression testing frameworks, identifying critical vulnerabilities early and reducing QA cycle duration by 30%.",
    "microservices": "Decomposed monolithic backend applications into modular microservices with REST/gRPC interfaces, enhancing request throughput by 3.5x.",
    "rest api": "Designed and published secure, idempotent RESTful APIs handling 100k+ daily requests with sub-120ms response latencies.",
    "graphql": "Engineered GraphQL endpoints with schema federation, reducing mobile payload sizes by 42% and eliminating client-side over-fetching.",
    "postgresql": "Architected normalized relational schemas and optimized indexed queries in PostgreSQL, achieving a 60% reduction in query execution times.",
    "sql": "Wrote complex analytical SQL queries and database migrations, optimizing transaction locks and improving report generation speeds by 35%.",
    "mongodb": "Modeled document data stores in MongoDB for distributed workloads, scaling database write operations by 2.5x under peak user loads.",
    "redis": "Integrated Redis in-memory caching and session clustering, cutting primary database load by 55% and reducing p95 latency to <15ms.",
    "python": "Engineered production Python backend services and data automation scripts, processing 500k+ daily records with high reliability.",
    "fastapi": "Built asynchronous high-throughput REST microservices in FastAPI with automated Pydantic data validation and OpenAPI specs.",
    "react": "Developed modular, accessible user interfaces using React and TypeScript, improving Core Web Vitals and lowering initial page load times by 38%.",
    "node.js": "Architected non-blocking asynchronous event-driven services with Node.js and Express, scaling concurrent user capacity to 10k+ sessions.",
    "typescript": "Migrated critical codebases to TypeScript, eliminating runtime type errors by 70% and accelerating developer onboarding.",
    "golang": "Engineered high-concurrency microservices in Go (Golang) handling 50k+ QPS with sub-50ms latency and minimal memory footprint.",
    "rust": "Developed high-performance, memory-safe system components in Rust, eliminating data races and cutting CPU overhead by 45%.",
    "c++": "Optimized low-latency C++ core algorithmic pipelines, achieving sub-millisecond execution benchmarks for high-throughput data processing.",
    "c#": "Architected enterprise cloud services using C# and .NET Core, delivering 99.9% uptime across mission-critical business applications.",
    "flutter": "Built cross-platform iOS and Android applications in Flutter and Dart, maintaining 60 FPS performance and native UI fidelity.",
    "swift": "Engineered native iOS applications in Swift with Combine and SwiftUI, boosting App Store ratings to 4.8 stars.",
    "kotlin": "Developed responsive Android applications in Kotlin with Coroutines and Jetpack Compose, cutting application crash rates by 80%.",
    "machine learning": "Trained and deployed production Machine Learning models using Scikit-Learn and PyTorch, achieving 91% F1-score in real-world validation.",
    "deep learning": "Engineered deep learning neural networks with PyTorch, optimizing inference latency by 45% via ONNX model quantization.",
    "nlp": "Developed Natural Language Processing (NLP) pipelines with Transformers, automating document classification with 94% categorical precision.",
    "generative ai": "Constructed Generative AI applications leveraging LLM prompts, LangChain, and RAG architectures, cutting customer inquiry handle times by 50%.",
    "rag": "Implemented Retrieval-Augmented Generation (RAG) vector pipelines with Pinecone embeddings, delivering contextual semantic search with 92% retrieval accuracy.",
    "system design": "Architected resilient distributed systems featuring load balancers, message queues, and caching layers to support 500k+ active users.",
    "kafka": "Engineered distributed real-time event streaming pipelines with Apache Kafka, processing 1M+ messages/minute with zero data loss.",
    "linux": "Automated server configuration and shell scripting in Linux environments, standardizing deployment practices across 50+ remote instances.",
    "git": "Championed Git workflow standards including trunk-based development and peer code reviews, improving sprint delivery predictability by 25%.",
    "agile": "Collaborated in Agile/Scrum ceremonies, translating user stories into technical specifications and delivering milestones ahead of schedule.",
    "problem solving": "Diagnosed and resolved critical high-severity production incidents, reducing Mean Time to Resolution (MTTR) by 45%.",
    "communication": "Partnered cross-functionally with product managers, designers, and stakeholders to define product roadmaps and technical architectures.",
    "leadership": "Mentored junior engineers on software architecture, clean code standards, and automated testing, accelerating team delivery velocity.",
    "figma": "Created interactive UI prototypes and design systems in Figma, bridging user research findings into production-ready frontend specs.",
    "ui/ux": "Conducted usability testing and refined UI/UX workflows, boosting user retention by 22% and reducing customer onboarding friction.",
    "snowflake": "Constructed cloud data warehouse models in Snowflake, enabling automated self-serve reporting for executive stakeholders.",
    "spark": "Engineered distributed PySpark pipelines processing terabytes of clickstream data, reducing daily batch runtimes from 6 hours to 45 minutes.",
    "airflow": "Orchestrated complex DAG data workflows with Apache Airflow, automating data ingestion and alert notifications across 20+ sources.",
    "solidity": "Authored and audited secure Solidity smart contracts on Ethereum, deploying gas-optimized protocols handling $2M+ in transaction volume.",
    "selenium": "Constructed automated regression test suites using Selenium WebDriver and Python, cutting test execution turnaround times by 65%.",
    "playwright": "Automated end-to-end web testing across Chromium, WebKit, and Firefox using Playwright, cutting UI defect escape rates by 50%.",
    "cybersecurity": "Conducted enterprise security assessments, vulnerability remediation, and OWASP compliance audits, eliminating critical attack vectors.",
}

ROLE_SKILL_PATTERNS: dict[str, list[str]] = {
    # Software Engineering & Web Stacks
    "frontend": ["javascript", "typescript", "react", "html", "css", "vue", "angular", "next.js", "tailwindcss", "rest api", "git", "ui/ux", "unit testing"],
    "react": ["react", "javascript", "typescript", "html", "css", "redux", "next.js", "rest api", "git", "unit testing"],
    "angular": ["angular", "typescript", "javascript", "html", "css", "rxjs", "rest api", "git", "unit testing"],
    "vue": ["vue", "javascript", "typescript", "html", "css", "vuex", "pinia", "rest api", "git", "unit testing"],
    "next.js": ["next.js", "react", "typescript", "javascript", "tailwindcss", "html", "css", "rest api", "git"],
    "backend": ["python", "java", "sql", "postgresql", "rest api", "docker", "fastapi", "django", "node.js", "microservices", "redis", "git", "system design"],
    "full stack": ["javascript", "typescript", "react", "node.js", "python", "sql", "postgresql", "html", "css", "git", "rest api", "docker", "microservices"],
    "software engineer": ["algorithms", "data structures", "system design", "git", "object oriented", "unit testing", "sql", "rest api", "agile", "docker"],
    "node": ["node.js", "express", "javascript", "typescript", "rest api", "mongodb", "postgresql", "docker", "git"],
    "python": ["python", "sql", "rest api", "git", "docker", "django", "flask", "fastapi", "unit testing", "postgresql"],
    "java": ["java", "spring", "spring boot", "sql", "microservices", "docker", "git", "rest api", "unit testing", "system design"],
    "golang": ["golang", "microservices", "docker", "kubernetes", "rest api", "grpc", "git", "system design", "sql"],
    "go ": ["golang", "microservices", "docker", "kubernetes", "rest api", "grpc", "git", "system design", "sql"],
    "c++": ["c++", "data structures", "algorithms", "object oriented", "linux", "git", "system design"],
    "c#": ["c#", ".net", "sql", "rest api", "azure", "microservices", "git", "object oriented", "unit testing"],
    ".net": ["c#", ".net", "sql", "rest api", "azure", "microservices", "git", "object oriented", "unit testing"],
    "rust": ["rust", "systems", "linux", "algorithms", "git", "rest api"],
    "ruby": ["ruby", "sql", "postgresql", "rest api", "git", "docker", "unit testing"],
    "php": ["php", "mysql", "sql", "javascript", "html", "css", "rest api", "git"],
    "laravel": ["php", "mysql", "sql", "rest api", "git", "html", "css"],
    "embedded": ["c++", "firmware", "microcontrollers", "linux", "git", "iot"],
    "firmware": ["c++", "embedded", "microcontrollers", "linux", "git"],
    "game": ["c++", "c#", "algorithms", "git", "object oriented"],
    "systems": ["c++", "linux", "algorithms", "git", "system design"],

    # Mobile Development
    "mobile": ["react", "flutter", "swift", "kotlin", "javascript", "typescript", "rest api", "git", "ui/ux"],
    "ios": ["swift", "ios", "rest api", "git", "ui/ux", "unit testing"],
    "android": ["kotlin", "java", "android", "rest api", "git", "ui/ux", "unit testing"],
    "flutter": ["flutter", "dart", "mobile", "rest api", "git", "ui/ux", "unit testing"],
    "react native": ["react", "javascript", "typescript", "mobile", "rest api", "git", "redux"],

    # AI, Machine Learning & Data Science
    "machine learning": ["python", "machine learning", "deep learning", "pytorch", "tensorflow", "nlp", "scikit-learn", "numpy", "pandas", "computer vision", "llm"],
    "ai": ["python", "machine learning", "deep learning", "pytorch", "tensorflow", "nlp", "generative ai", "rag", "langchain", "algorithms", "rest api"],
    "deep learning": ["python", "deep learning", "pytorch", "tensorflow", "computer vision", "nlp", "numpy"],
    "computer vision": ["python", "opencv", "deep learning", "pytorch", "tensorflow", "image processing"],
    "nlp": ["python", "nlp", "deep learning", "pytorch", "llm", "langchain"],
    "generative ai": ["generative ai", "llm", "rag", "langchain", "python", "pytorch"],
    "llm": ["llm", "generative ai", "rag", "langchain", "python"],
    "mlops": ["python", "docker", "kubernetes", "ci/cd", "machine learning", "aws", "gcp"],
    "data science": ["python", "data analysis", "machine learning", "pandas", "numpy", "sql", "scikit-learn", "data science", "deep learning", "tableau", "statistics"],
    "data scientist": ["python", "data analysis", "machine learning", "pandas", "numpy", "sql", "scikit-learn", "data science", "tableau", "statistics"],
    "data analyst": ["sql", "data analysis", "excel", "power bi", "tableau", "python", "data visualization", "problem solving"],
    "bi analyst": ["power bi", "tableau", "sql", "excel", "data analysis", "data visualization", "etl"],
    "data engineer": ["sql", "python", "etl", "data engineering", "spark", "hadoop", "airflow", "snowflake", "postgresql", "docker", "kafka"],
    "big data": ["spark", "hadoop", "kafka", "python", "sql", "data engineering", "airflow"],
    "analytics engineer": ["sql", "snowflake", "data modeling", "git", "data analysis", "airflow"],
    "database": ["sql", "postgresql", "mysql", "nosql", "redis", "mongodb"],
    "dba": ["sql", "postgresql", "mysql", "performance tuning", "high availability"],

    # Cloud, DevOps, Infrastructure & SRE
    "devops": ["docker", "kubernetes", "aws", "ci/cd", "linux", "terraform", "git", "azure", "gcp", "ansible", "prometheus", "grafana", "microservices"],
    "cloud engineer": ["aws", "azure", "gcp", "docker", "kubernetes", "terraform", "linux", "ci/cd", "microservices"],
    "cloud architect": ["aws", "azure", "system design", "terraform", "microservices", "kubernetes"],
    "cloud": ["aws", "azure", "gcp", "docker", "kubernetes", "terraform", "linux", "ci/cd", "microservices", "system design"],
    "sre": ["linux", "kubernetes", "docker", "ci/cd", "prometheus", "grafana", "terraform", "python"],
    "site reliability": ["linux", "kubernetes", "docker", "ci/cd", "prometheus", "grafana", "terraform", "python"],
    "platform engineer": ["kubernetes", "docker", "terraform", "aws", "ci/cd", "linux", "golang"],
    "infrastructure": ["terraform", "ansible", "linux", "aws", "docker", "ci/cd"],
    "network": ["networking", "firewalls", "routing", "switching", "linux"],

    # Cybersecurity & InfoSec
    "cybersecurity": ["cybersecurity", "linux", "python", "git", "docker", "cloud", "owasp", "penetration testing", "problem solving"],
    "security": ["cybersecurity", "linux", "python", "git", "docker", "cloud", "owasp", "penetration testing", "problem solving"],
    "infosec": ["cybersecurity", "risk management", "firewalls", "vulnerability assessment"],
    "soc": ["incident response", "log analysis", "cybersecurity", "networking"],
    "penetration": ["penetration testing", "owasp", "vulnerability assessment", "linux", "python"],
    "appsec": ["application security", "owasp", "code review", "vulnerability management", "python"],

    # QA & Quality Engineering
    "qa": ["testing", "unit testing", "automation testing", "selenium", "playwright", "cypress", "python", "javascript", "ci/cd", "git", "agile"],
    "sdet": ["automation testing", "java", "python", "selenium", "playwright", "ci/cd", "git", "unit testing", "docker"],
    "automation test": ["selenium", "playwright", "cypress", "automation testing", "python", "java", "ci/cd", "git"],
    "manual qa": ["test cases", "manual testing", "bug tracking", "regression testing", "agile", "qa"],
    "performance test": ["performance testing", "load testing", "api testing", "metrics"],

    # Product, Program & Project Management
    "product manager": ["product management", "agile", "scrum", "leadership", "communication", "problem solving", "ui/ux", "figma", "roadmap"],
    "product": ["product management", "agile", "scrum", "leadership", "communication", "problem solving", "ui/ux", "figma", "roadmap"],
    "technical product": ["product management", "system design", "agile", "scrum", "sql", "communication"],
    "apm": ["product management", "market research", "data analysis", "agile", "communication", "prioritization"],
    "product owner": ["product management", "scrum", "agile", "jira", "communication"],
    "project manager": ["project management", "agile", "scrum", "communication", "scheduling"],
    "scrum master": ["scrum", "agile", "facilitation", "jira", "mentorship"],
    "agile coach": ["agile", "scrum", "mentorship", "coaching"],
    "business analyst": ["business analysis", "requirements gathering", "sql", "excel", "communication"],

    # UI/UX & Design
    "ui/ux": ["figma", "ui/ux", "html", "css", "wireframing", "prototyping", "communication", "problem solving"],
    "designer": ["figma", "ui/ux", "html", "css", "wireframing", "prototyping", "communication", "problem solving"],
    "product designer": ["figma", "ui/ux", "prototyping", "user research", "communication"],
    "ux researcher": ["user research", "usability testing", "interviews", "personas", "figma"],
    "visual designer": ["figma", "typography", "branding", "illustration", "ui/ux"],

    # Web3 & Emerging
    "blockchain": ["blockchain", "solidity", "smart contracts", "ethereum", "git", "system design"],
    "solidity": ["solidity", "ethereum", "smart contracts", "git"],
    "web3": ["web3", "solidity", "smart contracts", "react", "typescript", "ethereum"],

    # Technical Solutions, Sales & Support
    "solutions architect": ["cloud", "system design", "aws", "enterprise architecture", "microservices", "communication"],
    "technical support": ["troubleshooting", "linux", "networking", "sql", "communication"],
    "customer success": ["customer success", "client onboarding", "communication", "problem solving"],
    "sales engineer": ["technical demonstrations", "solution design", "communication", "poc"],
    "devrel": ["developer relations", "public speaking", "technical writing", "api", "git", "communication"],
    "technical writer": ["technical writing", "api documentation", "markdown", "git", "communication"],
}


@dataclass
class ATSResult:
    score: int
    matched_keywords: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    formatting_notes: list[str] = field(default_factory=list)
    section_notes: list[str] = field(default_factory=list)
    # Recruiter-Grade Evaluation Details
    verdict: str = "Evaluating"
    pass_probability: str = "Medium"
    recruiter_summary: str = ""
    pillar_scores: dict[str, int] = field(default_factory=dict)
    quantified_impact_score: int = 70
    action_verbs_score: int = 75
    recommended_bullets: list[dict[str, str]] = field(default_factory=list)
    weak_phrase_replacements: list[dict[str, str]] = field(default_factory=list)
    pass_checklist: list[str] = field(default_factory=list)


def _check_sections(resume_text_lower: str) -> list[str]:
    notes = []
    for label, variants in REQUIRED_SECTIONS:
        if not any(v in resume_text_lower for v in variants):
            notes.append(f"No clear '{label.title()}' section detected — ATS parsers rely on recognized headings to bucket content accurately.")
    return notes


def _check_formatting(resume_text: str) -> list[str]:
    notes = []
    if not CONTACT_PATTERNS["email"].search(resume_text):
        notes.append("No email address detected in text — ensure contact details are in plain text (not embedded inside images or headers/footers).")
    if not CONTACT_PATTERNS["phone"].search(resume_text):
        notes.append("No phone number detected in plain text format.")
    if not CONTACT_PATTERNS["linkedin"].search(resume_text):
        notes.append("No LinkedIn or GitHub profile link found — recruiters look for verified profile URLs in the header.")
    if len(resume_text) < 700:
        notes.append("Resume text is very brief (<700 characters) — parser may be missing content trapped in tables or columns.")
    lines = resume_text.splitlines()
    very_short_lines = sum(1 for l in lines if 0 < len(l.strip()) <= 3)
    if lines and very_short_lines / max(len(lines), 1) > 0.25:
        notes.append("Extracted text looks fragmented — multi-column layouts or complex tables can scramble parser output.")
    return notes


def _analyze_metrics_and_bullets(resume_text: str) -> tuple[int, int, int]:
    """
    Scans resume for quantifiable achievements and metrics (%, $, scale, numbers).
    Returns (quantified_score, total_bullet_count, metrics_bullet_count).
    """
    lines = [l.strip() for l in resume_text.splitlines() if len(l.strip()) > 18]
    # Filter lines that look like bullet points or achievement statements
    bullet_lines = [l for l in lines if l.startswith(("•", "-", "*", "–", "—")) or re.match(r"^\d+\.", l) or len(l) > 35]

    metric_pattern = re.compile(
        r"(\d+(\.\d+)?%|\$\s?\d+[\d,]*(\.\d+)?[kKmMbB]?|\b\d+[\d,]*\+?\s*(users|clients|customers|requests|transactions|engineers|teams|downloads|records|qps|rps|members|stars)\b|\b\d+\s*(x|times|fold)\b|\b(reduced|increased|improved|boosted|grew|cut|saved)\s+.*?\b\d+)",
        re.IGNORECASE
    )

    metrics_count = 0
    for bullet in bullet_lines:
        if metric_pattern.search(bullet):
            metrics_count += 1

    total_bullets = max(len(bullet_lines), 1)
    ratio = metrics_count / total_bullets

    # Recruiters consider 40%+ metric density in bullets as world-class
    if ratio >= 0.45:
        score = min(100, int(85 + (ratio - 0.45) * 50))
    elif ratio >= 0.25:
        score = int(65 + (ratio - 0.25) * 100)
    elif ratio >= 0.10:
        score = int(45 + (ratio - 0.10) * 133)
    else:
        score = max(20, int(ratio * 400))

    return score, total_bullets, metrics_count


def _analyze_action_verbs(resume_text: str) -> tuple[int, list[dict[str, str]]]:
    """
    Measures ratio of power action verbs vs passive/weak phrases.
    Returns (action_verbs_score, weak_replacements).
    """
    text_lower = resume_text.lower()
    found_power_verbs = set()
    for verb in POWER_VERBS:
        if re.search(rf"\b{verb}\b", text_lower):
            found_power_verbs.add(verb)

    found_weak_phrases = []
    for weak, fix in WEAK_PHRASES_MAP.items():
        if weak in text_lower:
            found_weak_phrases.append({
                "weak": weak,
                "replacement": fix,
                "tip": f"Replace passive '{weak}' with strong power verbs like '{fix}' to emphasize ownership and impact."
            })

    # Base score on diversity of active power verbs (target: 6+ distinct power verbs)
    verb_score = min(100, int((len(found_power_verbs) / 8.0) * 100))
    # Deduct points for passive weak phrases
    penalty = min(30, len(found_weak_phrases) * 8)
    final_score = max(30, verb_score - penalty)

    return final_score, found_weak_phrases


def _generate_star_recommendations(missing_keywords: list[str], role: str = "") -> list[dict[str, str]]:
    """
    Generates ready-to-paste, recruiter-vetted STAR bullet points embedding missing keywords.
    """
    recommended = []
    used_keys = set()

    for kw in missing_keywords:
        norm = normalize_skill(kw.lower())
        if norm in used_keys:
            continue
        used_keys.add(norm)

        bullet = STAR_BULLET_TEMPLATES.get(norm)
        if not bullet:
            # Generate domain-intelligent STAR bullet fallback
            title_kw = kw.title()
            bullet = f"Engineered and integrated {title_kw} into core production workflows, optimizing process reliability and increasing overall sprint delivery velocity by 25%."

        recommended.append({
            "keyword": kw.title(),
            "bullet": bullet,
            "category": "Technical Competency"
        })

        if len(recommended) >= 6:
            break

    return recommended


def _get_role_expected_skills(role: str) -> list[str]:
    role_lower = role.lower()
    skills: list[str] = []
    for key, expected in ROLE_SKILL_PATTERNS.items():
        if key in role_lower:
            for s in expected:
                s_norm = normalize_skill(s)
                if s_norm not in skills:
                    skills.append(s_norm)
    if not skills:
        skills = ["git", "rest api", "sql", "docker", "problem solving", "communication", "agile", "unit testing", "system design"]
    return skills


def score_resume(resume_text: str, job_description: str = "", role: str = "") -> ATSResult:
    resume_lower = resume_text.lower()
    jd_clean = job_description.strip()
    role_clean = role.strip()

    # Pillar 4: Formatting & Structure (15% weight)
    section_notes = _check_sections(resume_lower)
    formatting_notes = _check_formatting(resume_text)
    format_penalty = min(len(section_notes) * 15 + len(formatting_notes) * 10, 70)
    parseability_score = max(30, 100 - format_penalty)

    # Pillar 1: Skills & Keywords Match (40% weight)
    if jd_clean:
        target_keywords = extract_keywords(jd_clean, top_n=30)
        matched = [kw for kw in target_keywords if kw in resume_lower or normalize_skill(kw) in resume_lower]
        missing = [kw for kw in target_keywords if kw not in resume_lower and normalize_skill(kw) not in resume_lower]
        skill_ratio = len(matched) / max(len(target_keywords), 1)
        skills_score = round(skill_ratio * 100)
    elif role_clean:
        expected_skills = _get_role_expected_skills(role_clean)
        matched = [kw for kw in expected_skills if kw in resume_lower or normalize_skill(kw) in resume_lower]
        missing = [kw for kw in expected_skills if kw not in resume_lower and normalize_skill(kw) not in resume_lower]
        skill_ratio = len(matched) / max(len(expected_skills), 1)
        skills_score = round(skill_ratio * 100)
    else:
        found_skills = [skill for skill in sorted(SKILL_DICTIONARY) if skill in resume_lower]
        matched = found_skills[:20]
        must_haves = ["git", "rest api", "sql", "docker", "unit testing", "agile", "communication"]
        missing = [s for s in must_haves if s not in resume_lower]
        skill_ratio = min(len(found_skills) / 10.0, 1.0)
        skills_score = round(skill_ratio * 100)

    # Pillar 2: Quantified Metrics & Outcomes (25% weight)
    quantified_impact_score, total_bullets, metric_bullets = _analyze_metrics_and_bullets(resume_text)

    # Pillar 3: Action Verbs & Power Phrasing (20% weight)
    action_verbs_score, weak_replacements = _analyze_action_verbs(resume_text)

    # Composite Recruiter Weighted Score
    composite_score = round(
        (skills_score * 0.40) +
        (quantified_impact_score * 0.25) +
        (action_verbs_score * 0.20) +
        (parseability_score * 0.15)
    )
    final_score = max(5, min(100, composite_score))

    # Recruiter Verdict & Pass Determination
    if final_score >= 82:
        verdict = "Strong ATS Pass — Immediate Recruiter Shortlist"
        pass_probability = "High Pass Rate (90%+ Screening Clearance)"
        recruiter_summary = "Your resume demonstrates excellent keyword alignment, strong quantifiable metrics (STAR format), and active leadership language. It has a very high likelihood of passing automated filters and advancing straight to human interview scheduling."
    elif final_score >= 65:
        verdict = "Borderline Pass — Automated Screening Risk"
        pass_probability = "Moderate (50-65% Clearance depending on applicant volume)"
        recruiter_summary = "Your resume has a solid foundation, but automated parsers will rank it lower due to missing core keywords and insufficient measurable metric outcomes. Incorporating the recommendations below will easily push this into the top 10% tier."
    else:
        verdict = "High Screening Rejection Risk — Requires Optimization"
        pass_probability = "Low Pass Rate (<40% chance of clearing automated filters)"
        recruiter_summary = "Modern applicant tracking systems (Workday, Taleo, Ashby) will likely filter out this resume before a recruiter sees it. Critical role keywords are absent, and experience entries lack quantifiable results (%, $, metrics)."

    # Recommended STAR bullets embedding missing keywords
    recommended_bullets = _generate_star_recommendations(missing, role=role_clean)

    # Direct Pass Guarantee Checklist
    pass_checklist = []
    if missing:
        top_missing_str = ", ".join([m.title() for m in missing[:4]])
        pass_checklist.append(f"Add the top missing keywords to your Skills & Experience sections: {top_missing_str}")
    if metric_bullets < 3:
        pass_checklist.append("Quantify your accomplishments: Add measurable numbers (e.g. %, $, user count, latency decrease) to at least 3-4 bullet points.")
    if weak_replacements:
        pass_checklist.append(f"Eliminate passive phrases: Replace '{weak_replacements[0]['weak']}' with strong action verbs like '{weak_replacements[0]['replacement']}'.")
    if section_notes:
        pass_checklist.append("Add standard uppercase section headers (e.g. 'WORK EXPERIENCE', 'TECHNICAL SKILLS', 'EDUCATION') to prevent parsing errors.")
    if formatting_notes:
        pass_checklist.append("Verify contact information (Email, Phone, LinkedIn profile link) is in plain readable text.")

    pillar_scores = {
        "skills_match": skills_score,
        "quantified_metrics": quantified_impact_score,
        "action_verbs": action_verbs_score,
        "ats_parseability": parseability_score,
    }

    return ATSResult(
        score=final_score,
        matched_keywords=matched,
        missing_keywords=missing,
        formatting_notes=formatting_notes,
        section_notes=section_notes,
        verdict=verdict,
        pass_probability=pass_probability,
        recruiter_summary=recruiter_summary,
        pillar_scores=pillar_scores,
        quantified_impact_score=quantified_impact_score,
        action_verbs_score=action_verbs_score,
        recommended_bullets=recommended_bullets,
        weak_phrase_replacements=weak_replacements,
        pass_checklist=pass_checklist,
    )
