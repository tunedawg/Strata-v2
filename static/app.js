const state = {
  datasets: [],
  activeTab: "index",
  activeDataset: null,
  indexResults: {},
  productionResults: {},
  productionSelections: {},
  redactionResults: [],
  indexPoller: null,
  redactionPoller: null,
};

function qs(selector, root = document) {
  return root.querySelector(selector);
}

function qsa(selector, root = document) {
  return [...root.querySelectorAll(selector)];
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function toast(message) {
  const host = qs("#toast-host");
  const item = document.createElement("div");
  item.className = "toast";
  item.textContent = message;
  host.appendChild(item);
  window.setTimeout(() => item.remove(), 2600);
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const contentType = response.headers.get("content-type") || "";
  if (!response.ok) {
    if (contentType.includes("application/json")) {
      const payload = await response.json();
      throw new Error(payload.error || "Request failed.");
    }
    throw new Error("Request failed.");
  }
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.blob();
}

function setStatus(kind, text) {
  const pill = qs("#status-pill");
  pill.className = `header-status${kind ? ` ${kind}` : ""}`;
  qs("#status-pill-text").textContent = text;
}

function setIndexFilesLabel() {
  qs("#index-files-label").textContent = state.activeDataset
    ? `Files In: ${state.activeDataset}`
    : "Files In";
}

function addTermRow(host, value = "") {
  const row = document.createElement("div");
  row.className = "term-row";
  row.innerHTML = `
    <input type="text" value="${esc(value)}" placeholder='e.g. "wrongful termination" AND NOT severance'>
    <button class="term-remove" type="button">×</button>
  `;
  row.querySelector("button").addEventListener("click", () => row.remove());
  row.querySelector("input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      if (host.id === "index-terms") {
        handleAction(runIndexSearch);
      } else if (host.id === "production-terms") {
        handleAction(runProductionSearch);
      }
    }
  });
  host.appendChild(row);
}

function readTerms(hostSelector) {
  return qsa(`${hostSelector} .term-row input`)
    .map((input) => input.value.trim())
    .filter(Boolean);
}

function resetTerms(host) {
  host.innerHTML = "";
  addTermRow(host);
}

function renderDatasets() {
  const host = qs("#dataset-list");
  setIndexFilesLabel();
  if (!state.datasets.length) {
    host.innerHTML = `<div class="empty-state"><div class="empty-state-mark"></div><p>No productions yet</p></div>`;
    syncDatasetSelectors();
    return;
  }

  host.innerHTML = state.datasets.map((dataset) => `
    <article class="dataset-tile ${dataset.name === state.activeDataset ? "active" : ""}" data-dataset="${esc(dataset.name)}">
      <div class="dataset-icon"></div>
      <div>
        <div class="dataset-name">${esc(dataset.name)}</div>
        <div class="dataset-meta">${dataset.file_count} file${dataset.file_count === 1 ? "" : "s"} · ${dataset.indexed ? "indexed" : "not indexed"}</div>
      </div>
      <div class="dataset-actions">
        <button class="dataset-mini" data-load="${esc(dataset.name)}" title="Load">↺</button>
        <button class="dataset-mini" data-delete="${esc(dataset.name)}" title="Delete">🗑</button>
      </div>
    </article>
  `).join("");

  qsa("[data-dataset]").forEach((node) => node.addEventListener("click", () => {
    state.activeDataset = node.dataset.dataset;
    renderDatasets();
    syncDatasetSelectors();
    updateHeaderDataset();
  }));

  qsa("[data-load]").forEach((button) => button.addEventListener("click", async (event) => {
    event.stopPropagation();
    await loadIndex(button.dataset.load);
  }));

  qsa("[data-delete]").forEach((button) => button.addEventListener("click", async (event) => {
    event.stopPropagation();
    const name = button.dataset.delete;
    if (!window.confirm(`Delete production "${name}" and all local files?`)) {
      return;
    }
    await api(`/api/datasets/${encodeURIComponent(name)}`, { method: "DELETE" });
    if (state.activeDataset === name) {
      state.activeDataset = null;
    }
    toast(`Deleted ${name}`);
    await refreshBootstrap();
  }));

  syncDatasetSelectors();
}

function syncDatasetSelectors() {
  const selectors = [qs("#production-dataset"), qs("#redaction-dataset")];
  selectors.forEach((select) => {
    const current = select.value;
    select.innerHTML = state.datasets.map((dataset) => `<option value="${esc(dataset.name)}">${esc(dataset.name)}</option>`).join("");
    if (state.activeDataset && state.datasets.some((dataset) => dataset.name === state.activeDataset)) {
      select.value = state.activeDataset;
    } else if (current) {
      select.value = current;
    }
  });
}

function updateHeaderDataset() {
  const dataset = state.datasets.find((item) => item.name === state.activeDataset);
  if (!dataset) {
    setStatus("", "No dataset loaded");
    return;
  }
  setStatus("ready", `${dataset.name} · ${dataset.file_count} file${dataset.file_count === 1 ? "" : "s"}`);
}

async function refreshBootstrap() {
  const payload = await api("/api/bootstrap");
  state.datasets = payload.datasets;
  state.activeDataset = payload.loaded_dataset || state.activeDataset || state.datasets[0]?.name || null;
  renderDatasets();
  syncDatasetSelectors();
  updateIndexStatus(payload.index_status);
  updateRedactionStatus(payload.redaction_status);
  updateHeaderDataset();
}

async function createDataset() {
  const input = qs("#dataset-name");
  const name = input.value.trim();
  if (!name) {
    return;
  }
  const result = await api("/api/datasets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  input.value = "";
  state.activeDataset = result.name;
  toast(`Created ${result.name}`);
  await refreshBootstrap();
}

async function uploadFiles(files) {
  if (!state.activeDataset) {
    throw new Error("Select a production first.");
  }
  const form = new FormData();
  [...files].forEach((file) => form.append("files", file, file.webkitRelativePath || file.name));
  const result = await api(`/api/datasets/${encodeURIComponent(state.activeDataset)}/upload`, {
    method: "POST",
    body: form,
  });
  qs("#upload-status").textContent = `${result.total} file${result.total === 1 ? "" : "s"} uploaded`;
  toast(`Uploaded ${result.total} file${result.total === 1 ? "" : "s"}.`);
  await refreshBootstrap();
}

function updateIndexStatus(status) {
  if (!status) {
    return;
  }
  const wrap = qs("#index-progress-wrap");
  const fill = qs("#index-progress-fill");
  const text = qs("#index-progress-text");
  const percent = status.total ? Math.round((status.done / status.total) * 100) : 0;
  fill.style.width = `${percent}%`;
  text.textContent = status.message || "Ready";
  if (status.status === "indexing" || status.status === "loading") {
    wrap.classList.remove("hidden");
    setStatus("busy", `${status.dataset || "Dataset"} · ${status.message}`);
    window.clearTimeout(state.indexPoller);
    state.indexPoller = window.setTimeout(pollIndexStatus, 1200);
  } else if (status.status === "ready") {
    wrap.classList.remove("hidden");
  } else {
    wrap.classList.add("hidden");
  }
}

async function pollIndexStatus() {
  const status = await api("/api/index/status");
  state.activeDataset = status.loaded_dataset || state.activeDataset;
  renderDatasets();
  updateIndexStatus(status);
  if (status.status === "ready") {
    await refreshBootstrap();
  }
}

async function buildIndex() {
  if (!state.activeDataset) {
    throw new Error("Select a production first.");
  }
  await api(`/api/datasets/${encodeURIComponent(state.activeDataset)}/index/build`, { method: "POST" });
  qs("#upload-status").textContent = `Building index for ${state.activeDataset}...`;
  updateIndexStatus({ status: "indexing", dataset: state.activeDataset, done: 0, total: 1, message: "Preparing index..." });
}

async function loadIndex(name) {
  await api(`/api/datasets/${encodeURIComponent(name)}/index/load`, { method: "POST" });
  state.activeDataset = name;
  updateIndexStatus({ status: "loading", dataset: name, done: 0, total: 0, message: "Loading dataset..." });
}

function openPreview(dataset, filename, page, label) {
  const drawer = qs("#preview-drawer");
  qs("#preview-title").textContent = filename.split("/").pop();
  qs("#preview-meta").textContent = `${dataset} · ${label || filename}${page ? ` · Page ${page}` : ""}`;
  qs("#preview-frame").src = `/api/preview/${encodeURIComponent(dataset)}/${filename.split("/").map(encodeURIComponent).join("/")}${page ? `#page=${page}` : ""}`;
  drawer.classList.remove("hidden");
}

function closePreview() {
  qs("#preview-drawer").classList.add("hidden");
  qs("#preview-frame").src = "about:blank";
}

function makeGroup({ title, pill, meta, caret = "▶" }) {
  const group = document.createElement("article");
  group.className = "result-group";
  group.innerHTML = `
    <div class="result-group-header">
      <div class="result-group-title">${esc(title)}</div>
      ${meta ? `<div>${meta}</div>` : `<div></div>`}
      ${pill ? `<div class="result-pill">${esc(pill)}</div>` : `<div></div>`}
      <div class="result-caret">${caret}</div>
    </div>
    <div class="result-group-body"></div>
  `;
  group.querySelector(".result-group-header").addEventListener("click", () => group.classList.toggle("open"));
  return group;
}

function renderIndexResults() {
  const host = qs("#index-results");
  const terms = Object.keys(state.indexResults);
  if (!terms.length) {
    host.innerHTML = `<div class="empty-state"><div class="empty-state-mark"></div><p>Load or build an index to begin searching.</p></div>`;
    return;
  }
  host.innerHTML = "";
  for (const term of terms) {
    const payload = state.indexResults[term];
    const group = makeGroup({
      title: term,
      pill: `${payload.total_hits || 0} chunks`,
    });
    const body = group.querySelector(".result-group-body");
    if ((payload.documents || []).length) {
      body.innerHTML = `
        <div class="result-table-head">
          <div></div>
          <div>Document</div>
          <div>Matching Pages / Chunks</div>
          <div>#</div>
        </div>
        ${payload.documents.map((document) => `
          <div class="result-row">
            <div></div>
            <div>
              <div class="doc-title">${esc(document.title)}</div>
              <div class="doc-title-subtle">${esc(document.name)}</div>
            </div>
            <div class="chip-grid">
              ${document.matches.map((match) => `<button class="chip-button" data-preview-file="${esc(document.name)}" data-preview-page="${match.page || ""}" data-preview-label="${esc(match.label)}">${esc(match.label)}</button>`).join("")}
            </div>
            <div class="row-count">${document.match_count}</div>
          </div>
        `).join("")}
      `;
      group.classList.add("open");
    } else {
      body.innerHTML = `<div class="finding-row"><div class="doc-title">No matches</div></div>`;
      group.classList.add("open");
    }
    host.appendChild(group);
  }
  bindPreviewButtons(host, state.activeDataset);
}

async function runIndexSearch() {
  const terms = readTerms("#index-terms");
  if (!terms.length) {
    throw new Error("Add at least one search term.");
  }
  const payload = await api("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ terms }),
  });
  state.indexResults = payload.results;
  renderIndexResults();
}

async function exportIndexReport(format) {
  const blob = await api("/api/exports/hit-report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset: state.activeDataset, results: state.indexResults, format }),
  });
  downloadBlob(blob, format === "pdf" ? "strata_hit_report.pdf" : "strata_hit_report.xlsx");
}

function renderProductionResults() {
  const host = qs("#production-results");
  const terms = Object.keys(state.productionResults);
  if (!terms.length) {
    host.innerHTML = `<div class="empty-state"><div class="empty-state-mark"></div><p>Run a production search to select responsive documents.</p></div>`;
    return;
  }
  host.innerHTML = "";
  for (const term of terms) {
    const payload = state.productionResults[term];
    const docs = payload.documents || [];
    const selected = docs.filter((document) => state.productionSelections[`${term}::${document.name}`]).length;
    const group = makeGroup({
      title: term,
      pill: `${payload.document_count || 0} doc${payload.document_count === 1 ? "" : "s"}`,
      meta: `
        <div class="selection-column">
          <label class="select-all" data-select-all-wrap="${esc(term)}">
            <input type="checkbox" data-select-all="${esc(term)}">
            <span>Select all</span>
          </label>
        </div>
      `,
      caret: "▼",
    });
    const body = group.querySelector(".result-group-body");
    if (docs.length) {
      body.innerHTML = `
        <div class="result-table-head">
          <div></div>
          <div>Document</div>
          <div>Matching Pages / Chunks</div>
          <div>#</div>
        </div>
        ${docs.map((document) => `
          <div class="result-row">
            <div><input class="doc-check" type="checkbox" data-selection-key="${esc(`${term}::${document.name}`)}" ${state.productionSelections[`${term}::${document.name}`] ? "checked" : ""}></div>
            <div>
              <div class="doc-title">${esc(document.title)}</div>
              <div class="doc-title-subtle">${esc(document.name)}</div>
            </div>
            <div class="chip-grid">
              ${document.matches.map((match) => `<button class="chip-button" data-preview-file="${esc(document.name)}" data-preview-page="${match.page || ""}" data-preview-label="${esc(match.label)}">${esc(match.label)}</button>`).join("")}
            </div>
            <div class="row-count">${document.match_count}</div>
          </div>
        `).join("")}
      `;
      group.classList.add("open");
    } else {
      body.innerHTML = `<div class="finding-row"><div class="doc-title">No matches</div></div>`;
      group.classList.add("open");
    }
    host.appendChild(group);

    const selectAll = group.querySelector("[data-select-all]");
    if (selectAll) {
      selectAll.checked = docs.length > 0 && docs.every((document) => state.productionSelections[`${term}::${document.name}`]);
    }
    if (selected && group.querySelector(".result-pill")) {
      group.querySelector(".result-pill").textContent = `${selected} selected`;
    }
  }

  qsa("[data-selection-key]", host).forEach((input) => input.addEventListener("change", () => {
    state.productionSelections[input.dataset.selectionKey] = input.checked;
    renderProductionResults();
  }));

  qsa("[data-select-all]", host).forEach((input) => input.addEventListener("change", () => {
    const term = input.dataset.selectAll;
    const docs = state.productionResults[term]?.documents || [];
    docs.forEach((document) => {
      state.productionSelections[`${term}::${document.name}`] = input.checked;
    });
    renderProductionResults();
  }));

  bindPreviewButtons(host, qs("#production-dataset").value || state.activeDataset);
}

async function runProductionSearch() {
  const dataset = qs("#production-dataset").value;
  const terms = readTerms("#production-terms");
  if (!dataset) {
    throw new Error("Choose a dataset.");
  }
  if (!terms.length) {
    throw new Error("Add at least one search term.");
  }
  const payload = await api("/api/production/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset, terms }),
  });
  state.productionResults = payload.results;
  renderProductionResults();
}

function collectProductionSelections() {
  const selections = [];
  for (const [term, payload] of Object.entries(state.productionResults)) {
    for (const document of payload.documents || []) {
      if (state.productionSelections[`${term}::${document.name}`]) {
        selections.push({
          term,
          name: document.name,
          labels: document.matches.map((match) => match.label),
          selected: true,
        });
      }
    }
  }
  return selections;
}

async function exportProduction() {
  const dataset = qs("#production-dataset").value;
  const selections = collectProductionSelections();
  if (!selections.length) {
    throw new Error("Select at least one document.");
  }
  const blob = await api("/api/production/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset, selections }),
  });
  downloadBlob(blob, "strata_production.zip");
}

function updateRedactionStatus(status) {
  if (!status) {
    return;
  }
  const wrap = qs("#redaction-progress-wrap");
  const fill = qs("#redaction-progress-fill");
  const text = qs("#redaction-progress-text");
  const percent = status.total ? Math.round((status.done / status.total) * 100) : 0;
  fill.style.width = `${percent}%`;
  text.textContent = status.message || "Ready";
  if (status.status === "running") {
    wrap.classList.remove("hidden");
    setStatus("warn", `${status.dataset || "Dataset"} · ${status.message}`);
    window.clearTimeout(state.redactionPoller);
    state.redactionPoller = window.setTimeout(pollRedactionStatus, 1300);
  } else if (status.status === "done" || status.status === "cancelled") {
    wrap.classList.remove("hidden");
  } else {
    wrap.classList.add("hidden");
  }
}

async function pollRedactionStatus() {
  const status = await api("/api/redactions/status");
  updateRedactionStatus(status);
  const payload = await api("/api/redactions/results");
  state.redactionResults = payload.results;
  renderRedactionSummary(payload.summary);
  renderRedactionResults();
}

function renderRedactionSummary(summary) {
  const host = qs("#redaction-summary");
  const safe = summary || { files_scanned: 0, with_redactions: 0, total_findings: 0, clean_files: 0 };
  host.innerHTML = `
    <div class="stat-box">
      <div class="stat-number orange">${safe.files_scanned}</div>
      <div class="stat-label">Files Scanned</div>
    </div>
    <div class="stat-box">
      <div class="stat-number orange">${safe.with_redactions}</div>
      <div class="stat-label">With Redactions</div>
    </div>
    <div class="stat-box">
      <div class="stat-number blue">${safe.total_findings}</div>
      <div class="stat-label">Total Findings</div>
    </div>
    <div class="stat-box">
      <div class="stat-number green">${safe.clean_files}</div>
      <div class="stat-label">Clean Files</div>
    </div>
  `;
  qs("#redaction-header-copy").textContent = `Showing ${safe.with_redactions} documents with redactions`;
}

function renderRedactionResults() {
  const host = qs("#redaction-results");
  if (!state.redactionResults.length) {
    host.innerHTML = `<div class="empty-state"><div class="empty-state-mark"></div><p>No documents found in this dataset.</p></div>`;
    return;
  }
  host.innerHTML = "";
  state.redactionResults.forEach((result) => {
    const pages = (result.pages || []).map((page) => `p.${page}`).join(", ");
    const group = makeGroup({
      title: result.filename,
      pill: `${result.finding_count} findings`,
      meta: `<div class="finding-meta">${Object.entries(result.finding_types || {}).map(([key, count]) => `<span class="finding-tag">${esc(key)} · ${count}</span>`).join("")}</div>`,
      caret: "▼",
    });
    group.classList.add("open");
    group.querySelector(".result-group-body").innerHTML = `
      <div class="finding-row">
        <div class="doc-title-subtle">${pages || "document-level findings"}</div>
      </div>
      ${result.findings.map((finding) => `
        <div class="finding-row">
          <div class="doc-title">${esc(finding.type)}</div>
          <div class="doc-title-subtle">${finding.page ? `Page ${finding.page}` : "Document"}</div>
          <div class="micro-status">${esc(finding.details)}</div>
        </div>
      `).join("")}
    `;
    host.appendChild(group);
  });
}

async function startRedactionScan() {
  const dataset = qs("#redaction-dataset").value;
  if (!dataset) {
    throw new Error("Choose a dataset.");
  }
  const options = {};
  qsa("[data-redaction-option]").forEach((input) => {
    options[input.dataset.redactionOption] = input.checked;
  });
  await api("/api/redactions/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset, options }),
  });
  updateRedactionStatus({ status: "running", dataset, done: 0, total: 1, message: "Starting scan..." });
}

async function cancelRedactionScan() {
  await api("/api/redactions/cancel", { method: "POST" });
  toast("Redaction scan cancellation requested.");
}

async function exportRedaction(format) {
  const blob = await api("/api/redactions/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ format }),
  });
  const fileName = {
    "zip": "strata_redacted_docs.zip",
    "findings-xlsx": "strata_redaction_findings.xlsx",
    "summary-xlsx": "strata_redaction_summary.xlsx",
    "pdf": "strata_redaction_report.pdf",
  }[format];
  downloadBlob(blob, fileName);
}

function downloadBlob(blob, fileName) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}

function bindPreviewButtons(root, dataset) {
  qsa("[data-preview-file]", root).forEach((button) => button.addEventListener("click", (event) => {
    event.stopPropagation();
    openPreview(dataset, button.dataset.previewFile, button.dataset.previewPage, button.dataset.previewLabel);
  }));
}

function switchTab(tabName) {
  state.activeTab = tabName;
  qsa(".primary-tab").forEach((button) => button.classList.toggle("is-active", button.dataset.tab === tabName));
  qsa(".panel-view").forEach((panel) => panel.classList.toggle("panel-view-active", panel.dataset.panel === tabName));
  closePreview();
  if (tabName === "index") {
    updateHeaderDataset();
  }
}

function bindHelp() {
  qs("#help-button").addEventListener("click", () => qs("#help-modal").classList.remove("hidden"));
  qs("#help-close").addEventListener("click", () => qs("#help-modal").classList.add("hidden"));
  qs("#help-modal").addEventListener("click", (event) => {
    if (event.target.id === "help-modal") {
      qs("#help-modal").classList.add("hidden");
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      qs("#help-modal").classList.add("hidden");
      closePreview();
    }
  });
  qsa(".help-tab").forEach((button) => button.addEventListener("click", () => {
    qsa(".help-tab").forEach((tab) => tab.classList.toggle("active", tab === button));
    qsa(".help-panel").forEach((panel) => panel.classList.toggle("active", panel.dataset.helpPanel === button.dataset.help));
  }));
}

function bindUi() {
  bindHelp();
  qsa(".primary-tab").forEach((button) => button.addEventListener("click", () => switchTab(button.dataset.tab)));
  qs("#create-dataset").addEventListener("click", () => handleAction(createDataset));
  qs("#dataset-name").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      handleAction(createDataset);
    }
  });
  qs("#file-input").addEventListener("change", (event) => handleAction(() => uploadFiles(event.target.files)));
  qs("#folder-input").addEventListener("change", (event) => handleAction(() => uploadFiles(event.target.files)));
  qs("#build-index").addEventListener("click", () => handleAction(buildIndex));

  addTermRow(qs("#index-terms"));
  addTermRow(qs("#production-terms"));

  qs("#index-add-term").addEventListener("click", () => addTermRow(qs("#index-terms")));
  qs("#production-add-term").addEventListener("click", () => addTermRow(qs("#production-terms")));
  qs("#index-clear-terms").addEventListener("click", () => resetTerms(qs("#index-terms")));
  qs("#production-clear-terms").addEventListener("click", () => resetTerms(qs("#production-terms")));

  qs("#index-search").addEventListener("click", () => handleAction(runIndexSearch));
  qs("#production-search").addEventListener("click", () => handleAction(runProductionSearch));
  qs("#export-hit-xlsx").addEventListener("click", () => handleAction(() => exportIndexReport("xlsx")));
  qs("#export-hit-pdf").addEventListener("click", () => handleAction(() => exportIndexReport("pdf")));
  qs("#production-export").addEventListener("click", () => handleAction(exportProduction));

  qs("#redaction-scan").addEventListener("click", () => handleAction(startRedactionScan));
  qs("#redaction-cancel").addEventListener("click", () => handleAction(cancelRedactionScan));
  qs("#redaction-export-zip").addEventListener("click", () => handleAction(() => exportRedaction("zip")));
  qs("#redaction-export-findings").addEventListener("click", () => handleAction(() => exportRedaction("findings-xlsx")));
  qs("#redaction-export-summary").addEventListener("click", () => handleAction(() => exportRedaction("summary-xlsx")));
  qs("#redaction-export-pdf").addEventListener("click", () => handleAction(() => exportRedaction("pdf")));

  qs("#preview-close").addEventListener("click", closePreview);
}

async function handleAction(action) {
  try {
    await action();
  } catch (error) {
    toast(error.message);
  }
}

window.addEventListener("DOMContentLoaded", async () => {
  bindUi();
  await refreshBootstrap();
});
