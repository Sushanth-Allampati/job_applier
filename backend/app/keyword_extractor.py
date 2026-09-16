"""
Lightweight keyword extraction — deliberately avoids heavy NLP dependencies
(spaCy/transformers) so the backend stays fast to install and cheap to host.

Approach:
1. Strip a large stopword list.
2. Score remaining unigrams/bigrams by frequency.
3. Boost terms that also appear in a curated tech/soft-skill dictionary,
   since those are what ATS keyword matching actually weighs.
"""
from __future__ import annotations

import re
from collections import Counter

STOPWORDS = set("""
a about above after again against all am an and any are aren't as at be
because been before being below between both but by can't cannot could
couldn't did didn't do does doesn't doing don't down during each few for
from further had hadn't has hasn't have haven't having he he'd he'll he's
her here here's hers herself him himself his how how's i i'd i'll i'm i've
if in into is isn't it it's its itself let's me more most mustn't my
myself no nor not of off on once only or other ought our ours ourselves
out over own same shan't she she'd she'll she's should shouldn't so some
such than that that's the their theirs them themselves then there there's
these they they'd they'll they're they've this those through to too under
until up very was wasn't we we'd we'll we're we've were weren't what
what's when when's where where's which while who who's whom why why's
with won't would wouldn't you you'd you'll you're you've your yours
yourself yourselves will etc using use used strong good excellent great
experience years year role work team ability skills including preferred
responsibilities requirements required must plus job company looking
candidate candidates apply application applicants
""".split())

# Curated dictionary of common technical / professional skill terms.
# Not exhaustive — it's a relevance BOOST layer, not a hard filter.
SKILL_DICTIONARY = {
    "python", "java", "javascript", "typescript", "c++", "c#", "golang", "ruby", "rust", "php", "scala", "kotlin", "swift",
    "sql", "nosql", "react", "angular", "vue", "next.js", "node.js", "express", "django", "flask", "fastapi", "spring", "spring boot",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible", "helm", "linux", "ci/cd", "jenkins", "github actions",
    "machine learning", "deep learning", "nlp", "computer vision", "generative ai", "llm", "rag", "langchain",
    "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy", "opencv", "huggingface",
    "data analysis", "data engineering", "data science", "etl", "snowflake", "spark", "hadoop", "airflow", "kafka", "rabbitmq", "dbt",
    "rest api", "graphql", "grpc", "microservices", "git", "system design", "object oriented", "algorithms", "data structures",
    "mongodb", "postgresql", "mysql", "redis", "elasticsearch", "cassandra", "dynamodb", "prisma",
    "html", "css", "tailwindcss", "redux", "figma", "ui/ux",
    "testing", "unit testing", "integration testing", "selenium", "playwright", "cypress", "jest", "pytest",
    "cybersecurity", "owasp", "penetration testing", "devops", "sre", "prometheus", "grafana", "datadog",
    "agile", "scrum", "communication", "leadership", "problem solving", "project management", "excel", "power bi", "tableau",
}

SKILL_ALIASES = {
    "k8s": "kubernetes",
    "k8": "kubernetes",
    "reactjs": "react",
    "react.js": "react",
    "nodejs": "node.js",
    "vuejs": "vue",
    "nextjs": "next.js",
    "expressjs": "express",
    "postgres": "postgresql",
    "postgresql db": "postgresql",
    "aws cloud": "aws",
    "azure cloud": "azure",
    "gcp cloud": "gcp",
    "google cloud": "gcp",
    "ci cd": "ci/cd",
    "cicd": "ci/cd",
    "ts": "typescript",
    "js": "javascript",
    "py": "python",
    "ml": "machine learning",
    "dl": "deep learning",
    "genai": "generative ai",
    "gen ai": "generative ai",
    "tf": "tensorflow",
    "sklearn": "scikit-learn",
    "tailwind": "tailwindcss",
    "mongo": "mongodb",
}


def normalize_skill(term: str) -> str:
    clean = term.strip().lower()
    return SKILL_ALIASES.get(clean, clean)


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    # Normalize common multi-word or hyphenated skill aliases in raw text
    text = re.sub(r"\bci/cd\b", "ci_cd", text)
    text = re.sub(r"\bnode\.js\b", "node_js", text)
    text = re.sub(r"\bnext\.js\b", "next_js", text)

    raw_tokens = re.findall(r"[a-z][a-z0-9+._#/]*", text)
    tokens = []
    for t in raw_tokens:
        if t == "ci_cd":
            t = "ci/cd"
        elif t == "node_js":
            t = "node.js"
        elif t == "next_js":
            t = "next.js"
        else:
            if t not in SKILL_DICTIONARY and t not in SKILL_ALIASES:
                t = t.rstrip(".")

        t = normalize_skill(t)
        if t and t not in STOPWORDS and len(t) > 1:
            tokens.append(t)
    return tokens


def _bigrams(tokens: list[str]) -> list[str]:
    return [f"{a} {b}" for a, b in zip(tokens, tokens[1:])]


def extract_keywords(text: str, top_n: int = 30) -> list[str]:
    tokens = _tokenize(text)
    bigrams = _bigrams(tokens)

    counts: Counter[str] = Counter()
    counts.update(tokens)
    counts.update(bigrams)

    scored: list[tuple[str, float]] = []
    seen = set()
    for term, freq in counts.items():
        norm_term = normalize_skill(term)
        if norm_term in seen or freq < 1:
            continue
        seen.add(norm_term)

        weight = float(freq)
        if norm_term in SKILL_DICTIONARY:
            weight += 6.0  # High relevance boost for recognized tech/domain skills
        elif len(norm_term.split()) == 1 and freq < 2:
            continue  # skip rare noisy unigrams
        scored.append((norm_term, weight))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [term for term, _ in scored[:top_n]]
