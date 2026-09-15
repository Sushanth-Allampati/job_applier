// API Base URL Resolution:
// 1. If window.API_BASE_URL is explicitly set, use it (trimmed).
// 2. If running on localhost or 127.0.0.1, default to http://localhost:8000.
// 3. Otherwise (e.g. in production with proxy or same-domain), default to "" (relative path).
const API_BASE = (typeof window.API_BASE_URL === "string" && window.API_BASE_URL.trim() !== "")
  ? window.API_BASE_URL.trim().replace(/\/+$/, "")
  : (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? "http://localhost:8000"
    : "";

const apiBaseNoteEl = document.getElementById("apiBaseNote");
if (apiBaseNoteEl) {
  if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
    apiBaseNoteEl.textContent = `Backend endpoint: ${API_BASE || "(relative /api)"}`;
  } else {
    apiBaseNoteEl.style.display = "none";
  }
}

// ---------- Auth state ----------
// The JWT is stored in localStorage so it survives a page refresh. It only
// grants access to this account's own applied-job list — never resume data.
let authToken = localStorage.getItem("job_assistant_token") || null;
let authEmail = localStorage.getItem("job_assistant_email") || null;

const authEmailInput = document.getElementById("authEmail");
const authPasswordInput = document.getElementById("authPassword");
const loginBtn = document.getElementById("loginBtn");
const registerBtn = document.getElementById("registerBtn");
const logoutBtn = document.getElementById("logoutBtn");
const loggedOutView = document.getElementById("loggedOutView");
const loggedInView = document.getElementById("loggedInView");
const userEmailLabel = document.getElementById("userEmailLabel");
const authError = document.getElementById("authError");
const loggedOutJobsNote = document.getElementById("loggedOutJobsNote");

function updateAuthUI() {
  const isLoggedIn = !!authToken;
  loggedOutView.hidden = isLoggedIn;
  loggedInView.hidden = !isLoggedIn;
  if (loggedOutJobsNote) loggedOutJobsNote.hidden = isLoggedIn;
  if (isLoggedIn) userEmailLabel.textContent = authEmail || "";
}

function showAuthError(message) {
  authError.textContent = message;
  authError.hidden = false;
}

function clearAuthError() {
  authError.hidden = true;
}

async function handleAuth(endpoint) {
  clearAuthError();
  const email = authEmailInput.value.trim();
  const password = authPasswordInput.value;
  if (!email || !password) {
    showAuthError("Enter both an email and a password.");
    return;
  }

  try {
    let res;
    if (endpoint === "login") {
      const body = new URLSearchParams();
      body.append("username", email);
      body.append("password", password);
      res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
    } else {
      res = await fetch(`${API_BASE}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
    }

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Authentication failed.");

    authToken = data.access_token;
    authEmail = email;
    localStorage.setItem("job_assistant_token", authToken);
    localStorage.setItem("job_assistant_email", authEmail);
    authPasswordInput.value = "";
    updateAuthUI();
  } catch (e) {
    showAuthError(e.message);
  }
}

loginBtn.addEventListener("click", () => handleAuth("login"));
registerBtn.addEventListener("click", () => handleAuth("register"));
logoutBtn.addEventListener("click", () => {
  authToken = null;
  authEmail = null;
  localStorage.removeItem("job_assistant_token");
  localStorage.removeItem("job_assistant_email");
  updateAuthUI();
});

updateAuthUI();

function authHeaders() {
  return authToken ? { Authorization: `Bearer ${authToken}` } : {};
}

// ---------- Resume / role inputs ----------
const resumeFileInput = document.getElementById("resumeFile");
const roleInput = document.getElementById("roleInput");
const locationInput = document.getElementById("locationInput");
const jdInput = document.getElementById("jdInput");

const scoreBtn = document.getElementById("scoreBtn");
const searchBtn = document.getElementById("searchBtn");

const scoreCard = document.getElementById("scoreCard");
const scoreCircle = document.getElementById("scoreCircle");
const scoreDetails = document.getElementById("scoreDetails");

const jobsCard = document.getElementById("jobsCard");
const toApplyList = document.getElementById("toApplyList");
const appliedList = document.getElementById("appliedList");
const toApplyCount = document.getElementById("toApplyCount");
const appliedCount = document.getElementById("appliedCount");

function setLoading(button, isLoading, label) {
  button.disabled = isLoading;
  button.textContent = isLoading ? "Working..." : label;
}

function renderKeywordTags(list, className) {
  return (list || []).map(k => `<span class="keyword-tag ${className}">${escapeHtml(k)}</span>`).join(" ");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function scoreColor(score) {
  if (score >= 75) return "#3fbf7f";
  if (score >= 50) return "#e0b23f";
  return "#e05f5f";
}

// ---------- ATS scoring ----------
scoreBtn.addEventListener("click", async () => {
  const file = resumeFileInput.files[0];
  const jd = jdInput.value.trim();

  if (!file) { alert("Please upload your resume first."); return; }
  if (!jd) { alert("Paste a job description to score against."); return; }

  setLoading(scoreBtn, true, "Get ATS Score");
  try {
    const formData = new FormData();
    formData.append("resume", file);
    formData.append("job_description", jd);

    const res = await fetch(`${API_BASE}/api/score-resume`, { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to score resume.");
    }
    const data = await res.json();
    renderScore(data);
  } catch (e) {
    alert(e.message);
  } finally {
    setLoading(scoreBtn, false, "Get ATS Score");
  }
});

function renderScore(data) {
  scoreCard.hidden = false;
  scoreCircle.textContent = data.score;
  scoreCircle.style.borderColor = scoreColor(data.score);

  let html = "";
  if (data.section_notes.length) {
    html += "<h3>Section issues</h3><ul class='note-list'>" +
      data.section_notes.map(n => `<li>${escapeHtml(n)}</li>`).join("") + "</ul>";
  }
  if (data.formatting_notes.length) {
    html += "<h3>Formatting notes</h3><ul class='note-list'>" +
      data.formatting_notes.map(n => `<li>${escapeHtml(n)}</li>`).join("") + "</ul>";
  }
  html += `<h3>Matched keywords (${data.matched_keywords.length})</h3><div>${renderKeywordTags(data.matched_keywords, "tag-matched")}</div>`;
  html += `<h3>Missing keywords — add these to boost your score</h3><div>${renderKeywordTags(data.missing_keywords, "tag-missing")}</div>`;

  scoreDetails.innerHTML = html;
  scoreCard.scrollIntoView({ behavior: "smooth" });
}

// ---------- Job search ----------
searchBtn.addEventListener("click", async () => {
  const role = roleInput.value.trim();
  if (!role) { alert("Enter a target role first."); return; }

  setLoading(searchBtn, true, "Find Matching Jobs");
  try {
    const formData = new FormData();
    formData.append("role", role);
    formData.append("location", locationInput.value.trim());
    const file = resumeFileInput.files[0];
    if (file) formData.append("resume", file);

    const res = await fetch(`${API_BASE}/api/search-jobs`, {
      method: "POST",
      headers: authHeaders(), // optional — logged-out search still works, just without applied-tracking
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to search jobs.");
    }
    const data = await res.json();
    renderJobs(data);
  } catch (e) {
    alert(e.message);
  } finally {
    setLoading(searchBtn, false, "Find Matching Jobs");
  }
});

function jobCardHtml(job, isApplied) {
  return `
    <div class="job-item ${isApplied ? "is-applied" : ""}" data-job-id="${escapeHtml(job.job_id)}">
      <span class="badge badge-${job.legitimacy_verdict}">${job.legitimacy_verdict.replace("_", " ")}</span>
      <h3>${escapeHtml(job.title)}</h3>
      <div class="job-meta">${escapeHtml(job.company)} · ${escapeHtml(job.location)} · via ${escapeHtml(job.source)}</div>
      <p>${escapeHtml(job.description_snippet)}</p>
      ${job.matched_keywords && job.matched_keywords.length ? `<div><strong>You already match:</strong> ${renderKeywordTags(job.matched_keywords, "tag-matched")}</div>` : ""}
      ${job.missing_keywords && job.missing_keywords.length ? `<div><strong>Add to your resume:</strong> ${renderKeywordTags(job.missing_keywords, "tag-missing")}</div>` : ""}
      <div style="margin-top:10px; display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
        <a class="apply-link" href="${job.apply_url}" target="_blank" rel="noopener noreferrer">Open / Apply →</a>
        ${authToken ? `<button class="small ${isApplied ? "secondary" : ""}" data-action="${isApplied ? "unmark" : "mark"}">${isApplied ? "Move back to To Apply" : "Mark as Applied"}</button>` : ""}
      </div>
      <details style="margin-top:8px;">
        <summary style="cursor:pointer; color:#9aa1ac; font-size:0.85rem;">Why this verdict?</summary>
        <ul class="note-list">${job.legitimacy_reasons.map(r => `<li>${escapeHtml(r)}</li>`).join("")}</ul>
      </details>
    </div>
  `;
}

function renderJobs(data) {
  jobsCard.hidden = false;
  toApplyCount.textContent = data.to_apply_count;
  appliedCount.textContent = data.applied_count;

  toApplyList.innerHTML = data.to_apply.length
    ? data.to_apply.map(job => jobCardHtml(job, false)).join("")
    : "<p class='note'>No results — try a broader role title.</p>";

  appliedList.innerHTML = data.applied.length
    ? data.applied.map(job => jobCardHtml(job, true)).join("")
    : "<p class='note'>Nothing marked as applied yet.</p>";

  jobsCard.scrollIntoView({ behavior: "smooth" });
}

// Delegate click handling for mark/unmark buttons (cards are re-rendered often)
jobsCard.addEventListener("click", async (e) => {
  const button = e.target.closest("button[data-action]");
  if (!button) return;

  const jobItem = button.closest(".job-item");
  const jobId = jobItem.dataset.jobId;
  const action = button.dataset.action;

  button.disabled = true;
  try {
    if (action === "mark") {
      const titleEl = jobItem.querySelector("h3");
      const metaText = jobItem.querySelector(".job-meta").textContent;
      const applyUrl = jobItem.querySelector(".apply-link").href;
      const [company] = metaText.split("·").map(s => s.trim());
      const source = metaText.split("via").pop().trim();

      await fetch(`${API_BASE}/api/applications`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          job_id: jobId,
          title: titleEl.textContent,
          company,
          apply_url: applyUrl,
          source,
        }),
      });
    } else {
      await fetch(`${API_BASE}/api/applications/${jobId}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
    }
    // Re-run the search to refresh both columns from the server's source of truth.
    searchBtn.click();
  } catch (err) {
    alert("Couldn't update that job's status. Please try again.");
    button.disabled = false;
  }
});
