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

// 6. Target Role Autocomplete & Comprehensive 95+ Role Dropdown
const POPULAR_ROLES = [
  // Software & Web Engineering (26 roles)
  { role: "Full Stack Developer", cat: "Software Engineering", icon: "💻" },
  { role: "Frontend Developer", cat: "Software Engineering", icon: "🌐" },
  { role: "Backend Engineer", cat: "Software Engineering", icon: "⚙️" },
  { role: "Software Engineer", cat: "Software Engineering", icon: "💻" },
  { role: "Senior Software Engineer", cat: "Software Engineering", icon: "🚀" },
  { role: "Staff Software Engineer", cat: "Software Engineering", icon: "🏆" },
  { role: "Lead Software Engineer", cat: "Software Engineering", icon: "⭐" },
  { role: "React Developer", cat: "Software Engineering", icon: "⚛️" },
  { role: "Angular Developer", cat: "Software Engineering", icon: "🅰️" },
  { role: "Vue.js Developer", cat: "Software Engineering", icon: "💚" },
  { role: "Next.js / Node.js Developer", cat: "Software Engineering", icon: "⚡" },
  { role: "Node.js Backend Developer", cat: "Software Engineering", icon: "🟢" },
  { role: "Python Developer", cat: "Software Engineering", icon: "🐍" },
  { role: "Django / FastAPI Developer", cat: "Software Engineering", icon: "⚡" },
  { role: "Java Developer", cat: "Software Engineering", icon: "☕" },
  { role: "Spring Boot Developer", cat: "Software Engineering", icon: "🍃" },
  { role: "Golang Engineer", cat: "Software Engineering", icon: "🐹" },
  { role: "C++ Systems Engineer", cat: "Software Engineering", icon: "⚡" },
  { role: "C# / .NET Developer", cat: "Software Engineering", icon: "🔷" },
  { role: "Rust Systems Developer", cat: "Software Engineering", icon: "🦀" },
  { role: "Ruby on Rails Developer", cat: "Software Engineering", icon: "💎" },
  { role: "PHP / Laravel Developer", cat: "Software Engineering", icon: "🐘" },
  { role: "Embedded Systems Engineer", cat: "Software Engineering", icon: "🔌" },
  { role: "Firmware Engineer", cat: "Software Engineering", icon: "💾" },
  { role: "Systems Software Engineer", cat: "Software Engineering", icon: "🖥️" },
  { role: "Game Developer (Unity / Unreal)", cat: "Software Engineering", icon: "🎮" },

  // Mobile Engineering (6 roles)
  { role: "Mobile App Developer", cat: "Mobile Engineering", icon: "📱" },
  { role: "iOS Developer (Swift)", cat: "Mobile Engineering", icon: "🍎" },
  { role: "Android Developer (Kotlin)", cat: "Mobile Engineering", icon: "🤖" },
  { role: "Flutter Developer", cat: "Mobile Engineering", icon: "💙" },
  { role: "React Native Developer", cat: "Mobile Engineering", icon: "⚛️" },
  { role: "Cross-Platform Mobile Engineer", cat: "Mobile Engineering", icon: "📲" },

  // AI, Machine Learning & Data Science (15 roles)
  { role: "Machine Learning Engineer", cat: "AI & Data Science", icon: "🤖" },
  { role: "AI Engineer", cat: "AI & Data Science", icon: "🧠" },
  { role: "Generative AI / LLM Engineer", cat: "AI & Data Science", icon: "✨" },
  { role: "Deep Learning Engineer", cat: "AI & Data Science", icon: "🔮" },
  { role: "Computer Vision Engineer", cat: "AI & Data Science", icon: "👁️" },
  { role: "Natural Language Processing (NLP) Engineer", cat: "AI & Data Science", icon: "💬" },
  { role: "MLOps Engineer", cat: "AI & Data Science", icon: "🔄" },
  { role: "Data Scientist", cat: "AI & Data Science", icon: "🔬" },
  { role: "Senior Data Scientist", cat: "AI & Data Science", icon: "📊" },
  { role: "Data Analyst", cat: "AI & Data Science", icon: "📈" },
  { role: "Business Intelligence (BI) Analyst", cat: "AI & Data Science", icon: "📉" },
  { role: "Data Engineer", cat: "AI & Data Science", icon: "🏗️" },
  { role: "Analytics Engineer", cat: "AI & Data Science", icon: "📐" },
  { role: "Database Administrator (DBA)", cat: "AI & Data Science", icon: "🗄️" },
  { role: "Quantitative Analyst / FinTech Data", cat: "AI & Data Science", icon: "💹" },

  // Cloud, DevOps & SRE (9 roles)
  { role: "DevOps Engineer", cat: "Cloud & DevOps", icon: "♾️" },
  { role: "Cloud Engineer (AWS / Azure / GCP)", cat: "Cloud & DevOps", icon: "☁️" },
  { role: "Cloud Architect", cat: "Cloud & DevOps", icon: "🏛️" },
  { role: "Site Reliability Engineer (SRE)", cat: "Cloud & DevOps", icon: "🚨" },
  { role: "Platform Engineer", cat: "Cloud & DevOps", icon: "🛠️" },
  { role: "Infrastructure Engineer", cat: "Cloud & DevOps", icon: "🏢" },
  { role: "Kubernetes / Cloud Native Engineer", cat: "Cloud & DevOps", icon: "☸️" },
  { role: "Linux Systems Administrator", cat: "Cloud & DevOps", icon: "🐧" },
  { role: "Network Security Engineer", cat: "Cloud & DevOps", icon: "🌐" },

  // Cybersecurity & InfoSec (7 roles)
  { role: "Cybersecurity Analyst", cat: "Cybersecurity", icon: "🛡️" },
  { role: "Information Security Engineer", cat: "Cybersecurity", icon: "🔒" },
  { role: "SOC Analyst (Security Operations)", cat: "Cybersecurity", icon: "🚨" },
  { role: "Penetration Tester / Ethical Hacker", cat: "Cybersecurity", icon: "🎯" },
  { role: "Application Security (AppSec) Engineer", cat: "Cybersecurity", icon: "🛡️" },
  { role: "Cloud Security Architect", cat: "Cybersecurity", icon: "☁️" },
  { role: "Identity and Access Management (IAM) Specialist", cat: "Cybersecurity", icon: "🔑" },

  // QA & Testing (SDET) (6 roles)
  { role: "QA Engineer", cat: "QA & Testing", icon: "🧪" },
  { role: "Software Development Engineer in Test (SDET)", cat: "QA & Testing", icon: "🔍" },
  { role: "Automation Test Engineer (Selenium / Playwright)", cat: "QA & Testing", icon: "🤖" },
  { role: "Manual QA Tester", cat: "QA & Testing", icon: "📋" },
  { role: "Performance & Load Test Engineer", cat: "QA & Testing", icon: "⚡" },
  { role: "API Test Engineer", cat: "QA & Testing", icon: "🔌" },

  // Product & Project Management (9 roles)
  { role: "Product Manager", cat: "Product & Management", icon: "💡" },
  { role: "Technical Product Manager (TPM)", cat: "Product & Management", icon: "⚙️" },
  { role: "Associate Product Manager (APM)", cat: "Product & Management", icon: "🌱" },
  { role: "Product Owner", cat: "Product & Management", icon: "🎯" },
  { role: "Project Manager", cat: "Product & Management", icon: "📋" },
  { role: "Scrum Master", cat: "Product & Management", icon: "🏃" },
  { role: "Agile Coach", cat: "Product & Management", icon: "🧭" },
  { role: "IT Project Manager", cat: "Product & Management", icon: "💼" },
  { role: "Business Analyst", cat: "Product & Management", icon: "📊" },

  // UI/UX & Product Design (6 roles)
  { role: "UI/UX Designer", cat: "Design & UX", icon: "🎨" },
  { role: "Product Designer", cat: "Design & UX", icon: "✨" },
  { role: "UX Researcher", cat: "Design & UX", icon: "🔍" },
  { role: "Visual Designer", cat: "Design & UX", icon: "👁️" },
  { role: "Interaction Designer", cat: "Design & UX", icon: "📐" },
  { role: "Design Systems Lead", cat: "Design & UX", icon: "🧩" },

  // Web3 & Blockchain (4 roles)
  { role: "Blockchain Developer", cat: "Web3 & Blockchain", icon: "⛓️" },
  { role: "Solidity / Smart Contract Engineer", cat: "Web3 & Blockchain", icon: "📜" },
  { role: "Web3 Full Stack Developer", cat: "Web3 & Blockchain", icon: "🌐" },
  { role: "Smart Contract Security Auditor", cat: "Web3 & Blockchain", icon: "🔍" },

  // Solutions, Support & Growth (6 roles)
  { role: "Solutions Architect", cat: "Solutions & Support", icon: "🏛️" },
  { role: "Technical Support Engineer", cat: "Solutions & Support", icon: "🎧" },
  { role: "Customer Success Engineer", cat: "Solutions & Support", icon: "🤝" },
  { role: "Sales Engineer / Pre-Sales", cat: "Solutions & Support", icon: "💼" },
  { role: "Developer Relations (DevRel) Engineer", cat: "Solutions & Support", icon: "🥑" },
  { role: "Technical Writer / Documentation Specialist", cat: "Solutions & Support", icon: "📝" },
];

const roleInput = document.getElementById("roleInput");
const roleMenu = document.getElementById("roleSuggestionsMenu");
const roleClearBtn = document.getElementById("roleClearBtn");
const roleDropdownToggle = document.getElementById("roleDropdownToggle");
let selectedSuggestionIndex = -1;

function closeRoleDropdown() {
  if (roleMenu) roleMenu.hidden = true;
  if (roleDropdownToggle) roleDropdownToggle.classList.remove("open");
  selectedSuggestionIndex = -1;
}

function syncRoleChips(currentVal) {
  const normalized = (currentVal || "").trim().toLowerCase();
  document.querySelectorAll(".role-chip").forEach(chip => {
    const chipVal = (chip.dataset.role || "").toLowerCase();
    const isActive = normalized && (chipVal === normalized || normalized.includes(chipVal));
    chip.classList.toggle("active", Boolean(isActive));
  });
}

function selectRole(roleName) {
  if (!roleInput) return;
  roleInput.value = roleName;
  if (roleClearBtn) roleClearBtn.hidden = !roleName;
  closeRoleDropdown();
  syncRoleChips(roleName);
  roleInput.focus();
}

function updateSelectedSuggestion(items) {
  items.forEach((item, idx) => {
    item.classList.toggle("selected", idx === selectedSuggestionIndex);
    if (idx === selectedSuggestionIndex) {
      item.scrollIntoView({ block: "nearest" });
    }
  });
}

function renderRoleSuggestions(query = "") {
  if (!roleMenu) return;
  const q = query.trim().toLowerCase();

  let matches = [];
  if (!q) {
    matches = [...POPULAR_ROLES];
  } else {
    matches = POPULAR_ROLES.filter(item =>
      item.role.toLowerCase().includes(q) || item.cat.toLowerCase().includes(q)
    );
  }

  selectedSuggestionIndex = -1;

  if (matches.length === 0) {
    roleMenu.innerHTML = `
      <div class="autocomplete-item role-item" data-index="0" data-role="${escapeHtml(query.trim())}">
        <span class="role-item-left">
          <span class="role-item-icon">🎯</span>
          <span class="role-item-text">Use "<strong>${escapeHtml(query.trim())}</strong>"</span>
        </span>
        <span class="autocomplete-category">Custom Role</span>
      </div>
    `;
    roleMenu.hidden = false;
    if (roleDropdownToggle) roleDropdownToggle.classList.add("open");
    return;
  }

  let html = "";
  let lastCategory = "";

  matches.forEach((item, idx) => {
    if (!q && item.cat !== lastCategory) {
      lastCategory = item.cat;
      html += `<div class="role-group-header">${escapeHtml(lastCategory)}</div>`;
    }

    let displayTitle = escapeHtml(item.role);
    if (q) {
      const regex = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, "gi");
      displayTitle = displayTitle.replace(regex, `<span class="autocomplete-highlight">$1</span>`);
    }

    html += `
      <div class="autocomplete-item role-item" data-index="${idx}" data-role="${escapeHtml(item.role)}">
        <span class="role-item-left">
          <span class="role-item-icon">${item.icon || "💻"}</span>
          <span class="role-item-text">${displayTitle}</span>
        </span>
        <span class="autocomplete-category">${escapeHtml(item.cat)}</span>
      </div>
    `;
  });

  // If user typed a query that is not an exact match to any predefined role, append custom 1-click fallback
  const exactMatchExists = matches.some(m => m.role.toLowerCase() === q);
  if (q && !exactMatchExists) {
    html += `
      <div class="autocomplete-item role-item custom-role-item" data-index="${matches.length}" data-role="${escapeHtml(query.trim())}">
        <span class="role-item-left">
          <span class="role-item-icon">🎯</span>
          <span class="role-item-text">Use "<strong>${escapeHtml(query.trim())}</strong>"</span>
        </span>
        <span class="autocomplete-category">Custom Role</span>
      </div>
    `;
  }

  roleMenu.innerHTML = html;
  roleMenu.hidden = false;
  if (roleDropdownToggle) roleDropdownToggle.classList.add("open");
}

if (roleInput) {
  roleInput.addEventListener("input", (e) => {
    const val = e.target.value;
    if (roleClearBtn) roleClearBtn.hidden = !val;
    syncRoleChips(val);
    renderRoleSuggestions(val);
  });

  roleInput.addEventListener("focus", () => {
    renderRoleSuggestions(roleInput.value);
  });

  roleInput.addEventListener("keydown", (e) => {
    if (roleMenu.hidden) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        renderRoleSuggestions(roleInput.value);
      }
      return;
    }
    const items = roleMenu.querySelectorAll(".role-item");
    if (!items.length) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      selectedSuggestionIndex = (selectedSuggestionIndex + 1) % items.length;
      updateSelectedSuggestion(items);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      selectedSuggestionIndex = (selectedSuggestionIndex - 1 + items.length) % items.length;
      updateSelectedSuggestion(items);
    } else if (e.key === "Enter") {
      if (selectedSuggestionIndex >= 0 && items[selectedSuggestionIndex]) {
        e.preventDefault();
        selectRole(items[selectedSuggestionIndex].dataset.role);
      } else if (roleInput.value.trim()) {
        closeRoleDropdown();
      }
    } else if (e.key === "Escape") {
      closeRoleDropdown();
    }
  });
}

if (roleDropdownToggle) {
  roleDropdownToggle.addEventListener("click", (e) => {
    e.stopPropagation();
    if (!roleMenu.hidden) {
      closeRoleDropdown();
    } else {
      renderRoleSuggestions(roleInput?.value || "");
      roleInput?.focus();
    }
  });
}

if (roleClearBtn) {
  roleClearBtn.addEventListener("click", () => {
    if (roleInput) roleInput.value = "";
    roleClearBtn.hidden = true;
    syncRoleChips("");
    closeRoleDropdown();
    roleInput?.focus();
  });
}

if (roleMenu) {
  roleMenu.addEventListener("click", (e) => {
    const item = e.target.closest(".role-item");
    if (item && item.dataset.role) {
      selectRole(item.dataset.role);
    }
  });
}

document.addEventListener("click", (e) => {
  if (roleMenu && !e.target.closest(".role-input-group")) {
    closeRoleDropdown();
  }
});

// Clickable Role Suggestion Chips
document.querySelectorAll(".role-chip").forEach(chip => {
  chip.addEventListener("click", () => {
    const role = chip.dataset.role;
    if (role) {
      if (roleInput?.value === role) {
        selectRole("");
      } else {
        selectRole(role);
      }
    }
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

// 7b. Target Location Dropdown & Suggestions
const POPULAR_LOCATIONS = [
  // Nationwide Countries (Auto-matches all states & regional tech hubs)
  { name: "India (All States / Nationwide)", cat: "Nationwide", icon: "🇮🇳" },
  { name: "United States (Nationwide)", cat: "Nationwide", icon: "🇺🇸" },
  { name: "United Kingdom (Nationwide)", cat: "Nationwide", icon: "🇬🇧" },
  { name: "Canada (Nationwide)", cat: "Nationwide", icon: "🇨🇦" },
  { name: "Germany (Nationwide)", cat: "Nationwide", icon: "🇩🇪" },
  { name: "Australia (Nationwide)", cat: "Nationwide", icon: "🇦🇺" },
  { name: "Singapore (Nationwide)", cat: "Nationwide", icon: "🇸🇬" },
  { name: "Remote (Global / Anywhere)", cat: "Remote", icon: "🌐" },
  { name: "Remote (India)", cat: "Remote", icon: "💻" },
  { name: "Remote (US / Americas)", cat: "Remote", icon: "🌎" },
  { name: "Remote (Europe / UK)", cat: "Remote", icon: "🌍" },

  // Top Indian Tech Hubs
  { name: "Bengaluru, India", cat: "India Hubs", icon: "📍" },
  { name: "Hyderabad, India", cat: "India Hubs", icon: "📍" },
  { name: "Pune, India", cat: "India Hubs", icon: "📍" },
  { name: "Delhi NCR (Gurgaon / Noida), India", cat: "India Hubs", icon: "📍" },
  { name: "Mumbai, India", cat: "India Hubs", icon: "📍" },
  { name: "Chennai, India", cat: "India Hubs", icon: "📍" },
  { name: "Kolkata, India", cat: "India Hubs", icon: "📍" },
  { name: "Ahmedabad, India", cat: "India Hubs", icon: "📍" },
  { name: "Kochi, India", cat: "India Hubs", icon: "📍" },
  { name: "Chandigarh, India", cat: "India Hubs", icon: "📍" },

  // North America
  { name: "San Francisco Bay Area, US", cat: "North America", icon: "📍" },
  { name: "New York, US", cat: "North America", icon: "📍" },
  { name: "Seattle, WA, US", cat: "North America", icon: "📍" },
  { name: "Austin, TX, US", cat: "North America", icon: "📍" },
  { name: "Boston, MA, US", cat: "North America", icon: "📍" },
  { name: "Toronto, Canada", cat: "North America", icon: "📍" },
  { name: "Vancouver, Canada", cat: "North America", icon: "📍" },

  // Europe & UK
  { name: "London, UK", cat: "Europe & UK", icon: "🇬🇧" },
  { name: "Berlin, Germany", cat: "Europe & UK", icon: "🇩🇪" },
  { name: "Amsterdam, Netherlands", cat: "Europe & UK", icon: "🇳🇱" },
  { name: "Dublin, Ireland", cat: "Europe & UK", icon: "🇮🇪" },
  { name: "Paris, France", cat: "Europe & UK", icon: "🇫🇷" },
  { name: "Zurich, Switzerland", cat: "Europe & UK", icon: "🇨🇭" },

  // Asia-Pacific & Middle East
  { name: "Sydney, Australia", cat: "Asia-Pacific", icon: "🇦🇺" },
  { name: "Dubai, UAE", cat: "Middle East", icon: "🇦🇪" },
  { name: "Tokyo, Japan", cat: "Asia-Pacific", icon: "🇯🇵" },
];

const locationInput = document.getElementById("locationInput");
const locationMenu = document.getElementById("locationSuggestionsMenu");
const locationClearBtn = document.getElementById("locationClearBtn");
const locationDropdownToggle = document.getElementById("locationDropdownToggle");
let selectedLocationIndex = -1;

function closeLocationDropdown() {
  if (locationMenu) locationMenu.hidden = true;
  if (locationDropdownToggle) locationDropdownToggle.classList.remove("open");
  selectedLocationIndex = -1;
}

function syncLocationChips(currentVal) {
  const normalized = (currentVal || "").trim().toLowerCase();
  document.querySelectorAll(".location-chip").forEach(chip => {
    const chipVal = (chip.dataset.location || "").toLowerCase();
    const isActive = normalized && (chipVal === normalized || normalized.startsWith(chipVal));
    chip.classList.toggle("active", Boolean(isActive));
  });
}

function selectLocation(locName) {
  if (!locationInput) return;
  locationInput.value = locName;
  if (locationClearBtn) locationClearBtn.hidden = !locName;
  closeLocationDropdown();
  syncLocationChips(locName);
}

function updateSelectedLocation(items) {
  items.forEach((item, idx) => {
    item.classList.toggle("selected", idx === selectedLocationIndex);
    if (idx === selectedLocationIndex) {
      item.scrollIntoView({ block: "nearest" });
    }
  });
}

function renderLocationDropdown(query = "") {
  if (!locationMenu) return;
  const q = query.trim().toLowerCase();

  let matches = [];
  if (!q) {
    matches = [...POPULAR_LOCATIONS];
  } else {
    matches = POPULAR_LOCATIONS.filter(item =>
      item.name.toLowerCase().includes(q) || item.cat.toLowerCase().includes(q)
    );
  }

  selectedLocationIndex = -1;

  if (matches.length === 0) {
    locationMenu.innerHTML = `
      <div class="autocomplete-item location-item" data-index="0" data-location="${escapeHtml(query.trim())}">
        <span class="location-item-left">
          <span class="location-item-icon">📍</span>
          <span class="location-item-text">Use "<strong>${escapeHtml(query.trim())}</strong>"</span>
        </span>
        <span class="autocomplete-category">Custom</span>
      </div>
    `;
    locationMenu.hidden = false;
    if (locationDropdownToggle) locationDropdownToggle.classList.add("open");
    return;
  }

  let html = "";
  let lastCategory = "";

  matches.forEach((item, idx) => {
    if (!q && item.cat !== lastCategory) {
      lastCategory = item.cat;
      html += `<div class="location-group-header">${escapeHtml(lastCategory)}</div>`;
    }

    let displayTitle = escapeHtml(item.name);
    if (q) {
      const regex = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, "gi");
      displayTitle = displayTitle.replace(regex, `<span class="autocomplete-highlight">$1</span>`);
    }

    html += `
      <div class="autocomplete-item location-item" data-index="${idx}" data-location="${escapeHtml(item.name)}">
        <span class="location-item-left">
          <span class="location-item-icon">${item.icon || "📍"}</span>
          <span class="location-item-text">${displayTitle}</span>
        </span>
        <span class="autocomplete-category">${escapeHtml(item.cat)}</span>
      </div>
    `;
  });

  locationMenu.innerHTML = html;
  locationMenu.hidden = false;
  if (locationDropdownToggle) locationDropdownToggle.classList.add("open");
}

if (locationInput) {
  locationInput.addEventListener("input", (e) => {
    const val = e.target.value;
    if (locationClearBtn) locationClearBtn.hidden = !val;
    syncLocationChips(val);
    renderLocationDropdown(val);
  });

  locationInput.addEventListener("focus", () => {
    renderLocationDropdown(locationInput.value);
  });

  locationInput.addEventListener("keydown", (e) => {
    if (locationMenu.hidden) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        renderLocationDropdown(locationInput.value);
      }
      return;
    }
    const items = locationMenu.querySelectorAll(".location-item");
    if (!items.length) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      selectedLocationIndex = (selectedLocationIndex + 1) % items.length;
      updateSelectedLocation(items);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      selectedLocationIndex = (selectedLocationIndex - 1 + items.length) % items.length;
      updateSelectedLocation(items);
    } else if (e.key === "Enter") {
      if (selectedLocationIndex >= 0 && items[selectedLocationIndex]) {
        e.preventDefault();
        selectLocation(items[selectedLocationIndex].dataset.location);
      } else if (locationInput.value.trim()) {
        closeLocationDropdown();
      }
    } else if (e.key === "Escape") {
      closeLocationDropdown();
    }
  });
}

if (locationDropdownToggle) {
  locationDropdownToggle.addEventListener("click", (e) => {
    e.stopPropagation();
    if (!locationMenu.hidden) {
      closeLocationDropdown();
    } else {
      renderLocationDropdown(locationInput?.value || "");
      locationInput?.focus();
    }
  });
}

if (locationClearBtn) {
  locationClearBtn.addEventListener("click", () => {
    if (locationInput) locationInput.value = "";
    locationClearBtn.hidden = true;
    syncLocationChips("");
    closeLocationDropdown();
    locationInput?.focus();
  });
}

if (locationMenu) {
  locationMenu.addEventListener("click", (e) => {
    const item = e.target.closest(".location-item");
    if (item && item.dataset.location) {
      selectLocation(item.dataset.location);
    }
  });
}

document.addEventListener("click", (e) => {
  if (locationMenu && !e.target.closest(".location-input-group")) {
    closeLocationDropdown();
  }
});

// Clickable Location Suggestion Chips
document.querySelectorAll(".location-chip").forEach(chip => {
  chip.addEventListener("click", () => {
    const loc = chip.dataset.location;
    if (loc) {
      if (locationInput?.value === loc) {
        selectLocation("");
      } else {
        selectLocation(loc);
      }
    }
  });
});

// 8. ATS Resume Scoring (Job Description is 100% OPTIONAL)
const scoreBtn = document.getElementById("scoreBtn");
const jdInput = document.getElementById("jdInput");
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
    if (score >= 82) {
      gaugeProgress.style.stroke = "var(--emerald)";
      scoreRatingText.textContent = "High Recruiter Pass Rate (90%+)";
      scoreRatingText.style.color = "#34d399";
    } else if (score >= 65) {
      gaugeProgress.style.stroke = "var(--amber)";
      scoreRatingText.textContent = "Borderline / Needs Optimization";
      scoreRatingText.style.color = "#fbbf24";
    } else {
      gaugeProgress.style.stroke = "var(--rose)";
      scoreRatingText.textContent = "High Filter Rejection Risk";
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

  // 1. Recruiter Determination & Verdict Banner
  const verdictClass = score >= 82 ? "verdict-strong" : (score >= 65 ? "verdict-warning" : "verdict-risk");
  const verdictIcon = score >= 82 ? "🟢" : (score >= 65 ? "🟡" : "🔴");
  const verdictTitle = data.verdict || (score >= 82 ? "Strong ATS Pass" : (score >= 65 ? "Borderline Pass" : "High Screening Risk"));
  const passProb = data.pass_probability || `${score}% Match Rate`;
  const recruiterSummary = data.recruiter_summary || "Automated recruiter ATS evaluation based on keywords, metrics, and parseability.";

  html += `
    <div class="recruiter-verdict-banner ${verdictClass}">
      <div class="verdict-header-row">
        <div class="verdict-title">${verdictIcon} ${escapeHtml(verdictTitle)}</div>
        <div class="verdict-probability-tag">${escapeHtml(passProb)}</div>
      </div>
      <p class="recruiter-summary-text">${escapeHtml(recruiterSummary)}</p>
    </div>
  `;

  // 2. Four Pillars Scorecard
  const pillars = data.pillar_scores || {
    skills_match: score,
    quantified_metrics: data.quantified_impact_score || 60,
    action_verbs: data.action_verbs_score || 70,
    ats_parseability: 85,
  };

  const getFillColor = (val) => val >= 75 ? "fill-green" : (val >= 50 ? "fill-amber" : "fill-rose");

  html += `
    <div class="score-section-title">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>
      Recruiter ATS 4-Pillar Evaluation Breakdown
    </div>
    <div class="pillar-scorecard-grid">
      <div class="pillar-item">
        <div class="pillar-label">
          <span>Technical Skills</span>
          <span class="pillar-score-val">${pillars.skills_match || 0}%</span>
        </div>
        <div class="pillar-track"><div class="pillar-fill ${getFillColor(pillars.skills_match || 0)}" style="width: ${pillars.skills_match || 0}%;"></div></div>
      </div>
      <div class="pillar-item">
        <div class="pillar-label">
          <span>Quantified Metrics</span>
          <span class="pillar-score-val">${pillars.quantified_metrics || 0}%</span>
        </div>
        <div class="pillar-track"><div class="pillar-fill ${getFillColor(pillars.quantified_metrics || 0)}" style="width: ${pillars.quantified_metrics || 0}%;"></div></div>
      </div>
      <div class="pillar-item">
        <div class="pillar-label">
          <span>Action Verbs</span>
          <span class="pillar-score-val">${pillars.action_verbs || 0}%</span>
        </div>
        <div class="pillar-track"><div class="pillar-fill ${getFillColor(pillars.action_verbs || 0)}" style="width: ${pillars.action_verbs || 0}%;"></div></div>
      </div>
      <div class="pillar-item">
        <div class="pillar-label">
          <span>ATS Parseability</span>
          <span class="pillar-score-val">${pillars.ats_parseability || 0}%</span>
        </div>
        <div class="pillar-track"><div class="pillar-fill ${getFillColor(pillars.ats_parseability || 0)}" style="width: ${pillars.ats_parseability || 0}%;"></div></div>
      </div>
    </div>
  `;

  // 3. Ready-to-Paste STAR Bullets to Guarantee Pass
  if (data.recommended_bullets && data.recommended_bullets.length) {
    html += `
      <div class="star-bullets-wrapper">
        <div class="score-section-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
          Direct Pass Recommendations: Ready-to-Paste STAR Bullet Points
        </div>
        <div class="star-bullets-header-box">
          <span>💡 <strong>1-Click Pass Guarantee:</strong> Copy and paste these pre-crafted bullet points directly into your Work Experience to embed missing keywords, STAR metrics, and high-impact action verbs.</span>
        </div>
        ${data.recommended_bullets.map((b) => `
          <div class="star-bullet-card">
            <div class="star-card-top">
              <span class="star-bullet-kw">+ ${escapeHtml(b.keyword)}</span>
              <button type="button" class="btn-copy-bullet" data-bullet="${escapeHtml(b.bullet)}" title="Copy bullet to clipboard">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                <span>Copy Bullet</span>
              </button>
            </div>
            <p class="star-bullet-content">• ${escapeHtml(b.bullet)}</p>
          </div>
        `).join("")}
      </div>
    `;
  }

  // 4. Passive Phrases to Eliminate & Power Verb Rewrites
  if (data.weak_phrase_replacements && data.weak_phrase_replacements.length) {
    html += `
      <div class="score-section-title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fbbf24" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
        Action Verb Optimization: Replace Weak Phrasing
      </div>
      ${data.weak_phrase_replacements.map(wp => `
        <div class="weak-phrase-box">
          <div class="phrase-compare-row">
            <span class="phrase-weak">${escapeHtml(wp.weak)}</span>
            <span class="phrase-arrow">➔</span>
            <span class="phrase-fix">${escapeHtml(wp.replacement)}</span>
          </div>
          <p class="phrase-tip">${escapeHtml(wp.tip)}</p>
        </div>
      `).join("")}
    `;
  }

  // 5. Direct Pass Guarantee Checklist
  if (data.pass_checklist && data.pass_checklist.length) {
    html += `
      <div class="pass-checklist-card">
        <div class="score-section-title" style="margin-top:0; color:#34d399;">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
          Recruiter Screening Clearance Checklist
        </div>
        ${data.pass_checklist.map(item => `
          <div class="pass-checklist-item">
            <span class="checklist-check-icon">✓</span>
            <span>${escapeHtml(item)}</span>
          </div>
        `).join("")}
      </div>
    `;
  }

  // 6. Matched & Missing Keyword Badges
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

  // 7. Section Notes & Formatting Feedback
  if (data.section_notes && data.section_notes.length) {
    html += `
      <div class="score-section-title" style="margin-top: 16px;">
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

  scoreDetails.innerHTML = html;

  // Bind 1-click copy buttons for recommended STAR bullets
  scoreDetails.querySelectorAll(".btn-copy-bullet").forEach(btn => {
    btn.addEventListener("click", async () => {
      const text = btn.dataset.bullet || "";
      if (!text) return;
      try {
        await navigator.clipboard.writeText(`• ${text}`);
        btn.classList.add("copied");
        btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg> <span>Copied!</span>`;
        showToast("STAR bullet point copied to clipboard!", "success");
        setTimeout(() => {
          btn.classList.remove("copied");
          btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg> <span>Copy Bullet</span>`;
        }, 2200);
      } catch {
        showToast("Press Ctrl+C to copy bullet.", "info");
      }
    });
  });

  scoreCard.scrollIntoView({ behavior: "smooth", block: "start" });
}

// 9. Job Search & Application Tracking
const searchBtn = document.getElementById("searchBtn");
const jobsCard = document.getElementById("jobsCard");
const toApplyList = document.getElementById("toApplyList");
const appliedList = document.getElementById("appliedList");
// Position Type & Experience Level Filter State (RoboApply Mode)
let selectedPositionType = "all";
let selectedExperience = "any";

const internFilterNotice = document.getElementById("internFilterNotice");
const positionPills = document.querySelectorAll("#positionTypeGroup .selector-pill");
const experiencePills = document.querySelectorAll("#experienceLevelGroup .selector-pill");

positionPills.forEach(pill => {
  pill.addEventListener("click", () => {
    positionPills.forEach(p => p.classList.remove("active"));
    pill.classList.add("active");
    selectedPositionType = pill.dataset.type;

    if (selectedPositionType === "internship") {
      if (internFilterNotice) internFilterNotice.hidden = false;
      // Auto-sync experience level to student/intern (0 yrs)
      experiencePills.forEach(p => {
        p.classList.toggle("active", p.dataset.exp === "intern");
      });
      selectedExperience = "intern";
      showToast("Position set to: 🎓 Internship (showing only internships)", "info");
    } else {
      if (internFilterNotice) internFilterNotice.hidden = true;
      if (selectedExperience === "intern") {
        experiencePills.forEach(p => {
          p.classList.toggle("active", p.dataset.exp === "any");
        });
        selectedExperience = "any";
      }
    }
  });
});

experiencePills.forEach(pill => {
  pill.addEventListener("click", () => {
    experiencePills.forEach(p => p.classList.remove("active"));
    pill.classList.add("active");
    selectedExperience = pill.dataset.exp;

    if (selectedExperience === "intern") {
      // Auto-sync position type to internship
      positionPills.forEach(p => {
        p.classList.toggle("active", p.dataset.type === "internship");
      });
      selectedPositionType = "internship";
      if (internFilterNotice) internFilterNotice.hidden = false;
      showToast("Experience set to: Student / 0 yrs (showing only internships)", "info");
    } else {
      if (selectedPositionType === "internship") {
        positionPills.forEach(p => {
          p.classList.toggle("active", p.dataset.type === "all");
        });
        selectedPositionType = "all";
        if (internFilterNotice) internFilterNotice.hidden = true;
      }
    }
  });
});

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
      formData.append("experience", selectedExperience);
      formData.append("job_type", selectedPositionType);
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
      renderJobs(data, false, true);
      const totalCount = (data.to_apply_count || 0) + (data.applied_count || 0);
      const filterLabel = selectedPositionType === "internship" ? "internship" : "job";
      showToast(`Found ${totalCount} matching ${filterLabel} opportunities!`, "success");
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      setBtnLoading(searchBtn, false, originalSearchBtnHtml);
    }
  });
}

let currentJobsData = null;

function jobCardHtml(job, isApplied) {
  const verdictMap = {
    likely_legit: { label: "Likely Legit", class: "badge-likely_legit" },
    verify: { label: "Verify Company", class: "badge-verify" },
    high_risk: { label: "High Risk Warning", class: "badge-high_risk" },
  };
  const verdictInfo = verdictMap[job.legitimacy_verdict] || { label: job.legitimacy_verdict, class: "badge-verify" };
  const isOfficial = !!job.is_official_career;

  return `
    <div class="job-item ${isApplied ? "is-applied" : ""} ${isOfficial ? "is-official-career" : ""}" data-job-id="${escapeHtml(job.job_id)}">
      <div class="job-top-bar">
        <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
          ${isOfficial ? `<span class="badge badge-official">🏢 Official Company Career Site</span>` : `<span class="badge ${verdictInfo.class}">● ${verdictInfo.label}</span>`}
          ${job.position_type ? `<span class="badge ${job.position_type === "Internship" ? "badge-likely_legit" : "badge-optional"}">${job.position_type === "Internship" ? "🎓 Internship" : "💼 " + escapeHtml(job.position_type)}</span>` : ""}
          ${job.experience_level && job.experience_level !== "Any Experience" ? `<span class="badge badge-optional">⭐ ${escapeHtml(job.experience_level)}</span>` : ""}
        </div>
        <span class="badge-optional">${escapeHtml(job.source)}</span>
      </div>

      <h3>${escapeHtml(job.title)}</h3>
      <div class="job-meta">
        <strong>${escapeHtml(job.company)}</strong>
        ${isOfficial ? `<span class="verified-icon" title="Verified Employer Direct Portal">✓</span>` : ""}
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
        <a class="apply-link" href="${escapeHtml(job.apply_url)}" target="_blank" rel="noopener noreferrer" style="${isOfficial ? 'color: #c084fc; font-weight: 800;' : ''}">
          <span>${isOfficial ? 'Apply on Official Portal' : 'Open / Apply Direct'}</span>
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
        <summary>Why this verdict? Details & verification</summary>
        <ul class="note-list">
          ${(job.legitimacy_reasons || []).map(r => `<li>${escapeHtml(r)}</li>`).join("")}
        </ul>
      </details>
    </div>
  `;
}

function renderJobs(data, filterOnlyOfficial = false, shouldScroll = false) {
  if (!jobsCard) return;
  jobsCard.hidden = false;
  currentJobsData = data;

  const toApplyListItems = data.to_apply || [];
  const appliedListItems = data.applied || [];

  const displayToApply = filterOnlyOfficial ? toApplyListItems.filter(j => j.is_official_career) : toApplyListItems;
  const displayApplied = filterOnlyOfficial ? appliedListItems.filter(j => j.is_official_career) : appliedListItems;

  const totalOfficial = toApplyListItems.filter(j => j.is_official_career).length + appliedListItems.filter(j => j.is_official_career).length;
  const officialCountEl = document.getElementById("officialCount");
  if (officialCountEl) officialCountEl.textContent = totalOfficial;

  const toApplyNum = toApplyListItems.length;
  const appliedNum = appliedListItems.length;

  if (toApplyCount) toApplyCount.textContent = toApplyNum;
  if (appliedCount) appliedCount.textContent = appliedNum;
  if (toApplyBadge) toApplyBadge.textContent = displayToApply.length;
  if (appliedBadge) appliedBadge.textContent = displayApplied.length;

  if (toApplyList) {
    toApplyList.innerHTML = displayToApply.length
      ? displayToApply.map(j => jobCardHtml(j, false)).join("")
      : `<div class="empty-col-note">${filterOnlyOfficial ? 'No official portals in this column.' : 'No opportunities in this column.'}</div>`;
  }

  if (appliedList) {
    appliedList.innerHTML = displayApplied.length
      ? displayApplied.map(j => jobCardHtml(j, true)).join("")
      : `<div class="empty-col-note">No jobs marked as applied yet.</div>`;
  }

  if (shouldScroll) {
    jobsCard.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

// 10. Segmented View Switcher Tabs (Mobile / Filter Tabs)
const viewAllTab = document.getElementById("viewAllTab");
const viewOfficialTab = document.getElementById("viewOfficialTab");
const viewToApplyTab = document.getElementById("viewToApplyTab");
const viewAppliedTab = document.getElementById("viewAppliedTab");
const colToApply = document.getElementById("colToApply");
const colApplied = document.getElementById("colApplied");

function setJobTab(activeTab, showToApply, showApplied, onlyOfficial = false) {
  [viewAllTab, viewOfficialTab, viewToApplyTab, viewAppliedTab].forEach(t => t && t.classList.remove("active"));
  if (activeTab) activeTab.classList.add("active");
  if (colToApply) colToApply.style.display = showToApply ? "block" : "none";
  if (colApplied) colApplied.style.display = showApplied ? "block" : "none";

  if (currentJobsData) {
    renderJobs(currentJobsData, onlyOfficial, false);
  }
}

if (viewAllTab) viewAllTab.addEventListener("click", () => setJobTab(viewAllTab, true, true, false));
if (viewOfficialTab) viewOfficialTab.addEventListener("click", () => setJobTab(viewOfficialTab, true, true, true));
if (viewToApplyTab) viewToApplyTab.addEventListener("click", () => setJobTab(viewToApplyTab, true, false, false));
if (viewAppliedTab) viewAppliedTab.addEventListener("click", () => setJobTab(viewAppliedTab, false, true, false));

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
