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
let mermaidInitialized = false;

// ---- Init ----

async function init() {
  initMermaid();
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
      renderDiagrams(contentEl, data.diagrams || []);
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

function initMermaid() {
  if (window.mermaid && !mermaidInitialized) {
    window.mermaid.initialize({
      startOnLoad: false,
      theme: "dark",
      securityLevel: "loose",
    });
    mermaidInitialized = true;
  }
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

function renderDiagrams(contentEl, diagrams) {
  if (!Array.isArray(diagrams) || !diagrams.length) return;

  const businessOverview = diagrams.find((diagram) => diagram.graph_type === "business_overview");
  if (!businessOverview) return;

  const wrapper = document.createElement("section");
  wrapper.className = "diagram-card";
  wrapper.innerHTML = `
    <div class="diagram-header">
      <div class="diagram-badge">业务流程概览图</div>
      <h3>${escapeHtml(businessOverview.title || "业务流程概览图")}</h3>
      ${businessOverview.summary ? `<p>${escapeHtml(businessOverview.summary)}</p>` : ""}
    </div>
    <div class="diagram-toolbar">
      <div class="diagram-legend">
        <span><i class="legend-dot legend-process"></i>业务步骤</span>
        <span><i class="legend-dot legend-page"></i>页面节点</span>
        <span><i class="legend-dot legend-result"></i>结果节点</span>
        <span><i class="legend-dot legend-decision"></i>条件分支</span>
      </div>
    </div>
    <div class="diagram-render" data-diagram-render></div>
  `;

  if (Array.isArray(businessOverview.annotations) && businessOverview.annotations.length) {
    const notes = document.createElement("div");
    notes.className = "diagram-notes";
    notes.innerHTML = businessOverview.annotations
      .map((annotation) => {
        const title = annotation.title ? `${escapeHtml(annotation.title)}: ` : "";
        return `<div class="diagram-note">${title}${escapeHtml(annotation.content)}</div>`;
      })
      .join("");
    wrapper.appendChild(notes);
  }

  contentEl.prepend(wrapper);
  renderBusinessOverviewInto(
    wrapper.querySelector("[data-diagram-render]"),
    businessOverview,
  );
}

async function renderMermaidInto(container, source) {
  if (!container || !window.mermaid) {
    if (container) container.innerHTML = `<pre><code>${escapeHtml(source)}</code></pre>`;
    return;
  }

  const id = `mermaid-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  try {
    const { svg } = await window.mermaid.render(id, source);
    container.innerHTML = svg;
  } catch {
    container.innerHTML = `<pre><code>${escapeHtml(source)}</code></pre>`;
  }
}

function renderBusinessOverviewInto(container, diagram) {
  if (!container) return;

  const svgMarkup = buildBusinessOverviewSvg(diagram);
  if (!svgMarkup) {
    renderMermaidFallbackCard(container, diagram.mermaid_fallback || "");
    return;
  }

  container.innerHTML = `
    <div class="diagram-surface">
      ${svgMarkup}
    </div>
    ${diagram.mermaid_fallback ? `
      <details class="diagram-fallback">
        <summary>查看 Mermaid 降级内容</summary>
        <pre><code>${escapeHtml(diagram.mermaid_fallback)}</code></pre>
      </details>
    ` : ""}
  `;
}

function renderMermaidFallbackCard(container, source) {
  if (!source) {
    container.innerHTML = '<div class="diagram-empty">暂无可渲染的流程图数据。</div>';
    return;
  }

  container.innerHTML = `
    <div class="diagram-empty">结构化图布局失败，已回退到 Mermaid 展示。</div>
    <div class="diagram-surface"></div>
  `;
  renderMermaidInto(container.querySelector(".diagram-surface"), source);
}

function buildBusinessOverviewSvg(diagram) {
  if (!diagram || !Array.isArray(diagram.nodes) || !diagram.nodes.length) return "";

  const layout = layoutDiagram(diagram);
  if (!layout) return "";

  const { nodeBoxes, annotationBoxes, width, height } = layout;
  const edgeMarkup = renderEdgeMarkup(diagram, nodeBoxes);
  const annotationMarkup = renderAnnotationMarkup(diagram, nodeBoxes, annotationBoxes);
  const nodeMarkup = renderNodeMarkup(diagram, nodeBoxes);

  return `
    <svg class="business-overview-svg" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${escapeHtmlAttr(diagram.title || "业务流程概览图")}">
      <defs>
        <marker id="diagram-arrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L10,5 L0,10 z" fill="#7dd3fc"></path>
        </marker>
        <marker id="diagram-arrow-warning" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L10,5 L0,10 z" fill="#fbbf24"></path>
        </marker>
        <marker id="diagram-arrow-danger" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L10,5 L0,10 z" fill="#f87171"></path>
        </marker>
      </defs>
      ${edgeMarkup}
      ${annotationMarkup}
      ${nodeMarkup}
    </svg>
  `;
}

function layoutDiagram(diagram) {
  const nodes = diagram.nodes || [];
  const edges = diagram.edges || [];
  const levelMap = assignNodeLevels(nodes, edges);
  const groups = {};

  for (const node of nodes) {
    const level = levelMap[node.id] ?? 0;
    if (!groups[level]) groups[level] = [];
    groups[level].push(node);
  }

  const levelKeys = Object.keys(groups).map(Number).sort((a, b) => a - b);
  const laneWidth = 240;
  const levelGapY = 150;
  const nodeGapX = 80;
  const paddingX = 60;
  const paddingY = 50;
  const noteStartX = 900;

  const nodeBoxes = {};
  let graphWidth = 0;

  for (const level of levelKeys) {
    const items = groups[level];
    const widths = items.map(getNodeDimensions);
    const rowWidth = widths.reduce((sum, size) => sum + size.width, 0) + Math.max(0, items.length - 1) * nodeGapX;
    let currentX = paddingX + Math.max(0, (noteStartX - paddingX * 2 - rowWidth) / 2);
    const y = paddingY + level * levelGapY;

    items.forEach((node, index) => {
      const size = widths[index];
      nodeBoxes[node.id] = {
        x: currentX,
        y,
        width: size.width,
        height: size.height,
        centerX: currentX + size.width / 2,
        centerY: y + size.height / 2,
      };
      currentX += size.width + nodeGapX;
      graphWidth = Math.max(graphWidth, currentX - nodeGapX + paddingX);
    });
  }

  const annotationBoxes = {};
  const annotations = Array.isArray(diagram.annotations) ? diagram.annotations : [];
  const perLevelOffsets = {};
  let noteWidthMax = 0;
  let noteBottom = 0;

  annotations.forEach((annotation, index) => {
    const anchor = nodeBoxes[annotation.anchor_node];
    const noteWidth = 250;
    const contentLines = wrapTextForLayout(`${annotation.title ? `${annotation.title}: ` : ""}${annotation.content}`, 24);
    const noteHeight = Math.max(92, 36 + contentLines.length * 18);
    const lane = index % 2;
    const baseLevel = anchor ? Math.round((anchor.y - paddingY) / levelGapY) : index;
    const offsetIndex = perLevelOffsets[baseLevel] || 0;
    perLevelOffsets[baseLevel] = offsetIndex + 1;
    const x = Math.max(noteStartX, graphWidth + 40) + lane * (laneWidth + 24);
    const y = anchor ? Math.max(24, anchor.y - 10 + offsetIndex * 26) : paddingY + index * 110;

    annotationBoxes[annotation.id] = { x, y, width: noteWidth, height: noteHeight, lines: contentLines };
    noteWidthMax = Math.max(noteWidthMax, x + noteWidth + 40);
    noteBottom = Math.max(noteBottom, y + noteHeight + 40);
  });

  const width = Math.max(graphWidth + 60, noteWidthMax || graphWidth + 60, noteStartX + 40);
  const height = Math.max(
    ...Object.values(nodeBoxes).map((box) => box.y + box.height + 60),
    noteBottom || 0,
    420,
  );

  return { nodeBoxes, annotationBoxes, width, height };
}

function assignNodeLevels(nodes, edges) {
  const incoming = {};
  const outgoing = {};
  const levels = {};

  nodes.forEach((node) => {
    incoming[node.id] = [];
    outgoing[node.id] = [];
  });
  edges.forEach((edge) => {
    if (incoming[edge.to_node]) incoming[edge.to_node].push(edge.from_node);
    if (outgoing[edge.from_node]) outgoing[edge.from_node].push(edge.to_node);
  });

  const roots = nodes.filter((node) => incoming[node.id] && incoming[node.id].length === 0);
  const queue = roots.length ? roots.map((node) => node.id) : nodes.slice(0, 1).map((node) => node.id);

  queue.forEach((id) => { levels[id] = 0; });

  while (queue.length) {
    const current = queue.shift();
    for (const next of outgoing[current] || []) {
      const nextLevel = (levels[current] || 0) + 1;
      if (levels[next] == null || levels[next] < nextLevel) {
        levels[next] = nextLevel;
        queue.push(next);
      }
    }
  }

  nodes.forEach((node) => {
    if (levels[node.id] == null) levels[node.id] = 0;
  });
  return levels;
}

function getNodeDimensions(node) {
  const labelLength = (node.label || "").length;
  switch (node.node_type) {
    case "start":
    case "end":
      return { width: Math.max(110, labelLength * 12), height: 54 };
    case "decision":
      return { width: Math.max(150, labelLength * 10), height: 88 };
    case "page":
      return { width: Math.max(170, labelLength * 9), height: 76 };
    case "result":
      return { width: Math.max(170, labelLength * 9), height: 70 };
    default:
      return { width: Math.max(150, labelLength * 9), height: 68 };
  }
}

function renderEdgeMarkup(diagram, nodeBoxes) {
  return (diagram.edges || []).map((edge) => {
    const from = nodeBoxes[edge.from_node];
    const to = nodeBoxes[edge.to_node];
    if (!from || !to) return "";

    const points = computeEdgePath(from, to);
    const edgeColor = edgeTypeColor(edge.edge_type);
    const label = edge.label || edge.condition;
    const labelX = (points.labelX).toFixed(1);
    const labelY = (points.labelY).toFixed(1);

    return `
      <g class="diagram-edge edge-${edge.edge_type || "transition"}">
        <path d="${points.path}" fill="none" stroke="${edgeColor}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" marker-end="url(${edgeTypeMarker(edge.edge_type)})"></path>
        ${label ? `
          <g transform="translate(${labelX}, ${labelY})">
            <rect x="-62" y="-15" width="124" height="28" rx="14" fill="rgba(15,15,26,0.92)" stroke="${edgeColor}" stroke-width="1"></rect>
            <text text-anchor="middle" dominant-baseline="middle" fill="#dbeafe" font-size="12" font-weight="600">${escapeSvg(label)}</text>
          </g>
        ` : ""}
      </g>
    `;
  }).join("");
}

function computeEdgePath(from, to) {
  const startX = from.centerX;
  const startY = from.y + from.height;
  const endX = to.centerX;
  const endY = to.y;
  const deltaY = Math.max(42, (endY - startY) / 2);
  const c1Y = startY + deltaY;
  const c2Y = endY - deltaY;
  const path = `M ${startX} ${startY} C ${startX} ${c1Y}, ${endX} ${c2Y}, ${endX} ${endY}`;
  return {
    path,
    labelX: startX + (endX - startX) / 2,
    labelY: startY + (endY - startY) / 2,
  };
}

function renderNodeMarkup(diagram, nodeBoxes) {
  return (diagram.nodes || []).map((node) => {
    const box = nodeBoxes[node.id];
    if (!box) return "";

    const fill = nodeFill(node);
    const stroke = nodeStroke(node);
    const textLines = wrapTextForLayout(node.label || "", node.node_type === "decision" ? 14 : 16);
    const descLine = node.description ? `<text x="${box.centerX}" y="${box.y + box.height - 14}" text-anchor="middle" fill="#94a3b8" font-size="11">${escapeSvg(truncateText(node.description, 24))}</text>` : "";

    return `
      <g class="diagram-node node-${node.node_type}">
        ${renderNodeShape(node, box, fill, stroke)}
        ${textLines.map((line, idx) => {
          const offset = box.centerY - ((textLines.length - 1) * 8) + idx * 16;
          return `<text x="${box.centerX}" y="${offset}" text-anchor="middle" dominant-baseline="middle" fill="#f8fafc" font-size="14" font-weight="600">${escapeSvg(line)}</text>`;
        }).join("")}
        ${descLine}
      </g>
    `;
  }).join("");
}

function renderNodeShape(node, box, fill, stroke) {
  if (node.node_type === "start" || node.node_type === "end") {
    return `<ellipse cx="${box.centerX}" cy="${box.centerY}" rx="${box.width / 2}" ry="${box.height / 2}" fill="${fill}" stroke="${stroke}" stroke-width="2"></ellipse>`;
  }
  if (node.node_type === "decision") {
    const top = `${box.centerX},${box.y}`;
    const right = `${box.x + box.width},${box.centerY}`;
    const bottom = `${box.centerX},${box.y + box.height}`;
    const left = `${box.x},${box.centerY}`;
    return `<polygon points="${top} ${right} ${bottom} ${left}" fill="${fill}" stroke="${stroke}" stroke-width="2"></polygon>`;
  }
  const rx = node.node_type === "result" ? 22 : 16;
  return `<rect x="${box.x}" y="${box.y}" width="${box.width}" height="${box.height}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="2"></rect>`;
}

function renderAnnotationMarkup(diagram, nodeBoxes, annotationBoxes) {
  return (diagram.annotations || []).map((annotation) => {
    const box = annotationBoxes[annotation.id];
    if (!box) return "";
    const anchor = nodeBoxes[annotation.anchor_node];
    const pointer = anchor ? renderAnnotationPointer(box, anchor) : "";
    const badge = annotationBadge(annotation.annotation_type);

    return `
      <g class="diagram-annotation annotation-${annotation.annotation_type}">
        <rect x="${box.x}" y="${box.y}" width="${box.width}" height="${box.height}" rx="18" fill="rgba(251,191,36,0.12)" stroke="rgba(251,191,36,0.65)" stroke-dasharray="5 5" stroke-width="1.5"></rect>
        ${pointer}
        <text x="${box.x + 16}" y="${box.y + 24}" fill="#fcd34d" font-size="12" font-weight="700">${escapeSvg(badge)}</text>
        ${box.lines.map((line, idx) => `<text x="${box.x + 16}" y="${box.y + 48 + idx * 16}" fill="#fef3c7" font-size="12">${escapeSvg(line)}</text>`).join("")}
      </g>
    `;
  }).join("");
}

function renderAnnotationPointer(box, anchor) {
  const startX = box.x;
  const startY = box.y + Math.min(box.height - 24, 42);
  const tipX = anchor.x + anchor.width;
  const tipY = anchor.centerY;
  return `<path d="M ${startX} ${startY - 10} L ${startX - 18} ${startY} L ${startX} ${startY + 10}" fill="rgba(251,191,36,0.18)" stroke="rgba(251,191,36,0.65)" stroke-width="1.5"></path>
    <path d="M ${startX - 18} ${startY} L ${tipX + 12} ${tipY}" fill="none" stroke="rgba(251,191,36,0.55)" stroke-width="1.4" stroke-dasharray="4 4"></path>`;
}

function nodeFill(node) {
  if (node.node_type === "page") return "rgba(96, 165, 250, 0.16)";
  if (node.node_type === "result") return "rgba(248, 113, 113, 0.12)";
  if (node.node_type === "decision") return "rgba(251, 191, 36, 0.16)";
  if (node.node_type === "start" || node.node_type === "end") return "rgba(226, 232, 240, 0.08)";
  return "rgba(148, 163, 184, 0.10)";
}

function nodeStroke(node) {
  if (node.node_type === "page") return "#60a5fa";
  if (node.node_type === "result") return "#f87171";
  if (node.node_type === "decision") return "#fbbf24";
  if (node.node_type === "start" || node.node_type === "end") return "#e2e8f0";
  return "#cbd5e1";
}

function edgeTypeColor(edgeType) {
  if (edgeType === "failure") return "#f87171";
  if (edgeType === "timeout") return "#fbbf24";
  if (edgeType === "retry") return "#f59e0b";
  if (edgeType === "success") return "#34d399";
  return "#7dd3fc";
}

function edgeTypeMarker(edgeType) {
  if (edgeType === "failure") return "#diagram-arrow-danger";
  if (edgeType === "timeout" || edgeType === "retry") return "#diagram-arrow-warning";
  return "#diagram-arrow";
}

function annotationBadge(type) {
  if (type === "payload") return "Payload";
  if (type === "rule") return "Rule";
  if (type === "risk") return "Risk";
  return "Note";
}

function wrapTextForLayout(text, maxChars) {
  const raw = (text || "").replace(/\s+/g, " ").trim();
  if (!raw) return [""];
  const segments = [];
  let current = "";

  for (const char of raw) {
    current += char;
    if (current.length >= maxChars) {
      segments.push(current);
      current = "";
    }
  }
  if (current) segments.push(current);
  return segments.slice(0, 6);
}

function truncateText(text, maxChars) {
  if (!text || text.length <= maxChars) return text || "";
  return `${text.slice(0, maxChars - 1)}…`;
}

function escapeSvg(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function escapeHtmlAttr(text) {
  return escapeHtml(text).replace(/"/g, "&quot;");
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
