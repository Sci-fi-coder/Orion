/**
 * ORION RESEARCH TERMINAL // FRONTEND APPLICATION ENGINE
 * Pure JavaScript - No Frameworks - No Dependencies
 * Communicates with ORION FastAPI backend at http://localhost:8000
 */

// Base API Configuration
const API_BASE = "http://localhost:8000";

// Runtime Session State
const sessionState = {
  queriesRun: 0,
  confidenceSum: 0.0,
  currentWorkspaceId: 1,
  isResearching: false,
  statusCheckInterval: null,
  clockInterval: null,
  tickerInterval: null,
};

// DOM Element Registry
const elements = {
  // Navigation & System Status
  systemStatusDot: document.getElementById("systemStatusDot"),
  systemStatusText: document.getElementById("systemStatusText"),
  systemStatusBadge: document.getElementById("systemStatusBadge"),
  navClock: document.getElementById("navClock"),
  newResearchBtn: document.getElementById("newResearchBtn"),

  // Sidebar Elements
  workspaceBadge: document.getElementById("workspaceBadge"),
  activeWsLabel: document.getElementById("activeWsLabel"),
  papersCountLabel: document.getElementById("papersCountLabel"),
  sidebarPapersList: document.getElementById("sidebarPapersList"),
  statQueriesRun: document.getElementById("statQueriesRun"),
  statAvgConfidence: document.getElementById("statAvgConfidence"),

  // Form Controls
  researchForm: document.getElementById("researchForm"),
  topicInput: document.getElementById("topicInput"),
  workspaceIdInput: document.getElementById("workspaceIdInput"),
  devilAdvocateToggle: document.getElementById("devilAdvocateToggle"),
  daToggleLabel: document.getElementById("daToggleLabel"),
  runResearchBtn: document.getElementById("runResearchBtn"),

  // Error & Loading States
  terminalErrorBox: document.getElementById("terminalErrorBox"),
  errorMessageText: document.getElementById("errorMessageText"),
  errorCloseBtn: document.getElementById("errorCloseBtn"),
  loadingStateContainer: document.getElementById("loadingStateContainer"),
  loadingStatusText: document.getElementById("loadingStatusText"),

  // Welcome Screen & Query Chips
  welcomeScreen: document.getElementById("welcomeScreen"),
  queryChips: document.querySelectorAll(".query-chip"),

  // Results Panel Elements
  resultsPanel: document.getElementById("resultsPanel"),
  resultTopicText: document.getElementById("resultTopicText"),
  resultChunksPill: document.getElementById("resultChunksPill"),
  resultWebPill: document.getElementById("resultWebPill"),
  resultReplansPill: document.getElementById("resultReplansPill"),

  // Confidence Meter
  confidenceValueText: document.getElementById("confidenceValueText"),
  confidenceTierBadge: document.getElementById("confidenceTierBadge"),
  confidenceBarFill: document.getElementById("confidenceBarFill"),

  // Stance & Evidence Pills
  pillSupports: document.getElementById("pillSupports"),
  pillContradicts: document.getElementById("pillContradicts"),
  pillNeutral: document.getElementById("pillNeutral"),
  pillExperimental: document.getElementById("pillExperimental"),
  pillTheoretical: document.getElementById("pillTheoretical"),
  pillSurvey: document.getElementById("pillSurvey"),
  pillAssertion: document.getElementById("pillAssertion"),

  // Dossier Answer Content
  answerContentBody: document.getElementById("answerContentBody"),

  // Devil's Advocate Section
  devilAdvocateCard: document.getElementById("devilAdvocateCard"),
  daToggleBtn: document.getElementById("daToggleBtn"),
  daBody: document.getElementById("daBody"),
  daContentText: document.getElementById("daContentText"),
  daStatusBadge: document.getElementById("daStatusBadge"),
  daCaret: document.getElementById("daCaret"),

  // Reasoning Pipeline
  toggleReasoningBtn: document.getElementById("toggleReasoningBtn"),
  reasoningToggleIcon: document.getElementById("reasoningToggleIcon"),
  reasoningToggleText: document.getElementById("reasoningToggleText"),
  reasoningBody: document.getElementById("reasoningBody"),
  nodeCoordSummary: document.getElementById("nodeCoordSummary"),
  nodeResearchSummary: document.getElementById("nodeResearchSummary"),
  nodeSynthSummary: document.getElementById("nodeSynthSummary"),
  nodeCriticSummary: document.getElementById("nodeCriticSummary"),
  rawLogList: document.getElementById("rawLogList"),

  // Retrieved Citations Card
  retrievedPapersCard: document.getElementById("retrievedPapersCard"),
  retrievedPapersCount: document.getElementById("retrievedPapersCount"),
  retrievedPapersList: document.getElementById("retrievedPapersList"),
};

// ==========================================================================
// 1. SYSTEM INITIALIZATION & TELEMETRY CLOCK
// ==========================================================================

document.addEventListener("DOMContentLoaded", () => {
  initClock();
  bindEventListeners();
  checkHealth();
  loadWorkspaceData(sessionState.currentWorkspaceId);

  // Periodic health check every 15 seconds
  sessionState.statusCheckInterval = setInterval(checkHealth, 15000);
});

/**
 * Updates terminal HUD clock in ISO/UTC format
 */
function initClock() {
  const update = () => {
    const now = new Date();
    const utcStr = now.toTimeString().split(" ")[0] + " UTC";
    if (elements.navClock) {
      elements.navClock.textContent = utcStr;
    }
  };
  update();
  sessionState.clockInterval = setInterval(update, 1000);
}

/**
 * Check backend health status (GET /health)
 */
async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (res.ok) {
      const data = await res.json();
      setSystemStatus(true, `SYS: ONLINE [${data.status.toUpperCase()}]`);
    } else {
      setSystemStatus(false, `SYS: HTTP ${res.status}`);
    }
  } catch (err) {
    setSystemStatus(false, "SYS: OFFLINE (PORT 8000)");
  }
}

/**
 * Update UI status dot and text
 */
function setSystemStatus(isOnline, label) {
  if (isOnline) {
    elements.systemStatusDot.classList.remove("offline");
    elements.systemStatusDot.classList.add("blinking");
    elements.systemStatusText.textContent = label || "SYS: ONLINE";
    elements.systemStatusBadge.title = "Backend is responding properly";
  } else {
    elements.systemStatusDot.classList.remove("blinking");
    elements.systemStatusDot.classList.add("offline");
    elements.systemStatusText.textContent = label || "SYS: OFFLINE";
    elements.systemStatusBadge.title = "Failed to connect to http://localhost:8000";
  }
}

// ==========================================================================
// 2. EVENT BINDINGS
// ==========================================================================

function bindEventListeners() {
  // Form submission
  elements.researchForm.addEventListener("submit", (e) => {
    e.preventDefault();
    runResearch();
  });

  // Enter key in topic textarea triggers runResearch (Shift+Enter for newline)
  elements.topicInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      runResearch();
    }
  });

  // Devil's Advocate switch change
  elements.devilAdvocateToggle.addEventListener("change", (e) => {
    elements.daToggleLabel.textContent = e.target.checked ? "ON" : "OFF";
  });

  // Workspace ID change
  elements.workspaceIdInput.addEventListener("change", (e) => {
    const val = parseInt(e.target.value, 10);
    if (!isNaN(val) && val > 0) {
      sessionState.currentWorkspaceId = val;
      elements.workspaceBadge.textContent = `ID: ${val}`;
      elements.activeWsLabel.textContent = `Workspace #${val}`;
      loadWorkspaceData(val);
    }
  });

  // New Research Button
  elements.newResearchBtn.addEventListener("click", () => {
    resetToWelcome();
    elements.topicInput.value = "";
    elements.topicInput.focus();
  });

  // Suggested prompt chips
  elements.queryChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const query = chip.getAttribute("data-query");
      if (query) {
        elements.topicInput.value = query;
        elements.topicInput.focus();
      }
    });
  });

  // Error box dismiss button
  elements.errorCloseBtn.addEventListener("click", hideError);

  // Devil's Advocate accordion toggle
  elements.daToggleBtn.addEventListener("click", toggleDevilsAdvocateSection);

  // Reasoning log toggle
  elements.toggleReasoningBtn.addEventListener("click", toggleReasoningLog);
}

// ==========================================================================
// 3. WORKSPACE DATA LOADING (GET /workspace/{id}/papers & metrics)
// ==========================================================================

async function loadWorkspaceData(workspaceId) {
  try {
    // 1. Fetch papers
    const papersRes = await fetch(`${API_BASE}/workspace/${workspaceId}/papers`);
    if (papersRes.ok) {
      const data = await papersRes.json();
      renderSidebarPapers(data.papers || []);
    } else {
      elements.papersCountLabel.textContent = "Papers: unavailable";
    }

    // 2. Fetch metrics
    const metricsRes = await fetch(`${API_BASE}/workspace/${workspaceId}/metrics`);
    if (metricsRes.ok) {
      const metrics = await metricsRes.json();
      if (metrics.total_queries !== undefined) {
        // Sync with session if higher
        sessionState.queriesRun = Math.max(sessionState.queriesRun, metrics.total_queries);
        elements.statQueriesRun.textContent = sessionState.queriesRun;
      }
      if (metrics.avg_confidence !== undefined) {
        elements.statAvgConfidence.textContent = Number(metrics.avg_confidence).toFixed(2);
      }
    }
  } catch (err) {
    console.warn("[ORION] Workspace query failed:", err.message);
  }
}

function renderSidebarPapers(papers) {
  elements.sidebarPapersList.innerHTML = "";
  elements.papersCountLabel.textContent = `Papers ingested: ${papers.length}`;

  if (!papers || papers.length === 0) {
    elements.sidebarPapersList.innerHTML = `<div class="empty-list-note">No papers in workspace #${sessionState.currentWorkspaceId}</div>`;
    return;
  }

  papers.slice(0, 10).forEach((p) => {
    const item = document.createElement("div");
    item.className = "sidebar-paper-item";
    const title = p.title || p.arxiv_id || "Untitled Paper";
    item.title = `${title} (${p.arxiv_id || "ID"})`;
    item.textContent = `• ${title}`;
    item.addEventListener("click", () => {
      elements.topicInput.value = `Analysis of findings in: ${title}`;
      elements.topicInput.focus();
    });
    elements.sidebarPapersList.appendChild(item);
  });
}

// ==========================================================================
// 4. RUN RESEARCH WORKFLOW (POST /research)
// ==========================================================================

async function runResearch() {
  if (sessionState.isResearching) return;

  const topic = elements.topicInput.value.trim();
  if (!topic) {
    showError("Please enter a research topic or hypothesis before executing.");
    elements.topicInput.focus();
    return;
  }

  const workspaceId = parseInt(elements.workspaceIdInput.value, 10) || 1;
  const devilAdvocate = elements.devilAdvocateToggle.checked;

  hideError();
  startLoading();

  const payload = {
    topic: topic,
    workspace_id: workspaceId,
    devil_advocate: devilAdvocate,
  };

  try {
    const response = await fetch(`${API_BASE}/research`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      let detailMsg = `HTTP Error ${response.status}: ${response.statusText}`;
      try {
        const errorData = await response.json();
        if (errorData.detail) {
          detailMsg = typeof errorData.detail === "string" 
            ? errorData.detail 
            : JSON.stringify(errorData.detail);
        }
      } catch (e) {
        // Fallback to response text
      }
      throw new Error(detailMsg);
    }

    const data = await response.json();
    stopLoading();
    renderResults(topic, data);
    updateSessionTelemetry(data.confidence || 0.0);
    loadWorkspaceData(workspaceId);
  } catch (err) {
    stopLoading();
    showError(`Execution failure: ${err.message}`);
    console.error("[ORION Research Error]", err);
  }
}

// ==========================================================================
// 5. LOADING SPINNER & STATUS TICKER
// ==========================================================================

function startLoading() {
  sessionState.isResearching = true;
  elements.runResearchBtn.disabled = true;
  elements.runResearchBtn.innerHTML = `<span class="btn-text">[PROCESSING...]</span>`;

  elements.welcomeScreen.classList.add("hidden");
  elements.resultsPanel.classList.add("hidden");
  elements.loadingStateContainer.classList.remove("hidden");

  // Multi-Agent Status Stage Ticker (simulates multi-stage execution progress)
  const tickerSteps = [
    "COORDINATOR AGENT DECOMPOSING TOPIC...",
    "COORDINATOR GENERATING SEARCH STRATEGY...",
    "RESEARCHER QUERYING ARXIV & VECTOR DATABASE...",
    "RETRIEVING & RANKING HYBRID CONTEXT CHUNKS...",
    "SYNTHESIZER EVALUATING STANCE & EVIDENCE QUALITY...",
    "DEVIL'S ADVOCATE FORMULATING ADVERSARIAL CRITIQUE...",
    "CRITIC AGENT VERIFYING CITATIONS & COHERENCE...",
    "FINALIZING RESEARCH INTELLIGENCE DOSSIER...",
  ];

  let stepIdx = 0;
  elements.loadingStatusText.textContent = tickerSteps[0];

  clearInterval(sessionState.tickerInterval);
  sessionState.tickerInterval = setInterval(() => {
    stepIdx = (stepIdx + 1) % tickerSteps.length;
    elements.loadingStatusText.textContent = tickerSteps[stepIdx];
  }, 4800);
}

function stopLoading() {
  sessionState.isResearching = false;
  clearInterval(sessionState.tickerInterval);
  elements.runResearchBtn.disabled = false;
  elements.runResearchBtn.innerHTML = `<span class="btn-text">[⚡ RUN RESEARCH]</span>`;
  elements.loadingStateContainer.classList.add("hidden");
}

// ==========================================================================
// 6. RENDER RESULTS PANEL
// ==========================================================================

function renderResults(topic, data) {
  // Show results panel with bottom slide animation
  elements.resultsPanel.classList.remove("hidden");
  elements.welcomeScreen.classList.add("hidden");

  // Re-trigger slide animation
  elements.resultsPanel.style.animation = "none";
  // Trigger reflow
  void elements.resultsPanel.offsetWidth;
  elements.resultsPanel.style.animation = "slideInUp 0.35s cubic-bezier(0.16, 1, 0.3, 1) forwards";

  // Topic & Quick Metrics
  elements.resultTopicText.textContent = topic;
  elements.resultChunksPill.textContent = `CHUNKS: ${data.chunks_used || 0}`;
  elements.resultWebPill.textContent = `WEB SOURCES: ${data.web_sources_used || 0}`;
  elements.resultReplansPill.textContent = `REPLANS: ${data.replan_count || 0}`;

  // 1. Confidence Meter Rendering
  renderConfidenceMeter(data.confidence || 0.0);

  // 2. Stance Distribution Rendering
  renderStanceSummary(data.stance_summary || {});

  // 3. Evidence Grades Rendering
  renderEvidenceGrades(data.evidence_grades || {});

  // 4. Dossier Answer Text with Citations & Markdown
  renderAnswer(data.answer || "No synthesis output returned.");

  // 5. Devil's Advocate Section (Collapsed by default)
  renderDevilsAdvocate(data.devil_advocate);

  // 6. Reasoning Pipeline & Timeline (4 steps)
  renderReasoningTimeline(data.reasoning_log || [], data);

  // 7. Retrieved Papers List
  renderRetrievedPapers(data.papers || []);
}

/**
 * Requirement 3: Confidence bar fills proportionally with color:
 * < 0.4: red, 0.4-0.7: amber, > 0.7: green
 */
function renderConfidenceMeter(rawConf) {
  const conf = Math.max(0.0, Math.min(1.0, Number(rawConf) || 0.0));
  const pct = Math.round(conf * 100);

  elements.confidenceValueText.textContent = `${conf.toFixed(2)} (${pct}%)`;

  // Reset classes
  elements.confidenceBarFill.classList.remove("conf-low", "conf-mid", "conf-high");
  elements.confidenceValueText.classList.remove("conf-low", "conf-mid", "conf-high");
  elements.confidenceTierBadge.classList.remove("conf-low", "conf-mid", "conf-high");

  let tierName = "ROBUST";
  let tierClass = "conf-high";

  if (conf < 0.4) {
    tierName = "LOW CONFIDENCE";
    tierClass = "conf-low";
  } else if (conf <= 0.7) {
    tierName = "MODERATE CONFIDENCE";
    tierClass = "conf-mid";
  } else {
    tierName = "HIGH CONFIDENCE";
    tierClass = "conf-high";
  }

  elements.confidenceBarFill.classList.add(tierClass);
  elements.confidenceValueText.classList.add(tierClass);
  elements.confidenceTierBadge.classList.add(tierClass);
  elements.confidenceTierBadge.textContent = tierName;

  // Animate width
  elements.confidenceBarFill.style.width = "0%";
  setTimeout(() => {
    elements.confidenceBarFill.style.width = `${pct}%`;
  }, 50);
}

/**
 * Requirement 4: Stance pills colored:
 * SUPPORTS: green, CONTRADICTS: red, NEUTRAL: gray
 */
function renderStanceSummary(stanceSummary) {
  const supports = stanceSummary.SUPPORTS || 0;
  const contradicts = stanceSummary.CONTRADICTS || 0;
  const neutral = stanceSummary.NEUTRAL || 0;

  elements.pillSupports.textContent = `SUPPORTS: ${supports}`;
  elements.pillContradicts.textContent = `CONTRADICTS: ${contradicts}`;
  elements.pillNeutral.textContent = `NEUTRAL: ${neutral}`;
}

/**
 * Requirement 5: Evidence pills colored:
 * EXPERIMENTAL: blue, THEORETICAL: purple, SURVEY: teal, ASSERTION: amber
 */
function renderEvidenceGrades(grades) {
  const exp = grades.EXPERIMENTAL || 0;
  const theo = grades.THEORETICAL || 0;
  const survey = grades.SURVEY || 0;
  const assertion = grades.ASSERTION || 0;

  elements.pillExperimental.textContent = `EXPERIMENTAL: ${exp}`;
  elements.pillTheoretical.textContent = `THEORETICAL: ${theo}`;
  elements.pillSurvey.textContent = `SURVEY: ${survey}`;
  elements.pillAssertion.textContent = `ASSERTION: ${assertion}`;
}

/**
 * Formats terminal research dossier with citation badges and formatting
 */
function renderAnswer(rawText) {
  elements.answerContentBody.innerHTML = "";

  if (!rawText) {
    elements.answerContentBody.innerHTML = `<p class="answer-paragraph">No response text provided.</p>`;
    return;
  }

  // Parse lines into paragraphs, bullets, code blocks
  const lines = rawText.split("\n");
  let inCodeBlock = false;
  let codeBuffer = [];

  lines.forEach((line) => {
    const trimmed = line.trim();

    // Code block detection
    if (trimmed.startsWith("```")) {
      if (inCodeBlock) {
        // Close code block
        const block = document.createElement("pre");
        block.className = "answer-code-block";
        block.textContent = codeBuffer.join("\n");
        elements.answerContentBody.appendChild(block);
        codeBuffer = [];
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
      }
      return;
    }

    if (inCodeBlock) {
      codeBuffer.push(line);
      return;
    }

    if (!trimmed) {
      return;
    }

    // Bullet points
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ") || trimmed.startsWith("• ")) {
      const p = document.createElement("div");
      p.className = "answer-bullet";
      p.innerHTML = formatCitationsAndMarkup(trimmed.substring(2));
      elements.answerContentBody.appendChild(p);
      return;
    }

    // Headers
    if (trimmed.startsWith("### ")) {
      const h = document.createElement("div");
      h.className = "card-title";
      h.style.margin = "14px 0 6px";
      h.innerHTML = formatCitationsAndMarkup(trimmed.substring(4));
      elements.answerContentBody.appendChild(h);
      return;
    }

    // Standard paragraph
    const p = document.createElement("p");
    p.className = "answer-paragraph";
    p.innerHTML = formatCitationsAndMarkup(line);
    elements.answerContentBody.appendChild(p);
  });
}

/**
 * Format markdown bold, and highlight citations [arxiv:2305.xxxx], [1], [WEB:title], etc.
 */
function formatCitationsAndMarkup(text) {
  // Sanitize basic HTML
  let escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Markdown bold
  escaped = escaped.replace(/\*\*(.*?)\*\*/g, `<strong style="color:#4dff4d;">$1</strong>`);

  // Inline citation brackets like [arxiv:1234.5678], [body][arxiv p.1], [WEB][Title], [1], [2]
  escaped = escaped.replace(/(\[[a-zA-Z0-9_\-\.\:\s\(\)\/]+\])/g, (match) => {
    return `<span class="citation-tag">${match}</span>`;
  });

  return escaped;
}

/**
 * Requirement 7: Devil's Advocate collapsed by default, click to expand with amber styling
 */
function renderDevilsAdvocate(devilAdvocateText) {
  // Ensure collapsed state initially
  elements.daBody.classList.add("collapsed");
  elements.daToggleBtn.classList.remove("is-expanded");
  elements.daCaret.textContent = "▼";

  if (devilAdvocateText && devilAdvocateText.trim().length > 0) {
    elements.daContentText.textContent = devilAdvocateText;
    elements.daStatusBadge.textContent = "CRITIQUE READY (CLICK TO EXPAND)";
    elements.daStatusBadge.style.color = "var(--color-amber)";
    elements.daStatusBadge.style.borderColor = "var(--color-amber)";
  } else {
    elements.daContentText.textContent = 
      "Devil's Advocate mode was not enabled for this query or no adversarial critiques were generated. Toggle Devil's Advocate ON in the research form for counter-arguments.";
    elements.daStatusBadge.textContent = "OFF / INACTIVE";
    elements.daStatusBadge.style.color = "var(--text-dim)";
    elements.daStatusBadge.style.borderColor = "var(--text-dim)";
  }
}

function toggleDevilsAdvocateSection() {
  const isCollapsed = elements.daBody.classList.contains("collapsed");
  if (isCollapsed) {
    elements.daBody.classList.remove("collapsed");
    elements.daToggleBtn.classList.add("is-expanded");
    elements.daCaret.textContent = "▲";
  } else {
    elements.daBody.classList.add("collapsed");
    elements.daToggleBtn.classList.remove("is-expanded");
    elements.daCaret.textContent = "▼";
  }
}

/**
 * Requirement 6: Reasoning timeline shows 4 steps sequentially:
 * Coordinator → Researcher → Synthesizer → Critic
 */
function renderReasoningTimeline(reasoningLog, fullData) {
  // Reset raw log list
  elements.rawLogList.innerHTML = "";

  // Populate raw log items
  if (Array.isArray(reasoningLog) && reasoningLog.length > 0) {
    reasoningLog.forEach((entry, idx) => {
      const row = document.createElement("div");
      row.className = "log-entry-row";
      const now = new Date();
      const timeStr = now.toTimeString().split(" ")[0];

      row.innerHTML = `
        <span class="log-timestamp">[${timeStr}.${idx + 1}]</span>
        <span class="log-bullet">▸</span>
        <span class="log-message">${escapeHtml(entry)}</span>
      `;
      elements.rawLogList.appendChild(row);
    });
  } else {
    elements.rawLogList.innerHTML = `<div class="empty-list-note">No execution log entries generated.</div>`;
  }

  // Update step summaries based on real log entries
  const plan = fullData.plan || {};
  const subQuestions = fullData.sub_questions || plan.sub_questions || [];
  elements.nodeCoordSummary.textContent = subQuestions.length > 0
    ? `${subQuestions.length} sub-questions planned`
    : "Strategy synthesized";

  const papersCount = (fullData.papers || []).length;
  elements.nodeResearchSummary.textContent = papersCount > 0
    ? `${papersCount} ArXiv sources queried`
    : `${fullData.chunks_used || 0} chunks retrieved`;

  const conf = Number(fullData.confidence || 0.0);
  elements.nodeSynthSummary.textContent = `Confidence: ${(conf * 100).toFixed(0)}%`;

  const replans = fullData.replan_count || 0;
  elements.nodeCriticSummary.textContent = replans > 0
    ? `Gate approved (${replans} replans)`
    : "Gate evaluated & approved";
}

function toggleReasoningLog() {
  const isHidden = elements.reasoningBody.classList.contains("collapsed");
  if (isHidden) {
    elements.reasoningBody.classList.remove("collapsed");
    elements.reasoningToggleIcon.textContent = "▼";
    elements.reasoningToggleText.textContent = "HIDE REASONING";
  } else {
    elements.reasoningBody.classList.add("collapsed");
    elements.reasoningToggleIcon.textContent = "▲";
    elements.reasoningToggleText.textContent = "SHOW REASONING";
  }
}

/**
 * Render retrieved citations list
 */
function renderRetrievedPapers(papers) {
  elements.retrievedPapersList.innerHTML = "";
  if (!papers || papers.length === 0) {
    elements.retrievedPapersCard.classList.add("hidden");
    return;
  }

  elements.retrievedPapersCard.classList.remove("hidden");
  elements.retrievedPapersCount.textContent = `${papers.length} PAPERS`;

  papers.slice(0, 8).forEach((p) => {
    const item = document.createElement("div");
    item.className = "paper-result-item";

    const title = p.title || "ArXiv Preprint";
    const authors = p.authors || "Unknown authors";
    const arxivId = p.arxiv_id || "";
    const score = p.final_score ? `SCORE: ${Number(p.final_score).toFixed(2)}` : "";

    item.innerHTML = `
      <div class="paper-result-main">
        <div class="paper-result-title">${escapeHtml(title)}</div>
        <div class="paper-result-meta">${escapeHtml(authors)} | ${escapeHtml(arxivId)}</div>
      </div>
      <div class="paper-result-score">${score}</div>
    `;
    elements.retrievedPapersList.appendChild(item);
  });
}

// ==========================================================================
// 7. SESSION STATS & TELEMETRY
// ==========================================================================

function updateSessionTelemetry(newConfidence) {
  sessionState.queriesRun += 1;
  sessionState.confidenceSum += Number(newConfidence) || 0.0;
  const avg = sessionState.confidenceSum / sessionState.queriesRun;

  elements.statQueriesRun.textContent = sessionState.queriesRun;
  elements.statAvgConfidence.textContent = avg.toFixed(2);
}

function resetToWelcome() {
  elements.resultsPanel.classList.add("hidden");
  elements.welcomeScreen.classList.remove("hidden");
  elements.loadingStateContainer.classList.add("hidden");
  hideError();
}

// ==========================================================================
// 8. ERROR HANDLING (Terminal-Style Box)
// ==========================================================================

function showError(msg) {
  elements.errorMessageText.textContent = msg;
  elements.terminalErrorBox.classList.remove("hidden");
  elements.terminalErrorBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function hideError() {
  elements.terminalErrorBox.classList.add("hidden");
}

function escapeHtml(str) {
  if (typeof str !== "string") return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
