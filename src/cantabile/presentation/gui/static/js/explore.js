// The Explore view: pick a chart type and what maps to each axis, render live,
// and pin the result to a per-playlist dashboard saved in localStorage.
import { draw } from "./theme.js";
import { MEASURES, DIMENSIONS } from "./data.js";
import { buildExplore } from "./charts.js";

const AXIS_MEASURES = MEASURES.filter((m) => m.key !== "__count__");
const CHART_TYPES = [
  { key: "bar", label: "Bar" }, { key: "pie", label: "Pie" }, { key: "line", label: "Line" },
  { key: "histogram", label: "Histogram" }, { key: "scatter", label: "Scatter" },
  { key: "scatter3d", label: "3D scatter" }, { key: "heatmap", label: "Heatmap" },
];

let ctx = { rows: () => [], playlist: () => "" };
let spec = {
  type: "scatter", groupBy: "structure", measure: "__count__", agg: "avg",
  feat: "felt_tempo", bins: 12, x: "energy", y: "valence", z: "felt_tempo",
  colorDim: "structure", sizeMeasure: "", xDim: "structure", yDim: "asset_confidence",
};

export function mountExplore(context) {
  ctx = context;
  document.getElementById("pin-btn").addEventListener("click", pin);
  renderControls();
}

function opts(list, selected) {
  return list.map((o) => `<option value="${o.key}" ${o.key === selected ? "selected" : ""}>${o.label}</option>`).join("");
}
function field(label, id, list, selected, allowNone) {
  const none = allowNone ? `<option value="" ${!selected ? "selected" : ""}>none</option>` : "";
  return `<label class="ctl"><span>${label}</span><select data-spec="${id}">${none}${opts(list, selected)}</select></label>`;
}

function renderControls() {
  const t = spec.type;
  let fields = "";
  if (t === "bar" || t === "pie") {
    fields = field("Group by", "groupBy", DIMENSIONS, spec.groupBy)
      + field("Measure", "measure", MEASURES, spec.measure)
      + aggField();
  } else if (t === "line") {
    fields = field("Measure (per track, across the playlist)", "measure", AXIS_MEASURES, spec.measure === "__count__" ? "felt_tempo" : spec.measure);
  } else if (t === "histogram") {
    fields = field("Feature", "feat", AXIS_MEASURES, spec.feat)
      + `<label class="ctl"><span>Bins</span><input type="number" min="3" max="40" data-spec="bins" value="${spec.bins}"></label>`;
  } else if (t === "scatter") {
    fields = field("X axis", "x", AXIS_MEASURES, spec.x)
      + field("Y axis", "y", AXIS_MEASURES, spec.y)
      + field("Color by", "colorDim", DIMENSIONS, spec.colorDim, true)
      + field("Size by", "sizeMeasure", AXIS_MEASURES, spec.sizeMeasure, true);
  } else if (t === "scatter3d") {
    fields = field("X axis", "x", AXIS_MEASURES, spec.x)
      + field("Y axis", "y", AXIS_MEASURES, spec.y)
      + field("Z axis", "z", AXIS_MEASURES, spec.z)
      + field("Color by", "colorDim", DIMENSIONS, spec.colorDim, true);
  } else if (t === "heatmap") {
    fields = field("Rows", "yDim", DIMENSIONS, spec.yDim)
      + field("Columns", "xDim", DIMENSIONS, spec.xDim)
      + field("Measure", "measure", MEASURES, spec.measure)
      + aggField();
  }
  const seg = CHART_TYPES.map((c) => `<button data-type="${c.key}" class="${c.key === t ? "active" : ""}">${c.label}</button>`).join("");
  document.getElementById("explore-controls").innerHTML =
    `<div class="ctl"><span>Chart type</span><div class="seg">${seg}</div></div>${fields}`;

  document.querySelectorAll("#explore-controls .seg button").forEach((b) =>
    b.addEventListener("click", () => { spec.type = b.dataset.type; renderControls(); renderChart(); }));
  document.querySelectorAll("#explore-controls [data-spec]").forEach((el) =>
    el.addEventListener("change", () => { spec[el.dataset.spec] = el.type === "number" ? Number(el.value) : el.value; renderChart(); }));
  renderChart();
}

function aggField() {
  return `<label class="ctl"><span>Aggregate</span><select data-spec="agg">
    ${["avg", "sum", "min", "max", "median"].map((a) => `<option value="${a}" ${a === spec.agg ? "selected" : ""}>${a}</option>`).join("")}
  </select></label>`;
}

export function renderChart() {
  const el = document.getElementById("explore-chart");
  draw(el, buildExplore(spec, ctx.rows()));
}

/* ───────────── dashboards ───────────── */
function dashKey(pl) { return `cantabile.dash.${pl}`; }
function loadDash(pl) { try { return JSON.parse(localStorage.getItem(dashKey(pl)) || "[]"); } catch { return []; } }
function saveDash(pl, arr) { localStorage.setItem(dashKey(pl), JSON.stringify(arr)); }

function pin() {
  const pl = ctx.playlist();
  if (!pl) return;
  const title = (document.getElementById("chart-title").value || "").trim() || defaultTitle(spec);
  const arr = loadDash(pl);
  arr.push({ id: Date.now(), title, spec: { ...spec } });
  saveDash(pl, arr);
  const btn = document.getElementById("pin-btn");
  btn.textContent = "Pinned ✓";
  setTimeout(() => { btn.textContent = "Pin to dashboard"; }, 1400);
}

function defaultTitle(s) {
  if (s.type === "scatter" || s.type === "scatter3d") return `${s.y} vs ${s.x}`;
  if (s.type === "histogram") return `${s.feat} distribution`;
  if (s.type === "line") return `${s.measure} across playlist`;
  if (s.type === "heatmap") return `${s.yDim} × ${s.xDim}`;
  return `${s.measure === "__count__" ? "count" : s.agg + " " + s.measure} by ${s.groupBy}`;
}

const TRASH = `<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>`;

export function renderDashboards() {
  const pl = ctx.playlist();
  const grid = document.getElementById("dash-grid");
  grid.querySelectorAll(".chart").forEach((el) => { const i = window.echarts.getInstanceByDom(el); if (i) i.dispose(); });
  const cards = loadDash(pl);
  if (!cards.length) {
    grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
      <svg viewBox="0 0 24 24" fill="none"><path d="M3 13h8V3H3z"/><path d="M13 21h8V8h-8z"/></svg>
      <h3>No pinned charts yet</h3><p>Build a chart in Explore and pin it. Your dashboard is saved per playlist in this browser.</p></div>`;
    return;
  }
  grid.innerHTML = cards.map((c) => `<div class="panel dash-card" data-id="${c.id}">
    <div class="dc-head"><h3>${escapeHtml(c.title)}</h3>
      <button class="icon-btn" data-remove="${c.id}" title="Remove">${TRASH}</button></div>
    <div class="panel-body"><div class="chart" id="dash-${c.id}"></div></div></div>`).join("");
  const rows = ctx.rows();
  for (const c of cards) draw(document.getElementById(`dash-${c.id}`), buildExplore(c.spec, rows));
  grid.querySelectorAll("[data-remove]").forEach((b) => b.addEventListener("click", () => {
    saveDash(pl, loadDash(pl).filter((c) => String(c.id) !== b.dataset.remove));
    renderDashboards();
  }));
}

function escapeHtml(s) { return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
