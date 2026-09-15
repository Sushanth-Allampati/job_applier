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
    "python", "java", "javascript", "typescript", "c++", "c#", "sql", "nosql",
    "react", "angular", "vue", "node.js", "django", "flask", "fastapi",
    "spring", "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
    "machine learning", "deep learning", "nlp", "computer vision",
    "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy",
    "data analysis", "data engineering", "data science", "etl",
    "rest api", "graphql", "microservices", "ci/cd", "git", "linux",
    "agile", "scrum", "communication", "leadership", "problem solving",
    "project management", "excel", "power bi", "tableau", "spark",
    "hadoop", "airflow", "mongodb", "postgresql", "mysql", "redis",
    "html", "css", "figma", "ui/ux", "testing", "unit testing",
    "system design", "object oriented", "algorithms", "data structures",
}


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    # keep tokens like "c++", "node.js" reasonably intact
    raw_tokens = re.findall(r"[a-z][a-z0-9+.#/]*", text)
    tokens = []
    for t in raw_tokens:
        # strip trailing punctuation that isn't part of a known pattern
        # (e.g. "experience." -> "experience", but keep "node.js", "c++", "c#")
        if t not in SKILL_DICTIONARY:
            t = t.rstrip(".")
        if t and t not in STOPWORDS and len(t) > 1:
            tokens.append(t)
    return tokens


def _bigrams(tokens: list[str]) -> list[str]:
    return [f"{a} {b}" for a, b in zip(tokens, tokens[1:])]


def extract_keywords(text: str, top_n: int = 25) -> list[str]:
    tokens = _tokenize(text)
    bigrams = _bigrams(tokens)

    counts: Counter[str] = Counter()
    counts.update(tokens)
    counts.update(bigrams)

    scored: list[tuple[str, float]] = []
    for term, freq in counts.items():
        if freq < 1:
            continue
        weight = freq
        if term in SKILL_DICTIONARY:
            weight += 5  # boost known professional/technical terms
        elif len(term.split()) == 1 and freq < 2:
            continue  # skip rare, likely-noise unigrams
        scored.append((term, weight))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [term for term, _ in scored[:top_n]]
