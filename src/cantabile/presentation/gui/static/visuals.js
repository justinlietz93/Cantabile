(function () {
  const TIPS = {
    tempo: "Which source currently supplies the displayed tempo.",
    shape: "Loop means the track returns to similar material; line means it moves forward.",
    matrix: "Each cell is one track. Filled cells mean that fact exists for that track.",
  };

  const qs = (selector) => document.querySelector(selector);
  const qsa = (selector) => Array.from(document.querySelectorAll(selector));

  function esc(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function setupViewTabs() {
    qsa(".view-tab").forEach((button) => {
      button.addEventListener("click", () => {
        qsa(".view-tab").forEach((tab) => tab.classList.toggle("active", tab === button));
        qsa(".studio-view").forEach((panel) => {
          panel.classList.toggle("active", panel.dataset.viewPanel === button.dataset.view);
        });
      });
    });
  }

  function renderAnalysisBoard(report) {
    const el = qs("#analysis-board");
    if (!report) {
      el.innerHTML = `<p class="empty">No playlist selected</p>`;
      return;
    }
    el.innerHTML = [
      studioSnapshot(report.summary),
      tempoField(report.tracks),
      structureStrip(report.tracks),
      featureMatrix(report.tracks),
    ].join("");
  }

  function studioSnapshot(summary) {
    const tiles = [
      ["Tracks", summary.total_tracks],
      ["Audio", `${summary.audio_assets}/${summary.total_tracks}`],
      ["Analyzed", `${summary.mir_tracks}/${summary.total_tracks}`],
      ["Parts", `${summary.stemmed_tracks}/${summary.total_tracks}`],
    ];
    return `<article class="visual-card studio-snapshot">
      ${tiles.map(([label, value]) => (
        `<div><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`
      )).join("")}
    </article>`;
  }

  function tempoField(tracks) {
    const points = tracks.map((row, index) => ({ row, index, tempo: numericFeature(row, "tempo") }))
      .filter((point) => point.tempo !== null);
    if (!points.length) return visualEmpty("Tempo Field", TIPS.tempo);
    const values = points.map((point) => point.tempo);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const dots = points.map((point) => tempoPoint(point, min, span, tracks.length)).join("");
    return `<article class="visual-card wide">
      <h3>Tempo Field <span class="tip" tabindex="0" data-tip="${esc(TIPS.tempo)}">?</span></h3>
      <div class="tempo-stage">${dots}</div>
      <div class="axis-labels"><span>${esc(min)} bpm</span><span>${esc(max)} bpm</span></div>
    </article>`;
  }

  function tempoPoint(point, min, span, count) {
    const x = ((point.tempo - min) / span) * 100;
    const y = count > 1 ? (point.index / (count - 1)) * 100 : 50;
    const tip = `${point.row.seq}. ${point.row.title}: ${point.tempo} bpm`;
    return `<span class="tempo-point ${shapeClass(point.row)}" tabindex="0"
      data-tip="${esc(tip)}" style="left:${x.toFixed(2)}%; top:${y.toFixed(2)}%"></span>`;
  }

  function structureStrip(tracks) {
    const cells = tracks.map((row) => {
      const value = feature(row, "structure");
      const label = value ? displayLabel(value.value) : "not measured";
      return `<span class="sequence-cell ${shapeClass(row)}" tabindex="0"
        data-tip="${esc(`${row.seq}. ${row.title}: ${label}`)}"></span>`;
    }).join("");
    return `<article class="visual-card">
      <h3>Loop / Line Sequence <span class="tip" tabindex="0" data-tip="${esc(TIPS.shape)}">?</span></h3>
      <div class="sequence-strip" style="--track-count:${Math.max(1, tracks.length)}">${cells}</div>
    </article>`;
  }

  function featureMatrix(tracks) {
    const rows = [
      ["Audio", (row) => row.has_audio],
      ["Lyrics", (row) => row.lyrics_status === "present" || row.lyrics_status === "instrumental"],
      ["Tempo", (row) => numericFeature(row, "tempo") !== null],
      ["Range", (row) => numericFeature(row, "tempo_min") !== null || numericFeature(row, "tempo_max") !== null],
      ["Sections", (row) => numericFeature(row, "section_count") !== null],
      ["Loop", (row) => numericFeature(row, "loop_score") !== null],
      ["Parts", (row) => Object.keys(row.stems || {}).length > 0],
    ];
    return `<article class="visual-card">
      <h3>Feature Matrix <span class="tip" tabindex="0" data-tip="${esc(TIPS.matrix)}">?</span></h3>
      <div class="feature-matrix">${rows.map(([label, test]) => matrixRow(label, tracks, test)).join("")}</div>
    </article>`;
  }

  function matrixRow(label, tracks, test) {
    const count = tracks.filter(test).length;
    const cells = tracks.map((row) => {
      const hit = test(row);
      const text = `${row.seq}. ${row.title}: ${label.toLowerCase()} ${hit ? "available" : "missing"}`;
      return `<span class="matrix-cell ${hit ? "hit" : ""}" tabindex="0" data-tip="${esc(text)}"></span>`;
    }).join("");
    return `<div class="feature-row">
      <span>${esc(label)} <b>${count}</b></span>
      <div class="feature-cells" style="--track-count:${Math.max(1, tracks.length)}">${cells}</div>
    </div>`;
  }

  function visualEmpty(title, tip) {
    return `<article class="visual-card wide">
      <h3>${esc(title)} <span class="tip" tabindex="0" data-tip="${esc(tip)}">?</span></h3>
      <p class="empty">No measured audio data</p>
    </article>`;
  }

  function feature(row, name) {
    return row.resolved && row.resolved[name] ? row.resolved[name] : null;
  }

  function numericFeature(row, name) {
    const item = feature(row, name);
    const number = Number(item && item.value);
    return Number.isFinite(number) ? number : null;
  }

  function shapeClass(row) {
    const value = feature(row, "structure");
    if (value && String(value.value).toLowerCase() === "loop") return "loop";
    if (value && String(value.value).toLowerCase() === "line") return "line";
    return row.has_audio ? "audio" : "missing";
  }

  function displayLabel(label) {
    const labels = {
      audio: "audio analysis",
      loop: "loop",
      line: "line",
    };
    return labels[label] || label;
  }

  window.CantabileVisuals = { setupViewTabs, renderAnalysisBoard };
}());
