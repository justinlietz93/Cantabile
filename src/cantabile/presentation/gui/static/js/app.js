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
  const res = await fetch(`/api/state?playlist=${encodeURIComponent(pl || "")}`);
  state = await res.json();
  playlist = state.selected || "";
  rows = state.report ? state.report.tracks : [];
  renderTopbar();
  renderView(view);
  renderJobs(state.jobs || []);
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

/* ───────── tracks table ───────── */
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

function renderJobs(jobs) {
  $("#job-count").textContent = String(jobs.length);
  const el = $("#jobs");
  if (!jobs.length) { el.innerHTML = `<p class="missing">No jobs yet.</p>`; return; }
  el.innerHTML = jobs.map((job) => {
    const logs = [...(job.logs || [])].slice(-4);
    const lines = (job.error ? [job.error] : logs.length ? logs : [job.playlist || job.id]).filter(Boolean);
    const links = job.result && job.result.links ? job.result.links : {};
    const linkHtml = Object.entries(links).map(([k, href]) => `<a href="${esc(href)}" target="_blank" rel="noreferrer">${esc(linkLabel(k))}</a>`).join("");
    return `<article class="job"><div class="job-top"><strong>${esc(job.action)}</strong><span class="pill ${esc(job.status)}">${esc(job.status)}</span></div>
      <div class="job-lines">${lines.map((l) => `<span>${esc(l)}</span>`).join("")}</div>${linkHtml}</article>`;
  }).join("");
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

// poll jobs; when status set changes, reload full state so new facts appear
setInterval(async () => {
  try {
    const res = await fetch("/api/jobs"); const data = await res.json();
    const sig = (data.jobs || []).map((j) => `${j.id}:${j.status}`).join("|");
    if (sig !== jobSig) { jobSig = sig; await loadState(playlist); }
    else renderJobs(data.jobs || []);
  } catch { /* ignore */ }
}, 2500);

loadState();
