/**
 * Smart Study Generator — Frontend Script
 * Communicates with Flask backend only. API key is NEVER present here.
 * Uses a relative path so it works whether opened via Flask (port 5000)
 * or any other local server — no hard-coded host needed.
 */

const API_BASE = "/api";

// ─── State ────────────────────────────────────────────────────────
let sessionId = localStorage.getItem("ssg_session_id") || null;
let pendingFiles = [];   // FileList staging area before upload

// ─── DOM Refs ─────────────────────────────────────────────────────
const chatMessages   = document.getElementById("chat-messages");
const chatInput      = document.getElementById("chat-input");
const sendBtn        = document.getElementById("send-btn");
const charCount      = document.getElementById("char-count");
const statusDot      = document.getElementById("status-dot");
const statusLabel    = document.getElementById("status-label");
const alertBanner    = document.getElementById("alert-banner");
const profileForm    = document.getElementById("profile-form");
const profileStatus  = document.getElementById("profile-status");
const dropZone       = document.getElementById("drop-zone");
const fileInput      = document.getElementById("file-input");
const fileList       = document.getElementById("file-list");
const uploadBtn      = document.getElementById("upload-btn");
const uploadStatus   = document.getElementById("upload-status");
const scoreForm      = document.getElementById("score-form");
const scoreStatus    = document.getElementById("score-status");
const refreshDash    = document.getElementById("refresh-dashboard");
const clearSession   = document.getElementById("clear-session-btn");

// ─── Init ──────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  checkHealth();
  setInterval(checkHealth, 30_000);
  if (sessionId) refreshDashboard();
  setupTabs();
  setupChat();
  setupProfile();
  setupUpload();
  setupQuickActions();
  setupScoreForm();
  refreshDash.addEventListener("click", refreshDashboard);
  clearSession.addEventListener("click", clearCurrentSession);
});

// ─── Health Check ─────────────────────────────────────────────────
async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    const data = await res.json();
    if (data.status === "ok") {
      statusDot.className = "status-dot online";
      if (data.groq_configured) {
        statusLabel.textContent = "Online";
        statusDot.title = "Backend online · Groq configured";
      } else {
        statusLabel.textContent = "No API Key";
        statusDot.className = "status-dot offline";
        statusDot.title = "Backend online but GROQ_API_KEY not set";
        showAlert("⚠️ GROQ_API_KEY is not configured. Edit your .env file and restart the server.");
      }
    } else {
      statusDot.className = "status-dot offline";
      statusLabel.textContent = "Error";
    }
  } catch {
    statusDot.className = "status-dot offline";
    statusLabel.textContent = "Offline";
    statusDot.title = "Backend not reachable";
    showAlert("⚠️ Cannot reach the backend. Make sure run_smart_study.bat is running.");
  }
}

// ─── Tabs ──────────────────────────────────────────────────────────
function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => { p.classList.remove("active"); p.classList.add("hidden"); });
      btn.classList.add("active");
      const panel = document.getElementById("tab-" + btn.dataset.tab);
      panel.classList.add("active");
      panel.classList.remove("hidden");
      if (btn.dataset.tab === "dashboard") refreshDashboard();
      if (btn.dataset.tab === "quiz-tracker") renderScoreHistory();
    });
  });
}

// ─── Profile ──────────────────────────────────────────────────────
function setupProfile() {
  profileForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const profile = {
      name:               document.getElementById("p-name").value.trim(),
      course:             document.getElementById("p-course").value.trim(),
      subjects:           document.getElementById("p-subjects").value.trim(),
      learning_preference:document.getElementById("p-pref").value,
      study_hours_per_day:parseFloat(document.getElementById("p-hours").value) || "",
      exam_date:          document.getElementById("p-exam-date").value,
      syllabus:           document.getElementById("p-syllabus").value.trim(),
      weak_areas:         document.getElementById("p-weak").value.trim(),
    };
    try {
      const res = await fetch(`${API_BASE}/profile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, profile }),
      });
      const data = await res.json();
      if (data.session_id) {
        sessionId = data.session_id;
        localStorage.setItem("ssg_session_id", sessionId);
      }
      setStatus(profileStatus, "✅ Profile saved!", "ok");
      addMessage("assistant",
        `👋 Hi **${profile.name || "there"}**! Your profile has been saved. ` +
        `I'm ready to help you study${profile.subjects ? " **" + profile.subjects + "**" : ""}. ` +
        `What would you like to work on?`
      );
    } catch (err) {
      setStatus(profileStatus, "❌ Failed to save profile. Is the backend running?", "err");
    }
  });
}

// ─── File Upload ──────────────────────────────────────────────────
function setupUpload() {
  dropZone.addEventListener("click", () => fileInput.click());
  dropZone.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("dragover"); });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
  dropZone.addEventListener("drop", e => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    addPendingFiles(e.dataTransfer.files);
  });
  fileInput.addEventListener("change", () => addPendingFiles(fileInput.files));

  uploadBtn.addEventListener("click", uploadFiles);
}

function addPendingFiles(files) {
  Array.from(files).forEach(f => {
    if (!pendingFiles.find(p => p.name === f.name && p.size === f.size)) {
      pendingFiles.push(f);
    }
  });
  renderFileList();
  uploadBtn.disabled = pendingFiles.length === 0;
}

function renderFileList() {
  fileList.innerHTML = "";
  pendingFiles.forEach((f, i) => {
    const item = document.createElement("div");
    item.className = "file-item";
    item.innerHTML = `
      <span class="file-name" title="${esc(f.name)}">${esc(f.name)}</span>
      <span class="file-size">${formatBytes(f.size)}</span>
      <button class="file-remove" data-index="${i}" title="Remove">✕</button>`;
    fileList.appendChild(item);
  });
  fileList.querySelectorAll(".file-remove").forEach(btn => {
    btn.addEventListener("click", () => {
      pendingFiles.splice(parseInt(btn.dataset.index), 1);
      renderFileList();
      uploadBtn.disabled = pendingFiles.length === 0;
    });
  });
}

async function uploadFiles() {
  if (!pendingFiles.length) return;
  uploadBtn.disabled = true;
  setStatus(uploadStatus, "⏳ Uploading…", "");

  const form = new FormData();
  if (sessionId) form.append("session_id", sessionId);
  pendingFiles.forEach(f => form.append("files", f));

  try {
    const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: form });
    const data = await res.json();
    if (data.session_id) {
      sessionId = data.session_id;
      localStorage.setItem("ssg_session_id", sessionId);
    }
    const ok = data.uploaded.filter(u => u.status === "processed");
    const bad = data.uploaded.filter(u => u.status !== "processed");
    let msg = `📂 Uploaded **${ok.length}** file(s) successfully.`;
    if (bad.length) msg += ` ⚠️ ${bad.length} rejected: ${bad.map(b => b.reason).join("; ")}`;
    setStatus(uploadStatus, ok.length > 0 ? "✅ " + ok.length + " file(s) ready" : "⚠️ No files processed", ok.length > 0 ? "ok" : "err");
    addMessage("assistant", msg + `\n\nI now have **${data.total_docs}** document(s) in context. Ask me to summarise, create flashcards, or anything else!`);
    pendingFiles = [];
    renderFileList();
  } catch (err) {
    setStatus(uploadStatus, "❌ Upload failed. Check backend.", "err");
    uploadBtn.disabled = false;
  }
}

// ─── Chat ──────────────────────────────────────────────────────────
function setupChat() {
  chatInput.addEventListener("input", () => {
    charCount.textContent = `${chatInput.value.length} / 5000`;
    sendBtn.disabled = chatInput.value.trim().length === 0;
  });

  chatInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });

  sendBtn.addEventListener("click", () => sendMessage());
  sendBtn.disabled = true;
}

async function sendMessage(actionOverride = null) {
  const query = chatInput.value.trim();
  if (!query && !actionOverride) return;

  const displayQuery = query || `[Action: ${actionOverride}]`;
  addMessage("user", displayQuery);
  chatInput.value = "";
  charCount.textContent = "0 / 5000";
  sendBtn.disabled = true;

  const typingId = showTyping();

  try {
    const res = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        query: query || `Please ${actionOverride?.replace(/_/g, " ")} for my uploaded material.`,
        action: actionOverride || null,
      }),
    });

    removeTyping(typingId);

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const msg = err.error || "Something went wrong. Please try again.";
      // Rate-limit: show as a plain warning, not a scary error
      if (res.status === 429) {
        addMessage("assistant", `⏳ **Rate limit reached** — ${msg}`);
      } else {
        addMessage("assistant", `❌ **Error**: ${msg}`);
      }
      return;
    }

    const data = await res.json();
    if (data.session_id) {
      sessionId = data.session_id;
      localStorage.setItem("ssg_session_id", sessionId);
    }

    // Show focus alerts for weak areas
    if (data.response && data.response.includes("Focus Alert")) {
      const alerts = data.response.match(/⚠️ Focus Alert[:\s]+([^\n]+)/g);
      if (alerts) showAlert(alerts.join(" · "));
    }

    addMessage("assistant", data.response, data.intent, data.docs_in_context);

  } catch (err) {
    removeTyping(typingId);
    addMessage("assistant", "❌ **Network error**: Cannot reach the backend. Make sure the server is running on port 5000.");
  }
}

// ─── Quick Actions ─────────────────────────────────────────────────
function setupQuickActions() {
  document.querySelectorAll(".btn-action").forEach(btn => {
    btn.addEventListener("click", () => {
      // Switch to chat tab first
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => { p.classList.remove("active"); p.classList.add("hidden"); });
      document.querySelector('[data-tab="chat"]').classList.add("active");
      document.getElementById("tab-chat").classList.add("active");
      document.getElementById("tab-chat").classList.remove("hidden");
      sendMessage(btn.dataset.action);
    });
  });
}

// ─── Dashboard ─────────────────────────────────────────────────────
async function refreshDashboard() {
  if (!sessionId) return;
  try {
    const res = await fetch(`${API_BASE}/progress?session_id=${encodeURIComponent(sessionId)}`);
    const data = await res.json();

    document.getElementById("stat-queries").textContent = data.total_queries ?? 0;
    document.getElementById("stat-docs").textContent    = data.docs_uploaded ?? 0;
    // Avg score: show numeric value or "N/A" placeholder
    const avgEl = document.getElementById("stat-avg-score");
    if (data.average_score != null) {
      avgEl.textContent = data.average_score + "%";
    } else {
      avgEl.innerHTML = '<span class="no-data">N/A</span>';
    }
    document.getElementById("stat-topics").textContent  = (data.topics_studied || []).length;

    // Topics
    const topicsList = document.getElementById("topics-list");
    if (data.topics_studied?.length) {
      topicsList.innerHTML = data.topics_studied.map(t => `<span class="tag">${esc(t)}</span>`).join("");
    } else {
      topicsList.innerHTML = "<em>None yet — start studying!</em>";
    }

    // Weak areas
    const weakList = document.getElementById("weak-list");
    if (data.weak_areas?.length) {
      weakList.innerHTML = data.weak_areas.map(w => `<span class="tag">⚠️ ${esc(w)}</span>`).join("");
      showAlert("⚠️ Focus needed on: " + data.weak_areas.join(", "));
    } else {
      weakList.innerHTML = "<em>No weak areas identified yet.</em>";
    }

    // Score chart
    renderScoreChart(data.quiz_scores || []);

  } catch (err) {
    console.warn("Dashboard refresh failed", err);
  }
}

function renderScoreChart(scores) {
  const container = document.getElementById("score-chart");
  if (!scores.length) {
    container.innerHTML = '<p class="muted">No quiz scores yet. Take a practice quiz to see your progress!</p>';
    return;
  }
  const recent = scores.slice(-10).reverse();
  container.innerHTML = recent.map(s => {
    const pct = s.percentage;
    const color = pct >= 80 ? "#16a34a" : pct >= 60 ? "#d97706" : "#dc2626";
    return `
      <div class="score-bar-row">
        <span class="score-bar-label" title="${esc(s.topic)}">${esc(s.topic)}</span>
        <div class="score-bar-track">
          <div class="score-bar-fill" style="width:${pct}%;background:${color}">
            <span class="score-bar-pct">${pct}%</span>
          </div>
        </div>
      </div>`;
  }).join("");
}

// ─── Quiz Score Form ───────────────────────────────────────────────
function setupScoreForm() {
  scoreForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const topic = document.getElementById("score-topic").value.trim();
    const score = parseInt(document.getElementById("score-value").value);
    const total = parseInt(document.getElementById("score-total").value);

    if (!topic || isNaN(score) || isNaN(total) || total <= 0 || score < 0 || score > total) {
      setStatus(scoreStatus, "❌ Please fill in all fields correctly.", "err");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/quiz-score`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, topic, score, total }),
      });
      const data = await res.json();
      if (data.status === "recorded") {
        const pct = Math.round(score / total * 100);
        setStatus(scoreStatus, `✅ Recorded: ${score}/${total} (${pct}%)`, "ok");
        scoreForm.reset();

        // Save to local history
        const history = JSON.parse(localStorage.getItem("ssg_scores") || "[]");
        history.push({ topic, score, total, pct, date: new Date().toLocaleString() });
        localStorage.setItem("ssg_scores", JSON.stringify(history.slice(-50)));
        renderScoreHistory();
        refreshDashboard();
      }
    } catch (err) {
      setStatus(scoreStatus, "❌ Failed to record score.", "err");
    }
  });
}

function renderScoreHistory() {
  const history = JSON.parse(localStorage.getItem("ssg_scores") || "[]").slice().reverse();
  const container = document.getElementById("score-history-list");
  if (!history.length) {
    container.innerHTML = '<p class="muted">No scores recorded yet.</p>';
    return;
  }
  container.innerHTML = history.slice(0, 20).map(s => {
    const cls = s.pct >= 80 ? "score-good" : s.pct >= 60 ? "score-ok" : "score-bad";
    return `
      <div class="score-entry">
        <span class="entry-topic">${esc(s.topic)}</span>
        <span class="entry-score ${cls}">${s.score}/${s.total} (${s.pct}%)</span>
        <span class="entry-date">${esc(s.date || "")}</span>
      </div>`;
  }).join("");
}

// ─── Clear Session ─────────────────────────────────────────────────
async function clearCurrentSession() {
  if (!confirm("Clear your session? This will reset progress, uploaded files, and scores.")) return;
  try {
    await fetch(`${API_BASE}/clear-session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    });
  } catch {}
  localStorage.removeItem("ssg_session_id");
  localStorage.removeItem("ssg_scores");
  sessionId = null;
  pendingFiles = [];
  renderFileList();
  uploadBtn.disabled = true;
  chatMessages.innerHTML = `
    <div class="chat-message assistant-message welcome-msg">
      <div class="msg-avatar">&#127891;</div>
      <div class="msg-body">
        <p><strong>Session cleared!</strong> Fill in your profile and start a new study session.</p>
      </div>
    </div>`;
  refreshDashboard();
  alertBanner.classList.add("hidden");
}

// ─── Message Rendering ─────────────────────────────────────────────
function addMessage(role, text, intent = null, docsInContext = 0) {
  const div = document.createElement("div");
  div.className = `chat-message ${role === "user" ? "user-message" : "assistant-message"}`;

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  avatar.textContent = role === "user" ? "\uD83E\uDDD1" : "\uD83C\uDF93";

  const body = document.createElement("div");
  body.className = "msg-body";

  if (intent && role === "assistant") {
    const badge = document.createElement("div");
    badge.className = "intent-badge";
    badge.textContent = intent.replace(/_/g, " ");
    body.appendChild(badge);
    if (docsInContext > 0) {
      const docNote = document.createElement("div");
      docNote.className = "intent-badge";
      docNote.style.background = "var(--accent-light)";
      docNote.style.color = "var(--accent)";
      docNote.textContent = `${docsInContext} doc(s) in context`;
      body.appendChild(docNote);
    }
  }

  // Render markdown-like formatting
  const content = document.createElement("div");
  content.innerHTML = renderMarkdown(text);
  body.appendChild(content);

  div.appendChild(avatar);
  div.appendChild(body);
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTyping() {
  const id = "typing-" + Date.now();
  const div = document.createElement("div");
  div.id = id;
  div.className = "chat-message assistant-message typing-indicator";
  div.innerHTML = `
    <div class="msg-avatar">🎓</div>
    <div class="msg-body">
      <div class="typing-dots"><span></span><span></span><span></span></div>
    </div>`;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return id;
}

function removeTyping(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

// ─── Markdown Renderer ─────────────────────────────────────────────
function renderMarkdown(text) {
  if (!text) return "";
  let html = esc(text);

  // Code blocks
  html = html.replace(/```[\s\S]*?```/g, m => {
    const code = m.replace(/^```[a-z]*\n?/, "").replace(/```$/, "");
    return `<pre><code>${code}</code></pre>`;
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/__(.+?)__/g, "<strong>$1</strong>");

  // Italic
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  html = html.replace(/_(.+?)_/g, "<em>$1</em>");

  // HR
  html = html.replace(/^---+$/gm, "<hr>");

  // Headers
  html = html.replace(/^#### (.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");

  // Blockquote
  html = html.replace(/^&gt; (.+)$/gm, "<blockquote>$1</blockquote>");

  // Unordered lists
  html = html.replace(/((?:^[\*\-] .+$\n?)+)/gm, match => {
    const items = match.trim().split("\n").map(l => `<li>${l.replace(/^[\*\-] /, "")}</li>`).join("");
    return `<ul>${items}</ul>`;
  });

  // Ordered lists
  html = html.replace(/((?:^\d+\. .+$\n?)+)/gm, match => {
    const items = match.trim().split("\n").map(l => `<li>${l.replace(/^\d+\. /, "")}</li>`).join("");
    return `<ol>${items}</ol>`;
  });

  // Paragraphs (double newline)
  html = html.replace(/\n\n+/g, "</p><p>");
  html = "<p>" + html + "</p>";

  // Single newlines
  html = html.replace(/([^>])\n([^<])/g, "$1<br>$2");

  // Clean up empty paragraphs
  html = html.replace(/<p>\s*<\/p>/g, "");

  return html;
}

// ─── Utilities ─────────────────────────────────────────────────────
function esc(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function setStatus(el, msg, type) {
  el.textContent = msg;
  el.className = "form-status " + type;
  if (type === "ok") setTimeout(() => { if (el.textContent === msg) el.textContent = ""; }, 4000);
}

function showAlert(msg) {
  alertBanner.textContent = msg;
  alertBanner.classList.remove("hidden");
  setTimeout(() => alertBanner.classList.add("hidden"), 10_000);
}
