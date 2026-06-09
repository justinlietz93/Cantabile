// Turns a chart spec + track rows into an ECharts option. Covers the Explore
// chart types and the fixed Overview charts. Pure (no DOM), so the same builder
// serves the live Explore canvas and the saved dashboard cards.
import { C, base, axis, catColor, provColor } from "./theme.js";
import {
  aggregate, histogram, scatterPoints, uniqueGroups,
  getNum, getCat, measureLabel, measureUnit, dimLabel,
} from "./data.js";

const seriesColor = (i) => C.series[i % C.series.length];

export function buildExplore(spec, rows) {
  switch (spec.type) {
    case "bar": return barOpt(spec, rows);
    case "pie": return pieOpt(spec, rows);
    case "line": return lineOpt(spec, rows);
    case "histogram": return histOpt(spec, rows);
    case "scatter": return scatterOpt(spec, rows);
    case "scatter3d": return scatter3dOpt(spec, rows);
    case "heatmap": return heatOpt(spec, rows);
    default: return empty("Pick a chart type");
  }
}

function empty(msg) {
  return base({ graphic: { type: "text", left: "center", top: "middle", style: { text: msg, fill: C.faint, font: "13px Inter" } } });
}

function barOpt(spec, rows) {
  const d = aggregate(rows, spec.groupBy, spec.measure, spec.agg);
  if (!d.length) return empty("No data for this combination");
  return base({
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" },
      formatter: (p) => `${p[0].name}<br/><b>${p[0].value}</b> · ${p[0].data.n} tracks` },
    xAxis: { ...axis("", "category"), data: d.map((o) => o.name), axisLabel: { color: C.dim, fontSize: 11, interval: 0, rotate: d.length > 7 ? 35 : 0 } },
    yAxis: axis(measureLabel(spec.measure)),
    series: [{ type: "bar", barMaxWidth: 46, data: d.map((o) => ({ value: o.value, n: o.n, itemStyle: { color: catColor(o.name) || C.audio, borderRadius: [4, 4, 0, 0] } })) }],
  });
}

function pieOpt(spec, rows) {
  const d = aggregate(rows, spec.groupBy, spec.measure, spec.agg);
  if (!d.length) return empty("No data for this combination");
  return base({
    tooltip: { trigger: "item", formatter: (p) => `${p.name}<br/><b>${p.value}</b> (${p.percent}%)` },
    legend: { bottom: 0, textStyle: { color: C.dim }, type: "scroll" },
    series: [{
      type: "pie", radius: ["42%", "70%"], center: ["50%", "46%"], avoidLabelOverlap: true,
      itemStyle: { borderColor: C.panel, borderWidth: 2 },
      label: { color: C.dim }, labelLine: { lineStyle: { color: C.line } },
      data: d.map((o, i) => ({ name: o.name, value: o.value, itemStyle: { color: catColor(o.name) || seriesColor(i) } })),
    }],
  });
}

function lineOpt(spec, rows) {
  const sorted = [...rows].sort((a, b) => a.seq - b.seq);
  const data = sorted.map((r) => [r.seq, getNum(r, spec.measure)]).filter((p) => p[1] != null);
  if (!data.length) return empty("No measured values yet — run audio analysis");
  return base({
    tooltip: { trigger: "axis", formatter: (p) => `Track ${p[0].data[0]}<br/><b>${p[0].data[1]}</b> ${measureUnit(spec.measure)}` },
    xAxis: { ...axis("playlist position"), min: 1 },
    yAxis: axis(measureLabel(spec.measure)),
    series: [{
      type: "line", smooth: true, showSymbol: data.length < 60, symbolSize: 6,
      lineStyle: { color: C.audio, width: 2 }, itemStyle: { color: C.audio },
      areaStyle: { color: new window.echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: "rgba(242,176,86,0.25)" }, { offset: 1, color: "rgba(242,176,86,0)" }]) },
      data,
    }],
  });
}

function histOpt(spec, rows) {
  const h = histogram(rows, spec.feat, spec.bins || 10);
  if (!h.labels.length) return empty("No values for this feature");
  return base({
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, formatter: (p) => `≥ ${p[0].name} ${measureUnit(spec.feat)}<br/><b>${p[0].value}</b> tracks` },
    xAxis: { ...axis(`${measureLabel(spec.feat)} (${measureUnit(spec.feat) || "value"})`, "category"), data: h.labels },
    yAxis: axis("tracks"),
    series: [{ type: "bar", data: h.counts, itemStyle: { color: C.teal, borderRadius: [3, 3, 0, 0] } }],
  });
}

function scatterOpt(spec, rows) {
  const pts = scatterPoints(rows, spec.x, spec.y, null, spec.colorDim, spec.sizeMeasure);
  if (!pts.length) return empty("No tracks have both of these measured");
  const sizes = pts.map((p) => p.size).filter((s) => s != null);
  const smin = sizes.length ? Math.min(...sizes) : 0, smax = sizes.length ? Math.max(...sizes) : 1;
  const sym = (p) => { if (p.size == null || smax === smin) return 11; return 8 + 22 * ((p.size - smin) / (smax - smin)); };
  const groups = spec.colorDim ? uniqueGroups(pts) : [null];
  const series = groups.map((g, i) => ({
    type: "scatter", name: g == null ? measureLabel(spec.y) : g,
    symbolSize: (v, p) => p.data.sym,
    itemStyle: { color: g == null ? C.audio : (catColor(g) || seriesColor(i)), opacity: 0.82, borderColor: "rgba(0,0,0,0.3)" },
    data: pts.filter((p) => p.group === g).map((p) => ({ value: p.coord, sym: sym(p), name: p.label, sz: p.size })),
  }));
  return base({
    tooltip: { trigger: "item", formatter: (p) => `${p.data.name}<br/>${measureLabel(spec.x)}: <b>${p.value[0]}</b><br/>${measureLabel(spec.y)}: <b>${p.value[1]}</b>${spec.sizeMeasure ? `<br/>${measureLabel(spec.sizeMeasure)}: ${p.data.sz}` : ""}` },
    legend: spec.colorDim ? { bottom: 0, textStyle: { color: C.dim }, type: "scroll" } : undefined,
    xAxis: axis(`${measureLabel(spec.x)} ${measureUnit(spec.x) ? "(" + measureUnit(spec.x) + ")" : ""}`),
    yAxis: axis(`${measureLabel(spec.y)} ${measureUnit(spec.y) ? "(" + measureUnit(spec.y) + ")" : ""}`),
    series,
  });
}

function scatter3dOpt(spec, rows) {
  const pts = scatterPoints(rows, spec.x, spec.y, spec.z, spec.colorDim, null);
  if (!pts.length) return empty("No tracks have all three measured");
  const groups = spec.colorDim ? uniqueGroups(pts) : [null];
  const series = groups.map((g, i) => ({
    type: "scatter3D", name: g == null ? "tracks" : g, symbolSize: 9,
    itemStyle: { color: g == null ? C.audio : (catColor(g) || seriesColor(i)), opacity: 0.85 },
    data: pts.filter((p) => p.group === g).map((p) => ({ value: p.coord, name: p.label })),
  }));
  return {
    backgroundColor: "transparent",
    tooltip: { backgroundColor: "#050810", borderColor: C.line, textStyle: { color: C.ink }, formatter: (p) => `${p.data.name}<br/>${p.value.map(Number).map((n) => n.toFixed(2)).join(", ")}` },
    legend: spec.colorDim ? { bottom: 0, textStyle: { color: C.dim } } : undefined,
    xAxis3D: { name: measureLabel(spec.x), nameTextStyle: { color: C.faint }, axisLine: { lineStyle: { color: C.line } }, axisLabel: { color: C.dim }, splitLine: { lineStyle: { color: C.grid } } },
    yAxis3D: { name: measureLabel(spec.y), nameTextStyle: { color: C.faint }, axisLine: { lineStyle: { color: C.line } }, axisLabel: { color: C.dim }, splitLine: { lineStyle: { color: C.grid } } },
    zAxis3D: { name: measureLabel(spec.z), nameTextStyle: { color: C.faint }, axisLine: { lineStyle: { color: C.line } }, axisLabel: { color: C.dim }, splitLine: { lineStyle: { color: C.grid } } },
    grid3D: {
      boxWidth: 100, boxDepth: 100, viewControl: { projection: "perspective", autoRotate: false },
      axisPointer: { lineStyle: { color: C.teal } },
      environment: new window.echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: "#0e1320" }, { offset: 1, color: "#0b0e14" }]),
    },
    series,
  };
}

function heatOpt(spec, rows) {
  const xCats = [...new Set(rows.map((r) => getCat(r, spec.xDim)))];
  const yCats = [...new Set(rows.map((r) => getCat(r, spec.yDim)))];
  const cell = new Map();
  for (const r of rows) {
    const k = getCat(r, spec.xDim) + "||" + getCat(r, spec.yDim);
    if (!cell.has(k)) cell.set(k, []);
    if (spec.measure === "__count__") cell.get(k).push(1);
    else { const v = getNum(r, spec.measure); if (v != null) cell.get(k).push(v); }
  }
  const data = []; let maxV = 0;
  xCats.forEach((xc, xi) => yCats.forEach((yc, yi) => {
    const xs = cell.get(xc + "||" + yc) || [];
    let v = 0;
    if (xs.length) v = spec.measure === "__count__" ? xs.length : xs.reduce((a, b) => a + b, 0) / xs.length;
    v = Number(v.toFixed(2)); maxV = Math.max(maxV, v);
    if (xs.length) data.push([xi, yi, v]);
  }));
  if (!data.length) return empty("No data for this combination");
  return base({
    grid: { left: 60, right: 24, top: 20, bottom: 70, containLabel: true },
    tooltip: { position: "top", formatter: (p) => `${xCats[p.value[0]]} · ${yCats[p.value[1]]}<br/><b>${p.value[2]}</b>` },
    xAxis: { ...axis(dimLabel(spec.xDim), "category"), data: xCats, axisLabel: { color: C.dim, rotate: xCats.length > 6 ? 35 : 0 }, splitLine: { show: false } },
    yAxis: { ...axis(dimLabel(spec.yDim), "category"), data: yCats, splitLine: { show: false } },
    visualMap: { min: 0, max: maxV || 1, calculable: true, orient: "horizontal", left: "center", bottom: 6, textStyle: { color: C.dim }, inRange: { color: ["#15233a", C.teal, C.audio] } },
    series: [{ type: "heatmap", data, label: { show: true, color: "#0b0e14", fontSize: 10 }, itemStyle: { borderColor: C.panel, borderWidth: 2 } }],
  });
}

/* ───────────── fixed Overview charts ───────────── */
export function overviewTempo(rows) {
  const pts = rows.filter((r) => r.spotify_tempo != null && r.measured_tempo != null)
    .map((r) => ({ value: [r.spotify_tempo, r.measured_tempo], name: `${r.seq}. ${r.title}`, d: Math.abs(r.spotify_tempo - r.measured_tempo) }));
  if (!pts.length) return empty("Run audio analysis (MIR) to compare Spotify's tempo with the measured tempo.");
  const all = pts.flatMap((p) => p.value); const lo = Math.min(...all) - 5, hi = Math.max(...all) + 5;
  return base({
    tooltip: { trigger: "item", formatter: (p) => p.data.name ? `${p.data.name}<br/>Spotify: <b>${p.value[0]}</b> · measured: <b style="color:${C.audio}">${p.value[1]}</b><br/>off by ${p.data.d.toFixed(1)} bpm` : "" },
    xAxis: { ...axis("Spotify tempo (bpm)"), min: lo, max: hi },
    yAxis: { ...axis("measured tempo (bpm)"), min: lo, max: hi },
    series: [
      { type: "line", silent: true, showSymbol: false, lineStyle: { color: C.spotify, type: "dashed", width: 1.5 }, data: [[lo, lo], [hi, hi]], tooltip: { show: false } },
      { type: "scatter", symbolSize: (v, p) => 9 + Math.min(26, p.data.d * 0.6),
        itemStyle: { color: C.audio, opacity: 0.85, borderColor: "rgba(0,0,0,0.35)" }, data: pts },
    ],
  });
}

export function overviewEV(rows) {
  const pts = rows.map((r) => ({ value: [getNum(r, "energy"), getNum(r, "valence")], name: `${r.seq}. ${r.title}`, g: getCat(r, "structure") }))
    .filter((p) => p.value[0] != null && p.value[1] != null);
  if (!pts.length) return empty("No energy/valence values imported yet");
  const groups = [...new Set(pts.map((p) => p.g))];
  return base({
    tooltip: { trigger: "item", formatter: (p) => `${p.data.name}<br/>energy <b>${p.value[0]}</b> · valence <b>${p.value[1]}</b>` },
    legend: { bottom: 0, textStyle: { color: C.dim } },
    xAxis: { ...axis("energy"), min: 0, max: 1 }, yAxis: { ...axis("valence"), min: 0, max: 1 },
    series: groups.map((g, i) => ({ type: "scatter", name: g, symbolSize: 11,
      itemStyle: { color: catColor(g) || seriesColor(i), opacity: 0.8 },
      data: pts.filter((p) => p.g === g) })),
  });
}

export function countsDonut(counts) {
  const d = Object.entries(counts || {}).map(([name, value]) => ({ name, value }));
  if (!d.length) return empty("No data");
  return base({
    tooltip: { trigger: "item", formatter: (p) => `${p.name}: <b>${p.value}</b> (${p.percent}%)` },
    legend: { bottom: 0, textStyle: { color: C.dim }, type: "scroll" },
    series: [{ type: "pie", radius: ["46%", "72%"], center: ["50%", "44%"], itemStyle: { borderColor: C.panel, borderWidth: 2 }, label: { show: false },
      data: d.map((o, i) => ({ ...o, itemStyle: { color: catColor(o.name) || seriesColor(i) } })) }],
  });
}

export function countsBar(counts, label, useProv) {
  const d = Object.entries(counts || {}).sort((a, b) => b[1] - a[1]);
  if (!d.length) return empty("No data");
  return base({
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: { ...axis("", "category"), data: d.map((o) => o[0]), axisLabel: { color: C.dim, interval: 0, rotate: d.length > 4 ? 30 : 0 } },
    yAxis: axis(label || "tracks"),
    series: [{ type: "bar", barMaxWidth: 40, data: d.map(([k, v]) => ({ value: v, itemStyle: { color: (useProv ? provColor(k) : catColor(k)) || C.teal, borderRadius: [4, 4, 0, 0] } })) }],
  });
}
