/* PaySkillCreator — Frontend Logic */

const $ = (sel) => document.querySelector(sel);
const chatArea = $("#chatArea");
const queryInput = $("#queryInput");
const sendBtn = $("#sendBtn");
const clearBtn = $("#clearBtn");
const repoPathInput = $("#repoPath");
const modelInfo = $("#modelInfo");

let isAnalyzing = false;

// ---- Init ----

async function init() {
  try {
    const res = await fetch("/api/config");
    const cfg = await res.json();
    repoPathInput.value = cfg.repo_path || "";
    modelInfo.textContent = cfg.model_name || "unknown";
  } catch {
    modelInfo.textContent = "连接失败";
  }
  queryInput.addEventListener("input", onInputChange);
  queryInput.addEventListener("keydown", onKeyDown);
  sendBtn.addEventListener("click", doSend);
  clearBtn.addEventListener("click", clearChat);
  document.querySelectorAll(".quick-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      queryInput.value = btn.dataset.query;
      onInputChange();
      doSend();
    });
  });
}

// ---- Input Handling ----

function onInputChange() {
  const ta = queryInput;
  ta.style.height = "auto";
  ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
  sendBtn.disabled = !ta.value.trim() || isAnalyzing;
}

function onKeyDown(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled) doSend();
  }
}

// ---- Send ----

async function doSend() {
  const query = queryInput.value.trim();
  if (!query || isAnalyzing) return;

  const repoPath = repoPathInput.value.trim();
  if (!repoPath) {
    appendError("请先在左侧填入仓库路径");
    return;
  }

  const skill = document.querySelector('input[name="skill"]:checked')?.value || null;

  hideWelcome();
  appendUserMessage(query);

  queryInput.value = "";
  queryInput.style.height = "auto";
  sendBtn.disabled = true;
  isAnalyzing = true;

  const { progressEl, contentEl, metaEl } = appendAIMessage();

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_path: repoPath, query, skill }),
    });

    await processSSE(res.body, progressEl, contentEl, metaEl);
  } catch (err) {
    setContent(contentEl, `**请求失败**: ${err.message}`);
  } finally {
    isAnalyzing = false;
    onInputChange();
  }
}

// ---- SSE Processing ----

async function processSSE(body, progressEl, contentEl, metaEl) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const steps = {
    routing: { label: "识别任务类型", done: false },
    retrieving: { label: "检索仓库上下文", done: false },
    executing: { label: "执行 Skill 分析", done: false },
    formatting: { label: "生成结构化报告", done: false },
  };
  renderProgress(progressEl, steps, null);

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    let eventType = "";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        const raw = line.slice(6);
        try {
          const data = JSON.parse(raw);
          handleSSEEvent(eventType, data, steps, progressEl, contentEl, metaEl);
        } catch { /* skip malformed */ }
      }
    }
  }
}

function handleSSEEvent(event, data, steps, progressEl, contentEl, metaEl) {
  if (event === "status") {
    const stage = data.stage;
    // mark previous stages as done
    const stageOrder = ["routing", "retrieving", "executing", "formatting"];
    const idx = stageOrder.indexOf(stage);
    for (let i = 0; i < idx; i++) {
      if (steps[stageOrder[i]]) steps[stageOrder[i]].done = true;
    }

    if (stage === "routing" && data.skill_type) {
      steps.routing.done = true;
      steps.routing.detail = `${data.skill_type}`;
    }

    renderProgress(progressEl, steps, stage);
  }

  if (event === "result") {
    Object.values(steps).forEach((s) => (s.done = true));
    renderProgress(progressEl, steps, null);

    const md = data.formatted_output || "*无结果*";
    setContent(contentEl, md);

    const meta = data.metadata || {};
    renderMetadata(metaEl, data.skill_type, meta);
  }

  if (event === "error") {
    Object.values(steps).forEach((s) => (s.done = true));
    renderProgress(progressEl, steps, null);
    contentEl.closest(".msg-ai")?.classList.add("msg-error");
    setContent(contentEl, `**错误**: ${data.message}`);
  }
}

// ---- Rendering ----

function renderProgress(el, steps, activeStage) {
  el.innerHTML = Object.entries(steps)
    .map(([key, s]) => {
      let cls = "";
      let icon = "○";
      if (s.done) {
        cls = "done";
        icon = "✓";
      } else if (key === activeStage) {
        cls = "active";
        icon = '<span class="spinner"></span>';
      }
      const detail = s.detail ? ` — ${s.detail}` : "";
      return `<div class="step ${cls}"><span class="step-icon">${icon}</span>${s.label}${detail}</div>`;
    })
    .join("");
}

function setContent(el, markdown) {
  el.innerHTML = marked.parse(markdown);
}

function renderMetadata(el, skillType, meta) {
  const parts = [];
  if (skillType) parts.push(`Skill: ${skillType}`);
  if (meta.router_method) parts.push(`路由: ${meta.router_method}`);
  if (meta.model) parts.push(`模型: ${meta.model}`);
  if (meta.total_elapsed_ms) parts.push(`总耗时: ${(meta.total_elapsed_ms / 1000).toFixed(1)}s`);
  else if (meta.skill_elapsed_ms) parts.push(`分析耗时: ${(meta.skill_elapsed_ms / 1000).toFixed(1)}s`);
  if (parts.length) {
    el.innerHTML = parts.map((p) => `<span>${p}</span>`).join("");
  }
}

// ---- DOM Helpers ----

function hideWelcome() {
  const w = $(".welcome-message");
  if (w) w.remove();
}

function appendUserMessage(text) {
  const div = document.createElement("div");
  div.className = "chat-message msg-user";
  div.innerHTML = `<div class="msg-content">${escapeHtml(text)}</div>`;
  chatArea.appendChild(div);
  scrollToBottom();
}

function appendAIMessage() {
  const div = document.createElement("div");
  div.className = "chat-message msg-ai";
  div.innerHTML = `
    <div class="progress-steps"></div>
    <div class="msg-content"></div>
    <div class="metadata-bar"></div>
  `;
  chatArea.appendChild(div);
  scrollToBottom();

  return {
    progressEl: div.querySelector(".progress-steps"),
    contentEl: div.querySelector(".msg-content"),
    metaEl: div.querySelector(".metadata-bar"),
  };
}

function appendError(text) {
  const div = document.createElement("div");
  div.className = "chat-message msg-ai msg-error";
  div.innerHTML = `<div class="msg-content"><strong>${escapeHtml(text)}</strong></div>`;
  chatArea.appendChild(div);
  scrollToBottom();
}

function clearChat() {
  chatArea.innerHTML = `
    <div class="welcome-message">
      <h2>欢迎使用 PaySkillCreator</h2>
      <p>输入你的问题，开始分析目标仓库。</p>
      <div class="quick-actions">
        <button class="quick-btn" data-query="请介绍这个仓库的整体架构和核心模块">仓库架构概览</button>
        <button class="quick-btn" data-query="分析支付下单的调用链路">支付链路分析</button>
        <button class="quick-btn" data-query="添加一个新的支付渠道需要改哪些地方">新增支付渠道方案</button>
      </div>
    </div>
  `;
  document.querySelectorAll(".quick-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      queryInput.value = btn.dataset.query;
      onInputChange();
      doSend();
    });
  });
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    chatArea.scrollTop = chatArea.scrollHeight;
  });
}

function escapeHtml(text) {
  const d = document.createElement("div");
  d.textContent = text;
  return d.innerHTML;
}

// ---- Boot ----
init();
