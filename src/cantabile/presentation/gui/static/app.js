let selectedPlaylist = "";
let currentState = null;
let floatingTip = null;
let tipTarget = null;

const qs = (selector) => document.querySelector(selector);
const qsa = (selector) => Array.from(document.querySelectorAll(selector));
const TIPS = {
  audio: "Tracks with a downloaded audio file.",
  analysis: "Tracks where Cantabile measured tempo and shape from the waveform.",
  confidence: "How confident Cantabile is that the downloaded file is the right recording.",
  facts: "Where the stored facts came from, such as Spotify, lyrics lookup, or audio analysis.",
  tempo: "Which source currently supplies the displayed tempo.",
  shape: "Loop means the track returns to similar material; line means it moves forward.",
  parts: "Separated audio parts from Demucs, such as drums, bass, vocals, and other.",
};

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function valueText(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function tipElement(target) {
  if (!(target instanceof Element)) return null;
  return target.closest("[data-tip]");
}

function setupTooltips() {
  floatingTip = document.createElement("div");
  floatingTip.className = "floating-tip";
  floatingTip.setAttribute("role", "tooltip");
  floatingTip.hidden = true;
  document.body.appendChild(floatingTip);

  document.addEventListener("mouseover", (event) => {
    const target = tipElement(event.target);
    if (target) showTip(target);
  });
  document.addEventListener("focusin", (event) => {
    const target = tipElement(event.target);
    if (target) showTip(target);
  });
  document.addEventListener("mouseout", (event) => {
    const leaving = tipElement(event.target);
    if (!leaving || leaving !== tipTarget) return;
    if (tipElement(event.relatedTarget) !== tipTarget) hideTip();
  });
  document.addEventListener("focusout", (event) => {
    if (event.target === tipTarget) hideTip();
  });
  window.addEventListener("scroll", () => {
    if (tipTarget) placeTip(tipTarget);
  }, true);
  window.addEventListener("resize", () => {
    if (tipTarget) placeTip(tipTarget);
  });
}

function showTip(target) {
  const text = target.dataset.tip || "";
  if (!text || !floatingTip) return;
  tipTarget = target;
  floatingTip.textContent = text;
  floatingTip.hidden = false;
  placeTip(target);
  floatingTip.classList.add("visible");
}

function hideTip() {
  if (!floatingTip) return;
  floatingTip.classList.remove("visible");
  floatingTip.hidden = true;
  tipTarget = null;
}

function placeTip(target) {
  if (!floatingTip) return;
  const rect = target.getBoundingClientRect();
  const tipRect = floatingTip.getBoundingClientRect();
  const margin = 12;
  let left = rect.left + rect.width / 2 - tipRect.width / 2;
  left = Math.max(margin, Math.min(left, window.innerWidth - tipRect.width - margin));
  let top = rect.top - tipRect.height - 10;
  if (top < margin) top = rect.bottom + 10;
  top = Math.max(margin, Math.min(top, window.innerHeight - tipRect.height - margin));
  floatingTip.style.left = `${left}px`;
  floatingTip.style.top = `${top}px`;
}

async function loadState(playlist = selectedPlaylist) {
  const res = await fetch(`/api/state?playlist=${encodeURIComponent(playlist || "")}`);
  currentState = await res.json();
  selectedPlaylist = currentState.selected || "";
  renderState(currentState);
}

function renderState(state) {
  renderPlaylists(state.playlists || []);
  renderHeader(state.report);
  renderMetrics(state.report);
  renderCharts(state.report);
  window.CantabileVisuals.renderAnalysisBoard(state.report);
  renderTracks(state.report);
  renderJobs(state.jobs || []);
  qsa("form[data-action] button").forEach((button) => {
    button.disabled = !selectedPlaylist;
  });
}

function renderPlaylists(playlists) {
  const nav = qs("#playlists");
  if (!playlists.length) {
    nav.innerHTML = `<p class="empty">No playlists</p>`;
    return;
  }
  nav.innerHTML = playlists.map((playlist) => `
    <button type="button" class="playlist-item ${playlist.name === selectedPlaylist ? "active" : ""}"
      data-playlist="${esc(playlist.name)}">
      <span>${esc(playlist.name)}</span><b>${playlist.size}</b>
    </button>
  `).join("");
  qsa(".playlist-item").forEach((button) => {
    button.addEventListener("click", () => loadState(button.dataset.playlist));
  });
}

function renderHeader(report) {
  qs("#playlist-title").textContent = report ? report.playlist_name : "Cantabile";
  qs("#report-subtitle").textContent = report
    ? `${report.summary.total_tracks} tracks / ${report.playlist_source} / ${report.schema_version}`
    : "No library loaded";
  qs("#console-playlist").textContent = report ? report.playlist_name : "No playlist";
  qs("#signal-note").textContent = report
    ? `${report.summary.feature_counts ? Object.keys(report.summary.feature_counts).length : 0} features`
    : "";
}

function renderMetrics(report) {
  const el = qs("#metrics");
  if (!report) {
    el.innerHTML = "";
    return;
  }
  const s = report.summary;
  el.innerHTML = [
    metric("Tracks", s.total_tracks, s.total_tracks, "Tracks in this playlist."),
    metric("Downloaded", s.audio_assets, s.total_tracks, TIPS.audio),
    metric("Lyrics", s.lyrics_tracks, s.total_tracks, "Tracks with lyrics or instrumental status."),
    metric("Analyzed", s.mir_tracks, s.total_tracks, TIPS.analysis),
    metric("Parts", s.stemmed_tracks, s.total_tracks, TIPS.parts),
  ].join("");
}

function metric(label, value, total, tip) {
  const pct = total ? Math.round((Number(value) / Number(total)) * 100) : 0;
  return `<article class="metric">
    <span>${esc(label)} <i class="tip" tabindex="0" data-tip="${esc(tip)}">?</i></span>
    <strong>${esc(value)}</strong>
    <div class="meter"><i style="width:${Math.max(0, Math.min(100, pct))}%"></i></div>
  </article>`;
}

function renderCharts(report) {
  const el = qs("#charts");
  if (!report) {
    el.innerHTML = "";
    return;
  }
  const s = report.summary;
  el.innerHTML = [
    bars("Download Confidence", s.confidence_counts, TIPS.confidence),
    bars("Fact Source", s.provenance_counts, TIPS.facts),
    bars("Tempo Source", s.tempo_source_counts, TIPS.tempo),
    bars("Loop / Line", s.structure_counts, TIPS.shape),
  ].join("");
}

function bars(title, counts, tip) {
  const entries = Object.entries(counts || {});
  const heading = `${esc(title)} <span class="tip" tabindex="0" data-tip="${esc(tip)}">?</span>`;
  if (!entries.length) return `<article class="chart"><h3>${heading}</h3><p class="empty">No data</p></article>`;
  const total = entries.reduce((sum, [, value]) => sum + value, 0) || 1;
  const body = entries.sort(([a], [b]) => a.localeCompare(b)).map(([label, value]) => {
    const pct = Math.max(3, Math.round((value / total) * 100));
    return `<div class="bar-row"><span>${esc(displayLabel(label))}</span><div class="bar">
      <i style="width:${pct}%"></i></div><b>${esc(value)}</b></div>`;
  }).join("");
  return `<article class="chart"><h3>${heading}</h3>${body}</article>`;
}

function displayLabel(label) {
  const labels = {
    audio: "audio analysis",
    spotify: "Spotify",
    lrclib: "lyrics lookup",
    genius: "Genius",
    missing: "missing",
    high: "high",
    medium: "medium",
    low: "low",
    override: "manual",
    loop: "loop",
    line: "line",
  };
  return labels[label] || label;
}

function renderTracks(report) {
  const body = qs("#track-body");
  if (!report) {
    body.innerHTML = `<tr><td colspan="8" class="empty">No tracks</td></tr>`;
    return;
  }
  const query = qs("#track-filter").value.trim().toLowerCase();
  const rows = report.tracks.filter((row) => {
    const haystack = `${row.title} ${row.artists.join(" ")}`.toLowerCase();
    return !query || haystack.includes(query);
  });
  body.innerHTML = rows.map(trackRow).join("") || `<tr><td colspan="8" class="empty">No matches</td></tr>`;
}

function trackRow(row) {
  const tempo = feature(row, "tempo");
  const minTempo = feature(row, "tempo_min");
  const maxTempo = feature(row, "tempo_max");
  const tempoVar = feature(row, "tempo_variability");
  const sections = feature(row, "section_count");
  const loopScore = feature(row, "loop_score");
  const shape = feature(row, "structure");
  const confidence = row.asset_confidence || "missing";
  return `<tr>
    <td>${esc(row.seq)}</td>
    <td><strong>${esc(row.title)}</strong><small>${esc(row.artists.join(", "))}</small></td>
    <td>${analysisValue(tempo)}${sourceText(tempo)}</td>
    <td>${tempoRange(minTempo, maxTempo, tempoVar)}</td>
    <td>${analysisValue(sections)}</td>
    <td>${analysisValue(loopScore)}</td>
    <td>${analysisValue(shape)}</td>
    <td>${evidence(row, confidence)}</td>
  </tr>`;
}

function feature(row, name) {
  return row.resolved && row.resolved[name] ? row.resolved[name] : null;
}

function analysisValue(item) {
  return item ? esc(valueText(item.value)) : `<span class="missing">not measured</span>`;
}

function sourceText(item) {
  return item ? `<small>${esc(displayLabel(item.source || "missing"))}</small>` : "";
}

function tempoRange(minTempo, maxTempo, tempoVar) {
  if (!minTempo && !maxTempo && !tempoVar) return `<span class="missing">not measured</span>`;
  const range = minTempo && maxTempo ? `${valueText(minTempo.value)}-${valueText(maxTempo.value)}` : "";
  const variability = tempoVar ? `variation ${valueText(tempoVar.value)}` : "";
  return `${esc(range || variability)}${range && variability ? `<small>${esc(variability)}</small>` : ""}`;
}

function evidence(row, confidence) {
  const parts = Object.keys(row.stems || {}).sort();
  const partText = parts.length ? `${parts.length} parts` : "no parts";
  return `<div class="evidence-stack">
    <span><b>download</b> <i class="pill ${esc(confidence)}">${esc(confidence)}</i></span>
    <span><b>lyrics</b> ${esc(row.lyrics_status || "missing")}</span>
    <span><b>parts</b> ${esc(partText)}</span>
  </div>`;
}

function renderJobs(jobs) {
  qs("#job-count").textContent = String(jobs.length);
  const el = qs("#job-list");
  if (!jobs.length) {
    el.innerHTML = `<p class="empty">No jobs</p>`;
    return;
  }
  el.innerHTML = jobs.map((job) => {
    const logs = [...(job.logs || [])].slice(-4).join("\n");
    const links = job.result && job.result.links ? job.result.links : {};
    const linkHtml = Object.entries(links).map(([label, href]) => (
      `<a href="${esc(href)}" title="${esc(href)}" target="_blank" rel="noreferrer">${esc(linkLabel(label))}</a>`
    )).join("");
    const lines = (job.error || logs || job.playlist || job.id).split("\n").filter(Boolean);
    const lineHtml = lines.map((line) => `<span>${esc(line)}</span>`).join("");
    return `<article class="job">
      <div class="job-top"><strong>${esc(job.action)}</strong>
        <span class="pill ${esc(job.status)}">${esc(job.status)}</span></div>
      <div class="job-lines">${lineHtml}</div>
      ${linkHtml}
    </article>`;
  }).join("");
}

function linkLabel(label) {
  const labels = {
    html_report: "Open report",
    observations_csv: "Download observations CSV",
    tracks_csv: "Download tracks CSV",
  };
  return labels[label] || label;
}

async function postForm(form, url) {
  const button = form.querySelector("button[type='submit']");
  const data = new FormData(form);
  if (url !== "/api/import") data.set("playlist", selectedPlaylist);
  button.disabled = true;
  try {
    const res = await fetch(url, { method: "POST", body: data });
    if (!res.ok) throw new Error(await res.text());
    await res.json();
    await loadState(selectedPlaylist);
  } finally {
    button.disabled = false;
  }
}

qs("#refresh").addEventListener("click", () => loadState(selectedPlaylist));
qs("#track-filter").addEventListener("input", () => renderTracks(currentState && currentState.report));

qs("#import-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  await postForm(event.currentTarget, "/api/import");
  event.currentTarget.reset();
});

qsa("form[data-action]").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!selectedPlaylist) return;
    await postForm(form, form.dataset.action);
  });
});

setupTooltips();
window.CantabileVisuals.setupViewTabs();
setInterval(() => loadState(selectedPlaylist), 2500);
loadState();
