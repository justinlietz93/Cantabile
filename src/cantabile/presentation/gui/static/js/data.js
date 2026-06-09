// The data model the GUI reasons about: which features are numeric measures,
// which are categorical dimensions, how to pull a value off a track row, and
// how to aggregate rows into groups. This is what makes Explore generic.

export const MEASURES = [
  { key: "__count__", label: "Track count", unit: "" },
  { key: "tempo", label: "Tempo (resolved)", unit: "bpm" },
  { key: "felt_tempo", label: "Felt tempo (measured)", unit: "bpm" },
  { key: "tempo_variability", label: "Tempo variability", unit: "bpm" },
  { key: "tempo_min", label: "Tempo min", unit: "bpm" },
  { key: "tempo_max", label: "Tempo max", unit: "bpm" },
  { key: "section_count", label: "Section count", unit: "" },
  { key: "loop_score", label: "Loop score", unit: "" },
  { key: "energy", label: "Energy", unit: "" },
  { key: "valence", label: "Valence", unit: "" },
  { key: "danceability", label: "Danceability", unit: "" },
  { key: "acousticness", label: "Acousticness", unit: "" },
  { key: "instrumentalness", label: "Instrumentalness", unit: "" },
  { key: "liveness", label: "Liveness", unit: "" },
  { key: "speechiness", label: "Speechiness", unit: "" },
  { key: "loudness", label: "Loudness", unit: "dB" },
  { key: "audio_duration", label: "Audio duration", unit: "s" },
  { key: "duration_min", label: "Track length", unit: "min" },
  { key: "key", label: "Key", unit: "" },
  { key: "mode", label: "Mode", unit: "" },
  { key: "time_signature", label: "Time signature", unit: "" },
  { key: "seq", label: "Playlist position", unit: "" },
];

export const DIMENSIONS = [
  { key: "structure", label: "Loop / line" },
  { key: "asset_confidence", label: "Download confidence" },
  { key: "tempo_source", label: "Tempo source" },
  { key: "asset_source", label: "Audio source" },
  { key: "lyrics_status", label: "Lyrics status" },
  { key: "primary_artist", label: "Artist" },
  { key: "key", label: "Key" },
  { key: "mode", label: "Mode" },
  { key: "time_signature", label: "Time signature" },
  { key: "has_audio", label: "Has audio" },
  { key: "has_stems", label: "Stemmed" },
];

const KEY_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const SRC_LABEL = { spotify: "Spotify", audio: "measured", lrclib: "LRCLIB", genius: "Genius", manual: "manual", missing: "missing" };

export function measureLabel(key) { return (MEASURES.find((m) => m.key === key) || {}).label || key; }
export function measureUnit(key) { return (MEASURES.find((m) => m.key === key) || {}).unit || ""; }
export function dimLabel(key) { return (DIMENSIONS.find((d) => d.key === key) || {}).label || key; }

export function getNum(row, feat) {
  if (!row) return null;
  if (feat === "duration_min") return row.duration_ms ? row.duration_ms / 60000 : null;
  if (feat === "seq") return row.seq;
  const r = row.resolved && row.resolved[feat];
  if (!r || r.value === null || r.value === undefined || r.value === "") return null;
  const n = Number(r.value);
  return Number.isFinite(n) ? n : null;
}

export function srcLabel(s) { return SRC_LABEL[s] || s || "missing"; }

export function getCat(row, dim) {
  const res = row.resolved || {};
  switch (dim) {
    case "primary_artist": return (row.artists && row.artists[0]) || "—";
    case "tempo_source": return srcLabel(res.tempo ? res.tempo.source : "missing");
    case "asset_source": return srcLabel(row.asset_source || "missing");
    case "asset_confidence": return row.asset_confidence || "missing";
    case "lyrics_status": return row.lyrics_status || "missing";
    case "structure": return res.structure ? String(res.structure.value) : "unmeasured";
    case "has_audio": return row.has_audio ? "has audio" : "no audio";
    case "has_stems": return Object.keys(row.stems || {}).length ? "stemmed" : "not stemmed";
    case "key": { const v = res.key ? Number(res.key.value) : null; return v == null || Number.isNaN(v) ? "—" : (KEY_NAMES[((v % 12) + 12) % 12] || String(v)); }
    case "mode": { const v = res.mode ? Number(res.mode.value) : null; return v == null ? "—" : (v >= 1 ? "major" : "minor"); }
    case "time_signature": { const v = res.time_signature ? res.time_signature.value : null; return v == null ? "—" : `${v}/4`; }
    default: return res[dim] ? String(res[dim].value) : "missing";
  }
}

const AGGS = {
  count: (xs) => xs.length,
  sum: (xs) => xs.reduce((a, b) => a + b, 0),
  avg: (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0),
  min: (xs) => (xs.length ? Math.min(...xs) : 0),
  max: (xs) => (xs.length ? Math.max(...xs) : 0),
  median: (xs) => { if (!xs.length) return 0; const s = [...xs].sort((a, b) => a - b); const m = Math.floor(s.length / 2); return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; },
};

// Group rows by a dimension and reduce a measure. measure '__count__' => count.
export function aggregate(rows, dim, measure, agg) {
  const groups = new Map();
  for (const row of rows) {
    const key = getCat(row, dim);
    if (!groups.has(key)) groups.set(key, []);
    if (measure === "__count__") groups.get(key).push(1);
    else { const v = getNum(row, measure); if (v != null) groups.get(key).push(v); }
  }
  const fn = measure === "__count__" ? AGGS.count : (AGGS[agg] || AGGS.avg);
  const out = [];
  groups.forEach((xs, name) => out.push({ name, value: Number(fn(xs).toFixed(3)), n: xs.length }));
  return out.sort((a, b) => b.value - a.value);
}

// Histogram of one numeric feature.
export function histogram(rows, feat, bins = 10) {
  const vals = rows.map((r) => getNum(r, feat)).filter((v) => v != null);
  if (!vals.length) return { labels: [], counts: [] };
  const min = Math.min(...vals), max = Math.max(...vals);
  if (min === max) return { labels: [String(min)], counts: [vals.length] };
  const w = (max - min) / bins;
  const counts = new Array(bins).fill(0);
  for (const v of vals) { let i = Math.floor((v - min) / w); if (i >= bins) i = bins - 1; counts[i]++; }
  const labels = counts.map((_, i) => `${(min + i * w).toFixed(0)}`);
  return { labels, counts };
}

// Rows as scatter points with optional color dimension and size measure.
export function scatterPoints(rows, x, y, z, colorDim, sizeMeasure) {
  const pts = [];
  for (const row of rows) {
    const xv = getNum(row, x), yv = getNum(row, y);
    if (xv == null || yv == null) continue;
    const zv = z ? getNum(row, z) : null;
    if (z && zv == null) continue;
    pts.push({
      row,
      coord: z ? [xv, yv, zv] : [xv, yv],
      group: colorDim ? getCat(row, colorDim) : null,
      size: sizeMeasure ? getNum(row, sizeMeasure) : null,
      label: `${row.seq}. ${row.title}`,
    });
  }
  return pts;
}

export function uniqueGroups(pts) { return [...new Set(pts.map((p) => p.group).filter((g) => g != null))]; }
