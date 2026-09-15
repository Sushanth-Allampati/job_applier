# Job Application Assistant

Upload your resume, get an ATS-style match score against a job description,
and find matching roles across job boards — with per-job keyword suggestions
and a heuristic "is this legit?" check.

## What it does

- **ATS scoring** — parses a `.pdf`/`.docx` resume, extracts keywords from a
  job description, and scores overlap + basic formatting/section checks.
- **Job search** — pulls real listings via the free [Adzuna](https://developer.adzuna.com/)
  API (covers India + many countries, and its links often lead to the
  original posting/company site), plus pre-filled search links for LinkedIn,
  Naukri, Unstop, and Indeed, and a "search this company's official careers
  page" link for each result.
- **Per-job keyword gaps** — for every listing, shows which of its key terms
  your resume already has and which it's missing.
- **Legitimacy heuristics** — flags common scam patterns (upfront fees,
  vague company names, "unlimited earning" language, etc.) with a
  likely-legit / verify / high-risk verdict and the reasons behind it.

### What this does NOT do (on purpose)

It does not log into LinkedIn/Naukri/Unstop and auto-submit applications.
Those platforms prohibit automated account actions in their Terms of
Service and actively detect/ban accounts that try. Instead, it gets you to
a one-click "apply" link and lets you (a human) submit — which keeps your
accounts safe and keeps this tool within the platforms' rules.

---

## Project structure

```
job-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app & routes
│   │   ├── resume_parser.py     # PDF/DOCX text extraction
│   │   ├── ats_scorer.py        # ATS scoring logic
│   │   ├── keyword_extractor.py # lightweight keyword extraction
│   │   ├── legitimacy.py        # scam-heuristic checks
│   │   └── job_search.py        # Adzuna + deep-link job search
│   ├── requirements.txt
│   ├── .env.example
│   └── Procfile                 # for Render/Railway
└── frontend/
    ├── index.html
    ├── style.css
    └── script.js
```

## Run it locally

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # then fill in your Adzuna keys (optional but recommended)
python -m uvicorn app.main:app --reload
```
Backend runs at `http://localhost:8000`.

**Frontend:**
Just open `frontend/index.html` in a browser, or serve it:
```bash
cd frontend
python -m http.server 5500
```
Then visit `http://localhost:5500`.

> The frontend defaults to calling `http://localhost:8000`. To point it at
> a deployed backend, either edit `API_BASE` at the top of `script.js`, or
> add `<script>window.API_BASE_URL = "https://your-backend-url";</script>`
> before `script.js` loads in `index.html`.

## Get a free Adzuna API key (recommended)

1. Sign up at https://developer.adzuna.com/
2. Create an app to get an `app_id` and `app_key`
3. Put them in `backend/.env`

Without these, job search still works but only returns the platform
deep-search links (LinkedIn/Naukri/Unstop/Indeed), not real aggregated
listings.

## Deploying

**1. Database (Render PostgreSQL):**
1. On Render: New → PostgreSQL.
2. Name: e.g. `job-assistant-db`. Free tier is available.
3. Once created, copy the **Internal Database URL** (for Render services in the same region) or **External Database URL**.

**2. Backend (Render Web Service):**
1. Push this repo to GitHub.
2. On Render: New → Web Service → connect the repo.
3. Configure settings:
   - Root Directory: `backend`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add Environment Variables:
   - `DATABASE_URL`: Your Render PostgreSQL database URL
   - `SECRET_KEY`: A secure random hex string (`python -c "import secrets; print(secrets.token_hex(32))"`)
   - `ADZUNA_APP_ID`: Your Adzuna app ID
   - `ADZUNA_APP_KEY`: Your Adzuna app key
   - `ADZUNA_COUNTRY`: `in` (or your target country code)
   - `ALLOWED_ORIGINS`: Your Netlify site URL (e.g. `https://your-site.netlify.app`) or `*`
5. Deploy — note the live backend URL, e.g. `https://job-assistant-api.onrender.com`.

**3. Frontend (Netlify):**
1. In `frontend/config.js`, set `window.API_BASE_URL` to your Render backend URL:
   ```javascript
   window.API_BASE_URL = "https://job-assistant-api.onrender.com";
   ```
2. On Netlify: Add new site → Import an existing project → Connect GitHub repo.
3. Publish directory: `frontend` (auto-detected via `netlify.toml`).
4. Deploy!

## Notes / next steps you might want

- Tighten CORS in `main.py` (`allow_origins`) to your actual frontend
  domain once deployed, instead of `*`.
- The keyword extractor is intentionally dependency-light (no spaCy/LLM
  calls) to keep hosting free-tier friendly. Swapping in a proper NLP
  model would improve keyword quality if you outgrow this.
- The legitimacy checker is heuristic only — always independently verify
  a company before paying anything or sharing sensitive documents.
