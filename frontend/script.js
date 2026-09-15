// ==========================================================================
// CareerPilot — Frontend Logic & Interactions
// ==========================================================================

// 1. API Base URL Resolution
const API_BASE = (typeof window.API_BASE_URL === "string" && window.API_BASE_URL.trim() !== "")
  ? window.API_BASE_URL.trim().replace(/\/+$/, "")
  : (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? "http://localhost:8000"
    : "";

// Developer hint display
const apiBaseNoteEl = document.getElementById("apiBaseNote");
if (apiBaseNoteEl) {
  if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
    apiBaseNoteEl.textContent = `Backend endpoint: ${API_BASE || "(relative /api)"}`;
  } else {
    apiBaseNoteEl.style.display = "none";
  }
}

// 2. Toast Notification System
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;

  const iconMap = {
    success: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`,
    error: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`,
    info: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`,
  };

  toast.innerHTML = `
    <span>${iconMap[type] || iconMap.info}</span>
    <span>${escapeHtml(message)}</span>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(40px)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4200);
}

// 3. Check Backend Connectivity
async function checkBackendHealth() {
  const pill = document.getElementById("backendStatusPill");
  if (!pill) return;

  try {
    const res = await fetch(`${API_BASE}/`, { method: "GET" });
    if (res.ok) {
      pill.className = "status-pill status-online";
      pill.querySelector(".status-text").textContent = "Backend Online";
    } else {
      throw new Error("Bad response");
    }
  } catch (err) {
    pill.className = "status-pill status-offline";
    pill.querySelector(".status-text").textContent = "Backend Offline";
  }
}
checkBackendHealth();

// 4. Authentication State
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
  if (loggedOutView) loggedOutView.hidden = isLoggedIn;
  if (loggedInView) loggedInView.hidden = !isLoggedIn;
  if (loggedOutJobsNote) loggedOutJobsNote.hidden = isLoggedIn;
  if (isLoggedIn && userEmailLabel) userEmailLabel.textContent = authEmail || "";
}

function showAuthError(msg) {
  if (authError) {
    authError.textContent = msg;
    authError.hidden = false;
  }
  showToast(msg, "error");
}

function clearAuthError() {
  if (authError) authError.hidden = true;
}

async function handleAuth(endpoint) {
  clearAuthError();
  const email = authEmailInput.value.trim();
  const password = authPasswordInput.value;
  if (!email || !password) {
    showAuthError("Please enter both email and password.");
    return;
  }

  const btn = endpoint === "login" ? loginBtn : registerBtn;
  const originalText = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span class="btn-spinner"></span>`;

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

    showToast(endpoint === "login" ? "Logged in successfully!" : "Account created successfully!", "success");
    // Refresh search results if already loaded to update applied status
    const role = document.getElementById("roleInput")?.value.trim();
    if (role && !document.getElementById("jobsCard").hidden) {
      document.getElementById("searchBtn")?.click();
    }
  } catch (e) {
    showAuthError(e.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalText;
  }
}

if (loginBtn) loginBtn.addEventListener("click", () => handleAuth("login"));
if (registerBtn) registerBtn.addEventListener("click", () => handleAuth("register"));
if (logoutBtn) logoutBtn.addEventListener("click", () => {
  authToken = null;
  authEmail = null;
  localStorage.removeItem("job_assistant_token");
  localStorage.removeItem("job_assistant_email");
  updateAuthUI();
  showToast("Logged out successfully.", "info");
});
updateAuthUI();

function authHeaders() {
  return authToken ? { Authorization: `Bearer ${authToken}` } : {};
}

// 5. Drag-and-Drop Resume Dropzone
const resumeFileInput = document.getElementById("resumeFile");
const resumeDropzone = document.getElementById("resumeDropzone");
const dropzoneDefault = document.getElementById("dropzoneDefault");
const dropzoneActive = document.getElementById("dropzoneActive");
const fileNameDisplay = document.getElementById("fileNameDisplay");
const fileSizeDisplay = document.getElementById("fileSizeDisplay");
const removeFileBtn = document.getElementById("removeFileBtn");

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
}

function handleFileSelected(file) {
  if (!file) return;
  const lower = file.name.toLowerCase();
  if (!lower.endsWith(".pdf") && !lower.endsWith(".docx")) {
    showToast("Please upload a .pdf or .docx document.", "error");
    resumeFileInput.value = "";
    return;
  }

  fileNameDisplay.textContent = file.name;
  fileSizeDisplay.textContent = formatFileSize(file.size);
  dropzoneDefault.hidden = true;
  dropzoneActive.hidden = false;
  showToast(`Loaded "${file.name}"`, "info");
}

if (resumeFileInput) {
  resumeFileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  });
}

if (resumeDropzone) {
  ["dragenter", "dragover"].forEach(eventName => {
    resumeDropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      resumeDropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach(eventName => {
    resumeDropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      resumeDropzone.classList.remove("dragover");
    });
  });

  resumeDropzone.addEventListener("drop", (e) => {
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
      resumeFileInput.files = e.dataTransfer.files;
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });
}

if (removeFileBtn) {
  removeFileBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    resumeFileInput.value = "";
    dropzoneDefault.hidden = false;
    dropzoneActive.hidden = true;
    showToast("Resume removed.", "info");
  });
}

// 6. Target Role Autocomplete & Suggestions
const POPULAR_ROLES = [
  { role: "Full Stack Developer", cat: "Engineering" },
  { role: "Frontend Developer", cat: "Engineering" },
  { role: "Backend Engineer", cat: "Engineering" },
  { role: "Software Engineer", cat: "Engineering" },
  { role: "React Developer", cat: "Frontend" },
  { role: "Python Developer", cat: "Backend" },
  { role: "Java Developer", cat: "Backend" },
  { role: "Node.js Developer", cat: "Backend" },
  { role: "Machine Learning Engineer", cat: "AI & Data" },
  { role: "Data Scientist", cat: "AI & Data" },
  { role: "Data Analyst", cat: "AI & Data" },
  { role: "Data Engineer", cat: "AI & Data" },
  { role: "AI Engineer", cat: "AI & Data" },
  { role: "DevOps Engineer", cat: "Cloud / Infra" },
  { role: "Cloud Architect", cat: "Cloud / Infra" },
  { role: "Site Reliability Engineer (SRE)", cat: "Cloud / Infra" },
  { role: "Product Manager", cat: "Product" },
  { role: "Project Manager", cat: "Management" },
  { role: "UI/UX Designer", cat: "Design" },
  { role: "Product Designer", cat: "Design" },
  { role: "Mobile App Developer", cat: "Mobile" },
  { role: "iOS Developer (Swift)", cat: "Mobile" },
  { role: "Android Developer (Kotlin)", cat: "Mobile" },
  { role: "Cybersecurity Analyst", cat: "Security" },
  { role: "QA Engineer / SDET", cat: "Testing" },
  { role: "Automation Test Engineer", cat: "Testing" },
  { role: "Scrum Master", cat: "Management" },
  { role: "Technical Lead", cat: "Leadership" },
  { role: "Engineering Manager", cat: "Leadership" },
  { role: "Embedded Systems Engineer", cat: "Hardware" },
  { role: "Blockchain Developer", cat: "Web3" },
];

const roleInput = document.getElementById("roleInput");
const roleMenu = document.getElementById("roleSuggestionsMenu");
const roleClearBtn = document.getElementById("roleClearBtn");
let selectedSuggestionIndex = -1;

function renderRoleSuggestions(query = "") {
  if (!roleMenu) return;
  const q = query.trim().toLowerCase();

  let matches;
  if (!q) {
    matches = POPULAR_ROLES.slice(0, 8);
  } else {
    matches = POPULAR_ROLES.filter(item => item.role.toLowerCase().includes(q));
  }

  if (matches.length === 0) {
    roleMenu.hidden = true;
    return;
  }

  selectedSuggestionIndex = -1;
  roleMenu.innerHTML = matches.map((item, idx) => {
    let displayTitle = escapeHtml(item.role);
    if (q) {
      const regex = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, "gi");
      displayTitle = displayTitle.replace(regex, `<span class="autocomplete-highlight">$1</span>`);
    }
    return `
      <div class="autocomplete-item" data-index="${idx}" data-role="${escapeHtml(item.role)}">
        <span>${displayTitle}</span>
        <span class="autocomplete-category">${escapeHtml(item.cat)}</span>
      </div>
    `;
  }).join("");

  roleMenu.hidden = false;
}

if (roleInput) {
  roleInput.addEventListener("input", (e) => {
    const val = e.target.value;
    if (roleClearBtn) roleClearBtn.hidden = !val;
    renderRoleSuggestions(val);
  });

  roleInput.addEventListener("focus", () => {
    renderRoleSuggestions(roleInput.value);
  });

  roleInput.addEventListener("keydown", (e) => {
    if (roleMenu.hidden) return;
    const items = roleMenu.querySelectorAll(".autocomplete-item");
    if (!items.length) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      selectedSuggestionIndex = (selectedSuggestionIndex + 1) % items.length;
      updateSelectedSuggestion(items);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      selectedSuggestionIndex = (selectedSuggestionIndex - 1 + items.length) % items.length;
      updateSelectedSuggestion(items);
    } else if (e.key === "Enter" && selectedSuggestionIndex >= 0) {
      e.preventDefault();
      const selected = items[selectedSuggestionIndex];
      if (selected) {
        selectRole(selected.dataset.role);
      }
    } else if (e.key === "Escape") {
      roleMenu.hidden = true;
    }
  });
}

function updateSelectedSuggestion(items) {
  items.forEach((item, idx) => {
    item.classList.toggle("selected", idx === selectedSuggestionIndex);
    if (idx === selectedSuggestionIndex) {
      item.scrollIntoView({ block: "nearest" });
    }
  });
}

function selectRole(roleName) {
  if (!roleInput) return;
  roleInput.value = roleName;
  if (roleClearBtn) roleClearBtn.hidden = false;
  if (roleMenu) roleMenu.hidden = true;
  roleInput.focus();
}

if (roleMenu) {
  roleMenu.addEventListener("click", (e) => {
    const item = e.target.closest(".autocomplete-item");
    if (item && item.dataset.role) {
      selectRole(item.dataset.role);
    }
  });
}

if (roleClearBtn) {
  roleClearBtn.addEventListener("click", () => {
    roleInput.value = "";
    roleClearBtn.hidden = true;
    roleMenu.hidden = true;
    roleInput.focus();
  });
}

document.addEventListener("click", (e) => {
  if (roleMenu && !e.target.closest(".role-input-group")) {
    roleMenu.hidden = true;
  }
});

// Clickable Role Suggestion Chips
document.querySelectorAll(".role-chip").forEach(chip => {
  chip.addEventListener("click", () => {
    const role = chip.dataset.role;
    if (role) selectRole(role);
  });
});

// 7. Helpers
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}

function renderKeywordTags(list, className, icon = "") {
  if (!list || !list.length) return `<span class="label-hint">None detected</span>`;
  return list.map(k => `<span class="keyword-tag ${className}">${icon} ${escapeHtml(k)}</span>`).join(" ");
}

function setBtnLoading(button, isLoading, normalHtml) {
  button.disabled = isLoading;
  if (isLoading) {
    button.innerHTML = `<span class="btn-spinner"></span> <span>Analyzing...</span>`;
  } else {
    button.innerHTML = normalHtml;
  }
}

// 8. ATS Resume Scoring (Job Description is 100% OPTIONAL)
const scoreBtn = document.getElementById("scoreBtn");
const jdInput = document.getElementById("jdInput");
const locationInput = document.getElementById("locationInput");
const scoreCard = document.getElementById("scoreCard");
const scoreCircle = document.getElementById("scoreCircle");
const gaugeProgress = document.getElementById("gaugeProgress");
const scoreRatingText = document.getElementById("scoreRatingText");
const scoreBenchmarkLabel = document.getElementById("scoreBenchmarkLabel");
const scoreDetails = document.getElementById("scoreDetails");

const originalScoreBtnHtml = scoreBtn ? scoreBtn.innerHTML : "Get ATS Score";

if (scoreBtn) {
  scoreBtn.addEventListener("click", async () => {
    const file = resumeFileInput?.files[0];
    const jd = jdInput?.value.trim() || "";
    const role = roleInput?.value.trim() || "";

    if (!file) {
      showToast("Please upload your resume file (.pdf or .docx) first.", "error");
      resumeDropzone?.scrollIntoView({ behavior: "smooth" });
      return;
    }

    setBtnLoading(scoreBtn, true, originalScoreBtnHtml);
    try {
      const formData = new FormData();
      formData.append("resume", file);
      formData.append("job_description", jd);
      formData.append("role", role);

      const res = await fetch(`${API_BASE}/api/score-resume`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to score resume.");
      }

      const data = await res.json();
      renderScore(data, jd, role);
      showToast("ATS scoring completed successfully!", "success");
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      setBtnLoading(scoreBtn, false, originalScoreBtnHtml);
    }
  });
}

function renderScore(data, jd, role) {
  if (!scoreCard) return;
  scoreCard.hidden = false;

  const score = Math.max(0, Math.min(100, data.score));
  scoreCircle.textContent = score;

  // Animate SVG gauge meter (circumference = 2 * PI * 52 ≈ 326.7)
  const circumference = 326.7;
  const offset = circumference - (score / 100) * circumference;
  if (gaugeProgress) {
    gaugeProgress.style.strokeDashoffset = offset;
    if (score >= 75) {
      gaugeProgress.style.stroke = "var(--emerald)";
      scoreRatingText.textContent = "Great Match / Ready to Apply";
      scoreRatingText.style.color = "#34d399";
    } else if (score >= 50) {
      gaugeProgress.style.stroke = "var(--amber)";
      scoreRatingText.textContent = "Moderate Match / Improvements Needed";
      scoreRatingText.style.color = "#fbbf24";
    } else {
      gaugeProgress.style.stroke = "var(--rose)";
      scoreRatingText.textContent = "Low Match / Needs Optimization";
      scoreRatingText.style.color = "#fb7185";
    }
  }

  // Set benchmark context label
  if (scoreBenchmarkLabel) {
    if (jd) {
      scoreBenchmarkLabel.textContent = "Targeted Job Description Match";
    } else if (role) {
      scoreBenchmarkLabel.textContent = `Role Benchmark: ${role}`;
    } else {
      scoreBenchmarkLabel.textContent = "General ATS Structural Health";
    }
  }

  let html = "";
  if (data.section_notes && data.section_notes.length) {
    html += `
      <div class="score-section-title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fbbf24" stroke-width="2"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
        Section Structure Notes (${data.section_notes.length})
      </div>
      <ul class="note-list">${data.section_notes.map(n => `<li>${escapeHtml(n)}</li>`).join("")}</ul>
    `;
  }

  if (data.formatting_notes && data.formatting_notes.length) {
    html += `
      <div class="score-section-title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
        Formatting & Parser Feedback (${data.formatting_notes.length})
      </div>
      <ul class="note-list">${data.formatting_notes.map(n => `<li>${escapeHtml(n)}</li>`).join("")}</ul>
    `;
  }

  const checkIcon = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
  const plusIcon = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>`;

  html += `
    <div class="score-section-title">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
      Matched Keywords (${(data.matched_keywords || []).length})
    </div>
    <div style="margin-bottom: 14px;">${renderKeywordTags(data.matched_keywords, "tag-matched", checkIcon)}</div>

    <div class="score-section-title">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fb7185" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
      Missing Keywords to Incorporate (${(data.missing_keywords || []).length})
    </div>
    <div>${renderKeywordTags(data.missing_keywords, "tag-missing", plusIcon)}</div>
  `;

  scoreDetails.innerHTML = html;
  scoreCard.scrollIntoView({ behavior: "smooth", block: "start" });
}

// 9. Job Search & Application Tracking
const searchBtn = document.getElementById("searchBtn");
const jobsCard = document.getElementById("jobsCard");
const toApplyList = document.getElementById("toApplyList");
const appliedList = document.getElementById("appliedList");
const toApplyCount = document.getElementById("toApplyCount");
const appliedCount = document.getElementById("appliedCount");
const toApplyBadge = document.getElementById("toApplyBadge");
const appliedBadge = document.getElementById("appliedBadge");

const originalSearchBtnHtml = searchBtn ? searchBtn.innerHTML : "Find Matching Jobs";

if (searchBtn) {
  searchBtn.addEventListener("click", async () => {
    const role = roleInput?.value.trim();
    if (!role) {
      showToast("Please enter a Target Role first.", "error");
      roleInput?.focus();
      return;
    }

    setBtnLoading(searchBtn, true, originalSearchBtnHtml);
    try {
      const formData = new FormData();
      formData.append("role", role);
      formData.append("location", locationInput?.value.trim() || "");
      const file = resumeFileInput?.files[0];
      if (file) formData.append("resume", file);

      const res = await fetch(`${API_BASE}/api/search-jobs`, {
        method: "POST",
        headers: authHeaders(),
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to search jobs.");
      }

      const data = await res.json();
      renderJobs(data);
      showToast(`Found ${data.to_apply_count + data.applied_count} matching listings!`, "success");
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      setBtnLoading(searchBtn, false, originalSearchBtnHtml);
    }
  });
}

function jobCardHtml(job, isApplied) {
  const verdictMap = {
    likely_legit: { label: "Likely Legit", class: "badge-likely_legit" },
    verify: { label: "Verify Company", class: "badge-verify" },
    high_risk: { label: "High Risk Warning", class: "badge-high_risk" },
  };
  const verdictInfo = verdictMap[job.legitimacy_verdict] || { label: job.legitimacy_verdict, class: "badge-verify" };

  return `
    <div class="job-item ${isApplied ? "is-applied" : ""}" data-job-id="${escapeHtml(job.job_id)}">
      <div class="job-top-bar">
        <span class="badge ${verdictInfo.class}">● ${verdictInfo.label}</span>
        <span class="badge-optional">${escapeHtml(job.source)}</span>
      </div>

      <h3>${escapeHtml(job.title)}</h3>
      <div class="job-meta">
        <strong>${escapeHtml(job.company)}</strong>
        <span>•</span>
        <span>📍 ${escapeHtml(job.location || "Remote / India")}</span>
      </div>

      <p class="job-desc-snippet">${escapeHtml(job.description_snippet || "")}</p>

      ${job.matched_keywords && job.matched_keywords.length ? `
        <div style="margin-bottom: 8px;">
          <span class="label-hint">Resume matches:</span>
          ${renderKeywordTags(job.matched_keywords.slice(0, 5), "tag-matched")}
        </div>
      ` : ""}

      ${job.missing_keywords && job.missing_keywords.length ? `
        <div style="margin-bottom: 8px;">
          <span class="label-hint">Key skill gaps:</span>
          ${renderKeywordTags(job.missing_keywords.slice(0, 4), "tag-missing")}
        </div>
      ` : ""}

      <div class="job-action-row">
        <a class="apply-link" href="${escapeHtml(job.apply_url)}" target="_blank" rel="noopener noreferrer">
          <span>Apply on Source</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
        </a>

        ${authToken ? `
          <button type="button" class="btn btn-sm ${isApplied ? "btn-secondary" : "btn-primary"}" data-action="${isApplied ? "unmark" : "mark"}">
            ${isApplied ? "Move to To Apply" : "Mark as Applied"}
          </button>
        ` : `
          <button type="button" class="btn btn-sm btn-secondary" onclick="showToast('Sign in to track applied listings!', 'info')">
            Mark Applied
          </button>
        `}
      </div>

      <details class="details-expander">
        <summary>Why this verdict? Details & heuristic report</summary>
        <ul class="note-list">
          ${(job.legitimacy_reasons || []).map(r => `<li>${escapeHtml(r)}</li>`).join("")}
        </ul>
      </details>
    </div>
  `;
}

function renderJobs(data) {
  if (!jobsCard) return;
  jobsCard.hidden = false;

  const toApplyNum = data.to_apply_count || (data.to_apply ? data.to_apply.length : 0);
  const appliedNum = data.applied_count || (data.applied ? data.applied.length : 0);

  if (toApplyCount) toApplyCount.textContent = toApplyNum;
  if (appliedCount) appliedCount.textContent = appliedNum;
  if (toApplyBadge) toApplyBadge.textContent = toApplyNum;
  if (appliedBadge) appliedBadge.textContent = appliedNum;

  if (toApplyList) {
    toApplyList.innerHTML = data.to_apply && data.to_apply.length
      ? data.to_apply.map(j => jobCardHtml(j, false)).join("")
      : `<div class="empty-col-note">No new opportunities in this column.</div>`;
  }

  if (appliedList) {
    appliedList.innerHTML = data.applied && data.applied.length
      ? data.applied.map(j => jobCardHtml(j, true)).join("")
      : `<div class="empty-col-note">No jobs marked as applied yet.</div>`;
  }

  jobsCard.scrollIntoView({ behavior: "smooth", block: "start" });
}

// 10. Segmented View Switcher Tabs (Mobile / Filter Tabs)
const viewAllTab = document.getElementById("viewAllTab");
const viewToApplyTab = document.getElementById("viewToApplyTab");
const viewAppliedTab = document.getElementById("viewAppliedTab");
const colToApply = document.getElementById("colToApply");
const colApplied = document.getElementById("colApplied");

function setJobTab(activeTab, showToApply, showApplied) {
  [viewAllTab, viewToApplyTab, viewAppliedTab].forEach(t => t && t.classList.remove("active"));
  if (activeTab) activeTab.classList.add("active");
  if (colToApply) colToApply.style.display = showToApply ? "block" : "none";
  if (colApplied) colApplied.style.display = showApplied ? "block" : "none";
}

if (viewAllTab) viewAllTab.addEventListener("click", () => setJobTab(viewAllTab, true, true));
if (viewToApplyTab) viewToApplyTab.addEventListener("click", () => setJobTab(viewToApplyTab, true, false));
if (viewAppliedTab) viewAppliedTab.addEventListener("click", () => setJobTab(viewAppliedTab, false, true));

// 11. Event Delegation for Mark/Unmark Applied
if (jobsCard) {
  jobsCard.addEventListener("click", async (e) => {
    const button = e.target.closest("button[data-action]");
    if (!button) return;

    if (!authToken) {
      showToast("Please log in above to save applied listings.", "info");
      return;
    }

    const jobItem = button.closest(".job-item");
    const jobId = jobItem?.dataset?.jobId;
    const action = button.dataset.action;
    if (!jobId) return;

    button.disabled = true;
    const originalText = button.textContent;
    button.textContent = "Updating...";

    try {
      if (action === "mark") {
        const titleEl = jobItem.querySelector("h3");
        const metaText = jobItem.querySelector(".job-meta")?.textContent || "";
        const applyUrl = jobItem.querySelector(".apply-link")?.href || "";
        const [company] = metaText.split("•").map(s => s.trim());
        const source = jobItem.querySelector(".badge-optional")?.textContent || "Web";

        await fetch(`${API_BASE}/api/applications`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({
            job_id: jobId,
            title: titleEl?.textContent || "Job Position",
            company: company || "Company",
            apply_url: applyUrl,
            source: source.trim(),
          }),
        });
        showToast("Job moved to Applied column!", "success");
      } else {
        await fetch(`${API_BASE}/api/applications/${jobId}`, {
          method: "DELETE",
          headers: authHeaders(),
        });
        showToast("Job moved back to To Apply.", "info");
      }
      // Re-trigger search to sync columns
      searchBtn.click();
    } catch (err) {
      showToast("Could not update application status. Please retry.", "error");
      button.disabled = false;
      button.textContent = originalText;
    }
  });
}
