// Composition of the studio: load state, route between views, render the
// overview charts and the full track table, wire the pipeline, and run a
// single robust tooltip. Chart building lives in charts.js / explore.js.
import { resizeAll, draw } from "./theme.js";
import { getNum, getCat, srcLabel, measureLabel, MEASURES } from "./data.js";
import { overviewTempo, overviewEV, countsDonut, countsBar } from "./charts.js";
import { mountExplore, renderChart, renderDashboards } from "./explore.js";

let state = null;
let playlist = "";
let rows = [];
let view = "overview";
let sortKey = "seq", sortDir = 1;
let jobSig = "";
let loadSeq = 0;

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (v, d = 1) => (v == null ? null : Number(v).toFixed(d).replace(/\.0+$/, ""));
const PROV = (s) => `prov-${s}`;

function valCell(row, key, decimals = 1) {
  const r = row.resolved && row.resolved[key];
  const v = getNum(row, key);
  if (v == null) return `<span class="missing">—</span>`;
  const tag = r && r.source ? ` <i class="src-tag ${PROV(r.source)}">${esc(srcLabel(r.source))}</i>` : "";
  return `<span class="val">${esc(num(v, decimals))}${tag}</span>`;
}

const COLUMNS = [
  { key: "seq", label: "#", always: true, cls: "num sticky-l", get: (r) => r.seq, render: (r) => `<td class="num sticky-l">${r.seq}</td>` },
  { key: "title", label: "Track", always: true, cls: "sticky-l2", get: (r) => r.title.toLowerCase(),
    render: (r) => `<td class="sticky-l2"><div class="t-title">${esc(r.title)}</div><div class="t-artist">${esc((r.artists || []).join(", "))}</div></td>` },
  { key: "tempo", label: "Tempo", get: (r) => getNum(r, "tempo"), render: (r) => `<td class="num">${valCell(r, "tempo")}</td>` },
  { key: "felt_tempo", label: "Felt", get: (r) => getNum(r, "felt_tempo"), render: (r) => `<td class="num">${valCell(r, "felt_tempo")}</td>` },
  { key: "tempo_variability", label: "Tempo σ", get: (r) => getNum(r, "tempo_variability"), render: (r) => `<td class="num">${valCell(r, "tempo_variability")}</td>` },
  { key: "tempo_min", label: "Tempo min", def: false, get: (r) => getNum(r, "tempo_min"), render: (r) => `<td class="num">${valCell(r, "tempo_min")}</td>` },
  { key: "tempo_max", label: "Tempo max", def: false, get: (r) => getNum(r, "tempo_max"), render: (r) => `<td class="num">${valCell(r, "tempo_max")}</td>` },
  { key: "section_count", label: "Sections", get: (r) => getNum(r, "section_count"), render: (r) => `<td class="num">${valCell(r, "section_count", 0)}</td>` },
  { key: "loop_score", label: "Loop score", get: (r) => getNum(r, "loop_score"), render: (r) => `<td class="num">${valCell(r, "loop_score", 2)}</td>` },
  { key: "structure", label: "Loop/line", get: (r) => getCat(r, "structure"),
    render: (r) => { const v = r.resolved.structure ? r.resolved.structure.value : null; return `<td>${v ? `<span class="pill ${esc(v)}">${esc(v)}</span>` : `<span class="missing">—</span>`}</td>`; } },
  { key: "energy", label: "Energy", get: (r) => getNum(r, "energy"), render: (r) => `<td class="num">${valCell(r, "energy", 2)}</td>` },
  { key: "valence", label: "Valence", get: (r) => getNum(r, "valence"), render: (r) => `<td class="num">${valCell(r, "valence", 2)}</td>` },
  { key: "danceability", label: "Dance", def: false, get: (r) => getNum(r, "danceability"), render: (r) => `<td class="num">${valCell(r, "danceability", 2)}</td>` },
  { key: "acousticness", label: "Acoustic", def: false, get: (r) => getNum(r, "acousticness"), render: (r) => `<td class="num">${valCell(r, "acousticness", 2)}</td>` },
  { key: "instrumentalness", label: "Instr.", def: false, get: (r) => getNum(r, "instrumentalness"), render: (r) => `<td class="num">${valCell(r, "instrumentalness", 2)}</td>` },
  { key: "liveness", label: "Live", def: false, get: (r) => getNum(r, "liveness"), render: (r) => `<td class="num">${valCell(r, "liveness", 2)}</td>` },
  { key: "speechiness", label: "Speech", def: false, get: (r) => getNum(r, "speechiness"), render: (r) => `<td class="num">${valCell(r, "speechiness", 2)}</td>` },
  { key: "loudness", label: "Loudness", def: false, get: (r) => getNum(r, "loudness"), render: (r) => `<td class="num">${valCell(r, "loudness", 1)}</td>` },
  { key: "key", label: "Key", def: false, get: (r) => getCat(r, "key"), render: (r) => `<td>${esc(getCat(r, "key"))}</td>` },
  { key: "mode", label: "Mode", def: false, get: (r) => getCat(r, "mode"), render: (r) => `<td>${esc(getCat(r, "mode"))}</td>` },
  { key: "time_signature", label: "Time sig", def: false, get: (r) => getCat(r, "time_signature"), render: (r) => `<td>${esc(getCat(r, "time_signature"))}</td>` },
  { key: "confidence", label: "Download", get: (r) => r.asset_confidence || "", render: (r) => `<td><span class="pill ${esc(r.asset_confidence || "none")}">${esc(r.asset_confidence || "—")}</span></td>` },
  { key: "lyrics", label: "Lyrics", get: (r) => r.lyrics_status || "", render: (r) => `<td><span class="pill ${r.lyrics_status === "present" ? "high" : r.lyrics_status === "instrumental" ? "override" : "none"}">${esc(r.lyrics_status || "—")}</span></td>` },
  { key: "stems", label: "Stems", get: (r) => Object.keys(r.stems || {}).length, render: (r) => { const n = Object.keys(r.stems || {}).length; return `<td class="num">${n ? n : `<span class="missing">—</span>`}</td>`; } },
  { key: "source", label: "Source", def: false, get: (r) => r.asset_source || "", render: (r) => `<td>${r.asset_source ? `<span class="src-tag ${PROV(r.asset_source)}">${esc(srcLabel(r.asset_source))}</span>` : `<span class="missing">—</span>`}</td>` },
];
function defaultCols() { return COLUMNS.filter((c) => c.always || c.def !== false).map((c) => c.key); }
function loadCols() { try { const v = JSON.parse(localStorage.getItem("cantabile.cols")); return Array.isArray(v) && v.length ? v : defaultCols(); } catch { return defaultCols(); } }
let visibleCols = loadCols();

/* ───────── boot / state ───────── */
async function loadState(pl = playlist) {
  const seq = ++loadSeq;
  const prevJobs = (state && state.jobs) || [];
  const res = await fetch(`/api/state?playlist=${encodeURIComponent(pl || "")}`);
  const data = await res.json();
  if (seq !== loadSeq) return;                 // a newer load superseded this one
  state = data;
  state.jobs = prevJobs;                       // /api/state carries no jobs; keep what the poll has
  playlist = state.selected || "";
  if (playlist) { try { localStorage.setItem("cantabile.playlist", playlist); } catch (_) {} }
  rows = state.report ? state.report.tracks : [];
  renderTopbar();
  renderView(view);
  renderJobs(state.jobs);
}

function renderTopbar() {
  const sel = $("#playlist-select");
  const pls = state.playlists || [];
  sel.innerHTML = pls.length ? pls.map((p) => `<option value="${esc(p.name)}" ${p.name === playlist ? "selected" : ""}>${esc(p.name)}</option>`).join("")
    : `<option>no playlists — import a CSV</option>`;
  $("#db-count").textContent = `${pls.length} playlist${pls.length === 1 ? "" : "s"}`;
  const s = state.report ? state.report.summary : null;
  $("#kpis").innerHTML = s ? [
    kpi("Tracks", s.total_tracks, s.total_tracks),
    kpi("Audio", s.audio_assets, s.total_tracks),
    kpi("MIR", s.mir_tracks, s.total_tracks),
    kpi("Lyrics", s.lyrics_tracks, s.total_tracks),
    kpi("Stems", s.stemmed_tracks, s.total_tracks),
  ].join("") : "";
  $$("form[data-action] button, #pin-btn").forEach((b) => { b.disabled = !playlist; });
}
function kpi(lab, val, total) {
  const pct = total ? Math.round((val / total) * 100) : 0;
  return `<div class="kpi"><span class="k-val">${val ?? 0}</span><span class="k-lab">${lab}</span><span class="k-sub">${pct}%</span></div>`;
}

/* ───────── routing ───────── */
function setView(v) {
  view = v;
  $$(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === v));
  $$(".view").forEach((s) => s.classList.toggle("active", s.dataset.view === v));
  requestAnimationFrame(() => { resizeAll(); renderView(v); });
}
function renderView(v) {
  if (!state) return;
  if (v === "overview") renderOverview();
  else if (v === "tracks") renderTracks();
  else if (v === "explore") renderChart();
  else if (v === "dashboard") renderDashboards();
  else if (v === "pipeline") renderPipeline();
}

/* ───────── overview ───────── */
function renderOverview() {
  $("#ov-title").textContent = playlist || "Overview";
  const s = state.report ? state.report.summary : null;
  if (!s) { $("#ov-stats").innerHTML = ""; return; }
  const stat = (lab, val, total, sub) => {
    const pct = total ? Math.round((val / total) * 100) : 0;
    return `<div class="panel stat-card"><div class="s-lab">${lab}</div><div class="s-val">${val}</div>
      <div class="s-bar"><i style="width:${pct}%"></i></div><div class="s-sub">${sub || pct + "% of playlist"}</div></div>`;
  };
  $("#ov-stats").innerHTML =
    stat("Tracks", s.total_tracks, s.total_tracks, `${s.missing_tracks} missing`)
    + stat("Downloaded", s.audio_assets, s.total_tracks)
    + stat("Analyzed (MIR)", s.mir_tracks, s.total_tracks)
    + stat("Stemmed", s.stemmed_tracks, s.total_tracks);
  draw($("#ov-tempo"), overviewTempo(rows));
  draw($("#ov-ev"), overviewEV(rows));
  draw($("#ov-structure"), countsDonut(s.structure_counts));
  draw($("#ov-temposrc"), countsBar(s.tempo_source_counts, "tracks", true));
  draw($("#ov-prov"), countsBar(s.provenance_counts, "facts", true));
  draw($("#ov-conf"), countsBar(s.confidence_counts, "tracks", false));
}

/* ───────── pipeline (job builder) ───────── */
const NODE_IC = {
  import: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
  fetch: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>',
  lyrics: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
  separate: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>',
  mir: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8"><polyline points="2 12 5 12 8 4 12 20 16 9 19 12 22 12"/></svg>',
  export: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
};
const NW = 210, NH = 86;
const NODES = [
  { id: "import", label: "Import", sub: "CSV \u2192 store", x: 24, y: 188, deps: [], chain: false, special: "import",
    covered: (s) => s.total_tracks, total: (s) => s.total_tracks, gate: () => null,
    desc: "Bring a playlist in from an Exportify CSV. Tracks, order, and Spotify features land in the database.", fields: [] },
  { id: "fetch", label: "Acquire audio", sub: "/api/fetch", api: "/api/fetch", x: 290, y: 70, deps: ["import"], chain: true,
    covered: (s) => s.audio_assets, total: (s) => s.total_tracks, gate: (s) => (s.total_tracks ? null : "Import a playlist first"),
    desc: "Find and download the real recording for each track, matched by duration.",
    fields: [ { name: "dry_run", type: "check", label: "Preview only (no download)", def: true },
      { name: "no_suggest", type: "check", label: "Skip alternate-source suggestions" },
      { name: "overrides_text", type: "textarea", label: "Manual pins (seq,url per line)" } ] },
  { id: "lyrics", label: "Lyrics", sub: "/api/lyrics", api: "/api/lyrics", x: 290, y: 306, deps: ["import"], chain: true,
    covered: (s) => s.lyrics_tracks, total: (s) => s.total_tracks, gate: (s) => (s.total_tracks ? null : "Import a playlist first"),
    desc: "Look up lyrics (LRCLIB first, Genius fallback) and mark instrumentals.",
    fields: [ { name: "force", type: "check", label: "Force re-lookup" } ] },
  { id: "separate", label: "Separate stems", sub: "/api/separate", api: "/api/separate", x: 556, y: 70, deps: ["fetch"], chain: false,
    covered: (s) => s.stemmed_tracks, total: (s) => s.total_tracks, gate: (s) => (s.audio_assets ? null : "Needs downloaded audio"),
    desc: "Split into drums, bass, vocals, other (Demucs). Heavy on CPU; off by default in a full run.",
    fields: [ { name: "model", type: "text", label: "Model", ph: "htdemucs" }, { name: "segment", type: "text", label: "Segment", ph: "7.0" },
      { name: "two_stems", type: "text", label: "Two-stems", ph: "vocals" }, { name: "out", type: "text", label: "Output dir" },
      { name: "force", type: "check", label: "Force re-separate" } ] },
  { id: "mir", label: "MIR analyze", sub: "/api/mir", api: "/api/mir", x: 822, y: 188, deps: ["fetch", "separate"], chain: true,
    covered: (s) => s.mir_tracks, total: (s) => s.total_tracks, gate: (s) => (s.audio_assets ? null : "Needs downloaded audio"),
    desc: "Measure felt tempo, variability, sections, loop/line. Reads the drum stem if separated.",
    fields: [ { name: "force", type: "check", label: "Force re-analyze" } ] },
  { id: "export", label: "Export", sub: "/api/export", api: "/api/export", x: 980, y: 306, deps: ["mir", "lyrics"], chain: true,
    covered: () => null, total: () => null, gate: (s) => (s.total_tracks ? null : "Import a playlist first"),
    desc: "Write CSV files and a standalone HTML report for this playlist.",
    fields: [ { name: "out", type: "text", label: "Reports dir" } ] },
];
const ENHANCE = new Set(["separate>mir"]);
const nodeById = Object.fromEntries(NODES.map((n) => [n.id, n]));
const nodeValues = {};
NODES.forEach((n) => { nodeValues[n.id] = {}; n.fields.forEach((f) => { nodeValues[n.id][f.name] = f.def || (f.type === "check" ? false : ""); }); });
const includeSet = new Set(["fetch", "lyrics", "mir", "export"]);
let selectedNode = null;
let chainRunning = false;

function pSummary() { return state && state.report ? state.report.summary : null; }
function jobsFor(key) { return (state.jobs || []).filter((j) => j.action === key && j.playlist === playlist); }
function isRunning(key) { return jobsFor(key).some((j) => j.status === "queued" || j.status === "running"); }
function nodeState(n, s) {
  if (isRunning(n.id)) return "running";
  const c = n.covered(s), t = n.total(s);
  if (c == null) return "available";
  if (t > 0 && c >= t) return "done";
  if (c > 0) return "partial";
  return "todo";
}

function renderPipeline() {
  const s = pSummary();
  const flow = $("#flow");
  if (!flow) return;
  if (!s) { flow.innerHTML = `<p class="missing" style="padding:16px">Import a playlist to begin building.</p>`; renderInspector(); return; }
  const states = {}; NODES.forEach((n) => { states[n.id] = nodeState(n, s); });
  const next = NODES.find((n) => n.chain && ["todo", "partial"].includes(states[n.id]) && !n.gate(s));

  let edges = "";
  for (const n of NODES) {
    for (const dep of n.deps) {
      const a = nodeById[dep];
      const ax = a.x + NW, ay = a.y + NH / 2, bx = n.x, by = n.y + NH / 2;
      const dx = Math.max(40, (bx - ax) / 2);
      const cls = ["edge", ENHANCE.has(`${dep}>${n.id}`) ? "enhance" : "",
        states[dep] === "done" ? "done" : "", states[n.id] === "running" ? "flowing" : ""].filter(Boolean).join(" ");
      edges += `<path class="${cls}" d="M ${ax} ${ay} C ${ax + dx} ${ay}, ${bx - dx} ${by}, ${bx} ${by}"/>`;
    }
  }
  let nodes = "";
  for (const n of NODES) {
    const st = states[n.id], gate = n.gate(s), cov = n.covered(s), tot = n.total(s);
    const cls = ["node", st, selectedNode === n.id ? "selected" : "", n === next ? "next" : "", gate ? "locked" : ""].filter(Boolean).join(" ");
    const cover = cov == null ? "ready" : `${cov}/${tot}`;
    const lbl = st === "available" ? "ready" : st;
    const toggle = n.chain ? `<div class="node-toggle ${includeSet.has(n.id) ? "on" : ""}" data-toggle="${n.id}" title="Include in Run pipeline"><svg viewBox="0 0 24 24" fill="none" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg></div>` : "";
    nodes += `<div class="${cls}" data-node="${n.id}" style="left:${n.x}px;top:${n.y}px">
      ${toggle}
      <div class="node-head"><div class="node-ic">${NODE_IC[n.id]}</div><div><div class="nt">${n.label}</div><div class="ns">${n.sub}</div></div></div>
      <div class="node-body"><span class="node-cov">${cover}</span><span class="node-state ${lbl}">${lbl}</span></div>
    </div>`;
  }
  flow.innerHTML = `<svg class="edges" viewBox="0 0 1200 460" preserveAspectRatio="none">${edges}</svg>${nodes}`;
  flow.querySelectorAll("[data-node]").forEach((el) => el.addEventListener("click", (e) => {
    if (panMoved) return;
    if (e.target.closest("[data-toggle]")) return; selectNode(el.dataset.node);
  }));
  flow.querySelectorAll("[data-toggle]").forEach((el) => el.addEventListener("click", () => {
    if (panMoved) return;
    const id = el.dataset.toggle; includeSet.has(id) ? includeSet.delete(id) : includeSet.add(id); renderPipeline();
  }));
  applyT();
  const pane = document.querySelector(".canvas-pane");
  if (pane && pane.clientWidth > 0 && lastFitPlaylist !== playlist) { fitView(); lastFitPlaylist = playlist; }

  const meas = ["fetch", "lyrics", "mir"].map((k) => nodeById[k]);
  const pct = Math.round(meas.reduce((a, n) => a + (n.total(s) ? n.covered(s) / n.total(s) : 0), 0) / meas.length * 100);
  if ($("#run-bar")) { $("#run-bar").style.width = `${pct}%`; $("#run-pct").textContent = `${pct}%`; }
  const runBtn = $("#run-pipeline"); if (runBtn) runBtn.disabled = !playlist || chainRunning;

  if (!selectedNode && next) selectedNode = next.id;
  const insp = $("#inspector");
  if (insp && !insp.contains(document.activeElement)) renderInspector();
}

function renderInspector() {
  const insp = $("#inspector"); if (!insp) return;
  const s = pSummary();
  const n = selectedNode ? nodeById[selectedNode] : null;
  if (!n || !s) { insp.innerHTML = `<div class="insp-empty">Select a step on the canvas to configure and run it.</div>`; return; }
  const st = nodeState(n, s), gate = n.gate(s), cov = n.covered(s), tot = n.total(s);
  const statLine = cov == null
    ? `<div class="insp-stat">Runs on demand.</div>`
    : `<div class="insp-stat"><span>${cov} / ${tot}</span><span class="bar"><i style="width:${tot ? Math.round(cov / tot * 100) : 0}%"></i></span></div>`;
  const gateLine = gate ? `<div class="gate"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>${esc(gate)}</div>` : "";
  let fields = "";
  if (n.special === "import") {
    fields = `<button class="btn btn-primary" id="insp-import" type="button">Choose a CSV file</button>`;
  } else {
    fields = `<div class="insp-fields">` + n.fields.map((f) => {
      const v = nodeValues[n.id][f.name];
      if (f.type === "check") return `<label class="check"><input type="checkbox" data-f="${f.name}" ${v ? "checked" : ""}> ${esc(f.label)}</label>`;
      if (f.type === "textarea") return `<label class="ctl"><span>${esc(f.label)}</span><textarea rows="2" data-f="${f.name}" placeholder="${esc(f.ph || "")}">${esc(v)}</textarea></label>`;
      return `<label class="ctl"><span>${esc(f.label)}</span><input type="text" data-f="${f.name}" value="${esc(v)}" placeholder="${esc(f.ph || "")}"></label>`;
    }).join("") + `</div>`;
    const disabled = !!gate || st === "running" || !playlist;
    fields += `<button class="btn btn-primary" id="insp-run" ${disabled ? "disabled" : ""} type="button">${st === "running" ? "Running\u2026" : "Run this step"}</button>`;
  }
  const runs = jobsFor(n.id).slice(0, 3).map((j) => {
    const line = j.error ? j.error : (j.logs && j.logs.length ? j.logs[j.logs.length - 1] : j.status);
    return `<div class="clog ${esc(j.status)}"><div class="clog-top"><strong>${esc(j.status)}</strong></div><div class="clog-line">${esc(line)}</div></div>`;
  }).join("") || `<p class="muted" style="font-size:12px">No runs yet.</p>`;

  insp.innerHTML = `<div class="insp-head"><h3>${n.label}</h3><p>${esc(n.desc)}</p></div>
    ${statLine}${gateLine}${fields}
    <div class="insp-runs"><h4>Recent runs</h4>${runs}</div>`;

  if (n.special === "import") { const b = $("#insp-import"); if (b) b.addEventListener("click", () => $("#csv-file").click()); return; }
  insp.querySelectorAll("[data-f]").forEach((el) => {
    const ev = el.type === "checkbox" ? "change" : "input";
    el.addEventListener(ev, () => { nodeValues[n.id][el.dataset.f] = el.type === "checkbox" ? el.checked : el.value; });
  });
  const rb = $("#insp-run"); if (rb) rb.addEventListener("click", () => runStep(n.id));
}

function selectNode(id) { selectedNode = id; renderPipeline(); }

async function runStep(id) {
  const n = nodeById[id]; if (!n || n.special === "import") return null;
  const fd = new FormData(); fd.set("playlist", playlist);
  for (const f of n.fields) {
    const v = nodeValues[id][f.name];
    if (f.type === "check") { if (v) fd.set(f.name, "on"); }
    else if (v) fd.set(f.name, v);
  }
  const res = await fetch(n.api, { method: "POST", body: fd });
  const job = await res.json().catch(() => null);
  await loadState(playlist);
  return job;
}

async function waitForJob(id, timeoutMs = 1000 * 60 * 30) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    await new Promise((r) => setTimeout(r, 1500));
    try {
      const res = await fetch(`/api/jobs/${id}`); if (!res.ok) return;
      const j = await res.json();
      if (state) state.jobs = (state.jobs || []).map((x) => (x.id === j.id ? j : x));
      if (view === "pipeline") renderPipeline();
      if (["done", "success", "error", "failed"].includes(j.status)) return j;
    } catch { return; }
  }
}

async function runChain() {
  if (chainRunning || !playlist) return;
  chainRunning = true; renderPipeline();
  try {
    for (const id of ["fetch", "lyrics", "separate", "mir", "export"]) {
      if (!includeSet.has(id)) continue;
      const n = nodeById[id];
      if (n.gate(pSummary())) continue;
      const job = await runStep(id);
      if (job && job.id) await waitForJob(job.id);
    }
  } finally { chainRunning = false; await loadState(playlist); }
}

/* ───────── canvas pan + zoom ───────── */
let viewT = { x: 0, y: 0, k: 1 };
let panMoved = false;
let lastFitPlaylist = null;
function applyT() {
  const f = $("#flow"); if (f) f.style.transform = `translate(${viewT.x}px, ${viewT.y}px) scale(${viewT.k})`;
  const z = $("#zoom-pct"); if (z) z.textContent = `${Math.round(viewT.k * 100)}%`;
}
function clampK(k) { return Math.max(0.35, Math.min(2.5, k)); }
function zoomAt(cx, cy, factor) {
  const nk = clampK(viewT.k * factor); const r = nk / viewT.k;
  viewT.x = cx - (cx - viewT.x) * r; viewT.y = cy - (cy - viewT.y) * r; viewT.k = nk; applyT();
}
function fitView() {
  const pane = document.querySelector(".canvas-pane"); if (!pane || !pane.clientWidth) return;
  const pad = 44;
  const minX = Math.min(...NODES.map((n) => n.x)), minY = Math.min(...NODES.map((n) => n.y));
  const maxX = Math.max(...NODES.map((n) => n.x + NW)), maxY = Math.max(...NODES.map((n) => n.y + NH));
  const w = maxX - minX, h = maxY - minY;
  const k = clampK(Math.min((pane.clientWidth - pad * 2) / w, (pane.clientHeight - pad * 2) / h));
  viewT.k = k;
  viewT.x = (pane.clientWidth - w * k) / 2 - minX * k;
  viewT.y = (pane.clientHeight - h * k) / 2 - minY * k;
  applyT();
}
function setupCanvasNav() {
  const pane = document.querySelector(".canvas-pane"); if (!pane) return;
  pane.addEventListener("wheel", (e) => {
    e.preventDefault(); const r = pane.getBoundingClientRect();
    zoomAt(e.clientX - r.left, e.clientY - r.top, e.deltaY < 0 ? 1.12 : 0.892);
  }, { passive: false });
  let dragging = false, sx = 0, sy = 0, ox = 0, oy = 0, captured = false;
  pane.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    dragging = true; panMoved = false; captured = false;
    sx = e.clientX; sy = e.clientY; ox = viewT.x; oy = viewT.y;
  });
  pane.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    const dx = e.clientX - sx, dy = e.clientY - sy;
    if (!panMoved && Math.abs(dx) + Math.abs(dy) > 4) { panMoved = true; pane.classList.add("grabbing"); try { pane.setPointerCapture(e.pointerId); captured = true; } catch (_) {} }
    if (panMoved) { viewT.x = ox + dx; viewT.y = oy + dy; applyT(); }
  });
  const end = (e) => {
    dragging = false; pane.classList.remove("grabbing");
    if (captured) { try { pane.releasePointerCapture(e.pointerId); } catch (_) {} captured = false; }
    setTimeout(() => { panMoved = false; }, 0);
  };
  pane.addEventListener("pointerup", end);
  pane.addEventListener("pointercancel", end);
  const cx = () => pane.getBoundingClientRect().width / 2;
  const cy = () => pane.getBoundingClientRect().height / 2;
  document.getElementById("zoom-in")?.addEventListener("click", () => zoomAt(cx(), cy(), 1.2));
  document.getElementById("zoom-out")?.addEventListener("click", () => zoomAt(cx(), cy(), 0.83));
  document.getElementById("zoom-fit")?.addEventListener("click", fitView);
}

function activeColumns() { return COLUMNS.filter((c) => c.always || visibleCols.includes(c.key)); }
function renderTracks() {
  const cols = activeColumns();
  const arrow = (k) => (sortKey === k ? `<span class="arrow">${sortDir > 0 ? "▲" : "▼"}</span>` : "");
  $("#track-head").innerHTML = `<tr>${cols.map((c) => `<th class="${c.cls || ""}" data-sort="${c.key}">${esc(c.label)}${arrow(c.key)}</th>`).join("")}</tr>`;
  const q = ($("#track-search").value || "").trim().toLowerCase();
  let list = rows.filter((r) => !q || `${r.title} ${(r.artists || []).join(" ")}`.toLowerCase().includes(q));
  const col = COLUMNS.find((c) => c.key === sortKey);
  if (col) list = [...list].sort((a, b) => cmp(col.get(a), col.get(b)) * sortDir);
  $("#track-body").innerHTML = list.length
    ? list.map((r) => `<tr data-seq="${r.seq}">${cols.map((c) => c.render(r)).join("")}</tr>`).join("")
    : `<tr><td colspan="${cols.length}" class="missing" style="padding:24px;text-align:center">No matching tracks</td></tr>`;
  $("#track-count").textContent = `${list.length} of ${rows.length}`;
  $$("#track-head th").forEach((th) => th.addEventListener("click", () => {
    const k = th.dataset.sort; if (sortKey === k) sortDir *= -1; else { sortKey = k; sortDir = 1; } renderTracks();
  }));
  $$("#track-body tr[data-seq]").forEach((tr) => tr.addEventListener("click", () => openDrawer(Number(tr.dataset.seq))));
}
function cmp(a, b) {
  const an = a == null || a === "", bn = b == null || b === "";
  if (an && bn) return 0; if (an) return 1; if (bn) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b));
}
function renderColsMenu() {
  const pop = $("#cols-pop");
  pop.innerHTML = COLUMNS.filter((c) => !c.always).map((c) =>
    `<label><input type="checkbox" data-col="${c.key}" ${visibleCols.includes(c.key) ? "checked" : ""}> ${esc(c.label)}</label>`).join("");
  pop.querySelectorAll("input").forEach((cb) => cb.addEventListener("change", () => {
    const k = cb.dataset.col;
    if (cb.checked) visibleCols.push(k); else visibleCols = visibleCols.filter((x) => x !== k);
    localStorage.setItem("cantabile.cols", JSON.stringify(visibleCols));
    renderTracks();
  }));
}

/* ───────── detail drawer ───────── */
async function openDrawer(seq) {
  const drawer = $("#drawer"), scrim = $("#scrim");
  drawer.classList.add("open"); scrim.classList.add("open"); drawer.setAttribute("aria-hidden", "false");
  drawer.innerHTML = `<div class="drawer-body" style="align-items:center;justify-content:center"><div class="spinner"></div></div>`;
  try {
    const res = await fetch(`/api/track?playlist=${encodeURIComponent(playlist)}&seq=${seq}`);
    if (!res.ok) throw new Error("not found");
    drawer.innerHTML = drawerHtml(await res.json());
    $("#drawer-close").addEventListener("click", closeDrawer);
  } catch { drawer.innerHTML = `<div class="drawer-body"><p class="missing">Could not load track detail.</p></div>`; }
}
function closeDrawer() { $("#drawer").classList.remove("open"); $("#scrim").classList.remove("open"); $("#drawer").setAttribute("aria-hidden", "true"); }

function drawerHtml(t) {
  const meta = [t.album, t.release_date].filter(Boolean).join(" · ");
  const resolvedKeys = MEASURES.map((m) => m.key).filter((k) => !["__count__", "duration_min", "seq"].includes(k) && t.resolved && t.resolved[k]);
  const resolved = resolvedKeys.map((k) => {
    const r = t.resolved[k];
    return `<div class="obs-row"><div class="of">${esc(measureLabel(k))}</div>
      <div class="ov ${PROV(r.source)}">${esc(r.value)} <span class="src-tag">${esc(srcLabel(r.source))}</span></div></div>`;
  }).join("") || `<p class="missing">No resolved features yet.</p>`;

  const obs = (t.observations || []).map((o) => {
    const v = typeof o.value === "string" && o.value.length > 60 ? o.value.slice(0, 60) + "…" : o.value;
    return `<div class="obs-row"><div class="of">${esc(o.feature)} <span class="src-tag ${PROV(o.source)}">${esc(srcLabel(o.source))}</span></div>
      <div class="ov">${esc(v)}</div>
      <div class="om">${esc(o.confidence)}${o.analyzer_version ? " · " + esc(o.analyzer_version) : ""}${o.unit ? " · " + esc(o.unit) : ""}</div></div>`;
  }).join("") || `<p class="missing">No observations.</p>`;

  const lyricsObs = (t.observations || []).find((o) => o.feature === "lyrics");
  const lyricsText = lyricsObs && typeof lyricsObs.value === "string" && lyricsObs.value !== "[instrumental]" ? lyricsObs.value : "";
  const lyrics = `<div class="dsec"><h4>Lyrics — ${esc(t.lyrics_status || "missing")}</h4>${lyricsText ? `<div class="lyrics-box">${esc(lyricsText)}</div>` : `<p class="missing">No lyrics stored.</p>`}</div>`;

  const stemNames = Object.keys(t.stems || {});
  const stems = `<div class="dsec"><h4>Stems</h4>${stemNames.length
    ? `<div class="stems-row">${stemNames.map((s) => `<span class="stem-tag">${esc(s)}</span>`).join("")}</div>`
    : `<p class="missing">Not separated.</p>`}</div>`;

  const audio = `<div class="dsec"><h4>Audio source</h4>${t.has_audio ? `<div class="obs-row"><div class="of">confidence</div><div class="ov"><span class="pill ${esc(t.asset_confidence || "none")}">${esc(t.asset_confidence || "—")}</span></div></div>
    <div class="obs-row"><div class="of">source</div><div class="ov">${esc(srcLabel(t.asset_source))}</div></div>
    ${t.asset_duration_sec != null ? `<div class="obs-row"><div class="of">duration</div><div class="ov">${esc(Number(t.asset_duration_sec).toFixed(1))} s</div></div>` : ""}
    ${t.asset_url ? `<div class="obs-row"><div class="of">link</div><div class="ov"><a href="${esc(t.asset_url)}" target="_blank" rel="noreferrer">open</a></div></div>` : ""}`
    : `<p class="missing">No audio downloaded.</p>`}</div>`;

  return `<div class="drawer-head">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
        <div><span class="seq">#${t.seq}</span><h2>${esc(t.title)}</h2><div class="sub">${esc((t.artists || []).join(", "))}${meta ? " · " + esc(meta) : ""}</div></div>
        <button class="icon-btn" id="drawer-close" title="Close"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
      </div>
    </div>
    <div class="drawer-body">
      <div class="dsec"><h4>Resolved facts (trusted value · source)</h4>${resolved}</div>
      ${audio}${stems}${lyrics}
      <div class="dsec"><h4>All observations (${(t.observations || []).length})</h4>${obs}</div>
    </div>`;
}

/* ───────── pipeline ───────── */
async function postForm(form, url) {
  const btn = form.querySelector("button[type='submit']");
  const data = new FormData(form);
  if (url !== "/api/import") data.set("playlist", playlist);
  if (btn) btn.disabled = true;
  try {
    const res = await fetch(url, { method: "POST", body: data });
    if (!res.ok) throw new Error(await res.text());
    await res.json();
    await loadState(playlist);
  } catch (e) {
    console.error(e);
  } finally { if (btn) btn.disabled = !playlist && url !== "/api/import"; }
}

function renderJobs(allJobs) {
  const jobs = (allJobs || []).filter((j) => !j.playlist || j.playlist === playlist);
  const cnt = $("#job-count"); if (cnt) cnt.textContent = String(jobs.length);
  const el = $("#jobs"); if (!el) return;
  if (!jobs.length) { el.innerHTML = `<p class="muted">No jobs for this playlist yet. Select a step and run it, or hit Run pipeline.</p>`; return; }
  el.innerHTML = jobs.map((job) => {
    const logs = [...(job.logs || [])].slice(-6);
    const lines = (job.error ? [job.error] : logs.length ? logs : [job.playlist || job.id]).filter(Boolean);
    const links = job.result && job.result.links ? job.result.links : {};
    const linkHtml = Object.entries(links).map(([k, href]) => `<a href="${esc(href)}" target="_blank" rel="noreferrer">${esc(linkLabel(k))}</a>`).join("");
    const preview = job.result && job.result.preview ? previewTable(job.result.preview, job.result.dry_run) : "";
    return `<div class="clog ${esc(job.status)}"><div class="clog-top"><strong>${esc(job.action)}</strong> <span class="pill ${esc(job.status)}">${esc(job.status)}</span> <span class="muted">${esc(job.playlist || "")}</span></div>
      ${lines.map((l) => `<div class="clog-line">${esc(l)}</div>`).join("")}${linkHtml ? `<div>${linkHtml}</div>` : ""}${preview}</div>`;
  }).join("");
}
function previewTable(preview, dryRun) {
  if (!preview || !preview.length) return "";
  const rows = preview.map((r) => {
    const conf = `<span class="pill ${esc(r.confidence)}">${esc(r.confidence)}</span>`;
    const off = r.delta != null ? `${r.delta}s` : "";
    let match;
    if (r.url) {
      match = `<a href="${esc(r.url)}" target="_blank" rel="noreferrer">${esc(r.url)}</a>`;
    } else {
      const sug = (r.suggestions || []).map((s) => s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noreferrer">${esc(s.label || "suggestion")}</a>` : esc(s.label || "")).join(" · ");
      match = `<span class="pv-nomatch">no match${sug ? ": " + sug : ""}</span>`;
    }
    return `<tr><td class="pv-seq">${esc(r.seq)}</td><td class="pv-title">${esc(r.title)}<span class="pv-artist">${esc(r.artist || "")}</span></td><td>${conf}</td><td class="pv-off">${esc(off)}</td><td class="pv-match">${match}</td></tr>`;
  }).join("");
  return `<table class="preview-tbl"><thead><tr><th>#</th><th>track</th><th>conf</th><th>off</th><th>${dryRun ? "would download" : "source"}</th></tr></thead><tbody>${rows}</tbody></table>`;
}
function linkLabel(k) { return { html_report: "Open report", observations_csv: "Observations CSV", tracks_csv: "Tracks CSV" }[k] || k; }

/* ───────── tooltips (single robust impl) ───────── */
const tip = $("#tooltip");
let tipTarget = null;
function showTip(target) {
  const text = target.getAttribute("data-tip"); if (!text) return;
  tipTarget = target; tip.textContent = text; tip.classList.add("show");
  placeTip(target);
}
function placeTip(target) {
  const r = target.getBoundingClientRect(); const tr = tip.getBoundingClientRect(); const m = 10;
  let left = r.left + r.width / 2 - tr.width / 2;
  left = Math.max(m, Math.min(left, window.innerWidth - tr.width - m));
  let top = r.top - tr.height - 8;
  if (top < m) top = r.bottom + 8;
  tip.style.left = `${left}px`; tip.style.top = `${top}px`;
}
function hideTip() { tip.classList.remove("show"); tipTarget = null; }
document.addEventListener("pointerover", (e) => { const t = e.target.closest("[data-tip]"); if (t && t !== tipTarget) showTip(t); });
document.addEventListener("pointerout", (e) => { const t = e.target.closest("[data-tip]"); if (t && t === tipTarget && !t.contains(e.relatedTarget)) hideTip(); });
document.addEventListener("focusin", (e) => { const t = e.target.closest && e.target.closest("[data-tip]"); if (t) showTip(t); });
document.addEventListener("focusout", () => hideTip());

/* ───────── wiring + boot ───────── */
$$(".nav-item").forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));
$("#refresh").addEventListener("click", () => loadState(playlist));
$("#playlist-select").addEventListener("change", (e) => loadState(e.target.value));
$("#track-search").addEventListener("input", () => renderTracks());
$("#cols-btn").addEventListener("click", (e) => { e.stopPropagation(); $("#cols-pop").hidden = !$("#cols-pop").hidden; });
document.addEventListener("click", (e) => { if (!e.target.closest(".menu")) $("#cols-pop").hidden = true; });
$("#scrim").addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });
const runPipelineBtn = document.getElementById("run-pipeline");
if (runPipelineBtn) runPipelineBtn.addEventListener("click", runChain);
const consoleBar = document.getElementById("console-bar");
if (consoleBar) consoleBar.addEventListener("click", () => {
  const c = document.getElementById("console"); c.classList.toggle("collapsed");
  const t = document.getElementById("console-toggle"); if (t) t.textContent = c.classList.contains("collapsed") ? "show" : "hide";
});

$("#csv-file").addEventListener("change", async (e) => {
  const file = e.target.files[0]; if (!file) return;
  const data = new FormData(); data.set("file", file);
  await fetch("/api/import", { method: "POST", body: data });
  e.target.value = "";
  await loadState();
});
$$("form[data-action]").forEach((form) => form.addEventListener("submit", (e) => {
  e.preventDefault(); if (!playlist) return; postForm(form, form.dataset.action);
}));

mountExplore({ rows: () => rows, playlist: () => playlist });
renderColsMenu();
setupCanvasNav();

// poll jobs; keep the pipeline live, and reload full state when a job changes
setInterval(async () => {
  try {
    const res = await fetch("/api/jobs"); const data = await res.json();
    const jobs = data.jobs || [];
    const sig = jobs.map((j) => `${j.id}:${j.status}`).join("|");
    if (state) state.jobs = jobs;
    renderJobs(jobs);
    const runningHere = jobs.some((j) => (j.status === "running" || j.status === "queued") && (!j.playlist || j.playlist === playlist));
    if (sig !== jobSig) { jobSig = sig; await loadState(playlist); }
    else if (runningHere) { await loadState(playlist); }   // live coverage while this playlist's job runs
    else if (view === "pipeline") renderPipeline();
  } catch { /* ignore */ }
}, 2500);

let bootPlaylist = "";
try { bootPlaylist = localStorage.getItem("cantabile.playlist") || ""; } catch (_) {}
loadState(bootPlaylist);
