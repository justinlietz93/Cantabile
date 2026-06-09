// Chart theme + palette + lifecycle. ECharts is loaded as a UMD global.
const echarts = window.echarts;

export const C = {
  audio: "#f2b056", spotify: "#7c86ff", teal: "#3fb6c4",
  ok: "#4ed99a", warn: "#f2b056", bad: "#f2785c", none: "#525d78",
  ink: "#e7ecf6", dim: "#9aa4bb", faint: "#5d6884",
  line: "#222c40", grid: "#1a2234", panel: "#121826",
  series: ["#f2b056", "#7c86ff", "#3fb6c4", "#4ed99a", "#f2785c", "#b48cff", "#5fd0e0", "#ffd089", "#9aa4bb", "#86f0c8"],
};

export function provColor(source) {
  return ({ spotify: C.spotify, audio: C.audio, lrclib: C.teal, genius: C.teal, manual: C.ok })[source] || C.none;
}
export function catColor(value) {
  const v = String(value).toLowerCase();
  if (v === "loop") return C.audio;
  if (v === "line") return C.spotify;
  if (v === "high") return C.ok;
  if (v === "medium") return C.warn;
  if (v === "low" || v === "missing" || v === "none") return C.bad;
  return null;
}

const charts = new Set();

export function chart(el) {
  if (!el) return null;
  let inst = echarts.getInstanceByDom(el);
  if (!inst) { inst = echarts.init(el, null, { renderer: "canvas" }); charts.add(inst); }
  return inst;
}
export function draw(el, option) {
  const inst = chart(el);
  if (!inst) return null;
  inst.setOption(option, true);
  return inst;
}
export function resizeAll() {
  charts.forEach((c) => { if (!c.isDisposed()) c.resize(); });
}
window.addEventListener("resize", resizeAll);

// shared option scaffolding so every chart matches the studio look
export function base(extra = {}) {
  return {
    backgroundColor: "transparent",
    textStyle: { fontFamily: "Inter, sans-serif", color: C.dim },
    color: C.series,
    grid: { left: 48, right: 24, top: 28, bottom: 40, containLabel: true },
    tooltip: {
      backgroundColor: "#050810", borderColor: C.line, borderWidth: 1,
      textStyle: { color: C.ink, fontSize: 12 }, ...extra.tooltip,
    },
    ...extra,
  };
}
export function axis(name, type = "value") {
  return {
    type, name, nameTextStyle: { color: C.faint, fontSize: 11 },
    axisLine: { lineStyle: { color: C.line } },
    axisTick: { show: false },
    axisLabel: { color: C.dim, fontSize: 11 },
    splitLine: { lineStyle: { color: C.grid, type: "dashed" } },
  };
}
