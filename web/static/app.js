/* PaySkillCreator — Frontend Logic */

const $ = (sel) => document.querySelector(sel);
const chatArea = $("#chatArea");
const queryInput = $("#queryInput");
const sendBtn = $("#sendBtn");
const clearBtn = $("#clearBtn");
const repoPathInput = $("#repoPath");
const modelSelect = $("#modelSelect");

let isAnalyzing = false;
let currentSkillType = null;

// ---- Init ----

async function init() {
  try {
    const res = await fetch("/api/config");
    const cfg = await res.json();
    repoPathInput.value = cfg.repo_path || "";
    populateModelSelect(cfg.models || [], cfg.default_model || "");
  } catch {
    modelSelect.innerHTML = '<option value="">连接失败</option>';
  }
  queryInput.addEventListener("input", onInputChange);
  queryInput.addEventListener("keydown", onKeyDown);
  sendBtn.addEventListener("click", doSend);
  clearBtn.addEventListener("click", clearChat);
  bindQuickButtons();
}

function populateModelSelect(models, defaultModel) {
  modelSelect.innerHTML = "";
  if (!models.length) {
    modelSelect.innerHTML = '<option value="">无可用模型</option>';
    return;
  }

  const grouped = {};
  for (const m of models) {
    const group = m.provider || "其他";
    if (!grouped[group]) grouped[group] = [];
    grouped[group].push(m);
  }

  for (const [provider, items] of Object.entries(grouped)) {
    const optgroup = document.createElement("optgroup");
    optgroup.label = provider;
    for (const m of items) {
      const opt = document.createElement("option");
      opt.value = m.id;
      opt.textContent = `${m.name}`;
      if (m.description) opt.title = m.description;
      if (m.id === defaultModel) opt.selected = true;
      optgroup.appendChild(opt);
    }
    modelSelect.appendChild(optgroup);
  }
}

function bindQuickButtons() {
  document.querySelectorAll(".quick-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      queryInput.value = btn.dataset.query;
      if (btn.dataset.skill) {
        const radio = document.querySelector(`input[name="skill"][value="${btn.dataset.skill}"]`);
        if (radio) radio.checked = true;
      }
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
  currentSkillType = skill;

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
      body: JSON.stringify({ repo_path: repoPath, query, skill, model: modelSelect.value || null }),
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

const ANALYSIS_STEPS = {
  routing: { label: "识别任务类型", done: false },
  retrieving: { label: "检索仓库上下文", done: false },
  executing: { label: "执行 Skill 分析", done: false },
  formatting: { label: "生成结构化报告", done: false },
};

const GENERATE_SKILL_STEPS = {
  routing: { label: "识别任务类型", done: false },
  retrieving: { label: "检索仓库上下文", done: false },
  executing: { label: "运行上游分析 Skill", done: false },
  spec_generating: { label: "生成 Skill 规格", done: false },
  md_rendering: { label: "渲染 SKILL.md", done: false },
};

function buildSteps(skillType) {
  const template = skillType === "generate_skill" ? GENERATE_SKILL_STEPS : ANALYSIS_STEPS;
  const steps = {};
  for (const [k, v] of Object.entries(template)) {
    steps[k] = { ...v, done: false, detail: undefined };
  }
  return steps;
}

async function processSSE(body, progressEl, contentEl, metaEl) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  let steps = buildSteps(currentSkillType);
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
          steps = handleSSEEvent(eventType, data, steps, progressEl, contentEl, metaEl);
        } catch { /* skip malformed */ }
      }
    }
  }
}

function handleSSEEvent(event, data, steps, progressEl, contentEl, metaEl) {
  if (event === "status") {
    const stage = data.stage;

    if (stage === "routing" && data.skill_type) {
      currentSkillType = data.skill_type;
      if (data.skill_type === "generate_skill" && !steps.spec_generating) {
        steps = buildSteps("generate_skill");
      }
      steps.routing.done = true;
      steps.routing.detail = data.skill_type === "generate_skill" ? "生成 SKILL.md" : data.skill_type;
    }

    const stageOrder = Object.keys(steps);
    const idx = stageOrder.indexOf(stage);
    for (let i = 0; i < idx; i++) {
      if (steps[stageOrder[i]]) steps[stageOrder[i]].done = true;
    }

    renderProgress(progressEl, steps, stage);
  }

  if (event === "result") {
    Object.values(steps).forEach((s) => (s.done = true));
    renderProgress(progressEl, steps, null);

    const rawOutput = data.formatted_output || "";
    const skillType = data.skill_type || currentSkillType;

    if (skillType === "generate_skill" && rawOutput) {
      renderSkillMd(contentEl, rawOutput);
    } else {
      setContent(contentEl, rawOutput || "*无结果*");
    }

    const meta = data.metadata || {};
    renderMetadata(metaEl, skillType, meta);
  }

  if (event === "error") {
    Object.values(steps).forEach((s) => (s.done = true));
    renderProgress(progressEl, steps, null);
    contentEl.closest(".msg-ai")?.classList.add("msg-error");
    setContent(contentEl, `**错误**: ${data.message}`);
  }

  return steps;
}

function appendDownloadButton(contentEl, markdown) {
  const wrapper = document.createElement("div");
  wrapper.className = "download-bar";

  const btn = document.createElement("button");
  btn.className = "btn-download";
  btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> 下载 SKILL.md`;
  btn.addEventListener("click", () => {
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "SKILL.md";
    a.click();
    URL.revokeObjectURL(url);
  });

  const copyBtn = document.createElement("button");
  copyBtn.className = "btn-download btn-copy";
  copyBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg> 复制内容`;
  copyBtn.addEventListener("click", () => {
    navigator.clipboard.writeText(markdown).then(() => {
      copyBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> 已复制`;
      setTimeout(() => {
        copyBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg> 复制内容`;
      }, 2000);
    });
  });

  wrapper.appendChild(btn);
  wrapper.appendChild(copyBtn);
  contentEl.appendChild(wrapper);
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

function parseFrontmatter(raw) {
  const trimmed = raw.trim();
  if (!trimmed.startsWith("---")) return { frontmatter: null, body: raw };

  const end = trimmed.indexOf("---", 3);
  if (end === -1) return { frontmatter: null, body: raw };

  const fmBlock = trimmed.slice(3, end).trim();
  const body = trimmed.slice(end + 3).trim();

  const fm = {};
  for (const line of fmBlock.split("\n")) {
    const idx = line.indexOf(":");
    if (idx > 0) {
      const key = line.slice(0, idx).trim();
      let val = line.slice(idx + 1).trim();
      if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
        val = val.slice(1, -1);
      }
      fm[key] = val;
    }
  }
  return { frontmatter: fm, body };
}

function renderSkillMd(contentEl, rawOutput) {
  const { frontmatter, body } = parseFrontmatter(rawOutput);

  let html = "";

  if (frontmatter) {
    html += '<div class="frontmatter-card">';
    html += '<div class="frontmatter-badge">SKILL.md · Codex Compatible</div>';
    if (frontmatter.name) {
      html += `<div class="frontmatter-name">${escapeHtml(frontmatter.name)}</div>`;
    }
    if (frontmatter.description) {
      html += `<div class="frontmatter-desc">${escapeHtml(frontmatter.description)}</div>`;
    }
    html += "</div>";
  }

  html += marked.parse(body);

  contentEl.innerHTML = html;
  appendDownloadButton(contentEl, rawOutput);
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
        <button class="quick-btn quick-btn-accent" data-query="为这个仓库生成代码链路追踪的 SKILL.md" data-skill="generate_skill">生成 SKILL.md</button>
      </div>
    </div>
  `;
  bindQuickButtons();
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
