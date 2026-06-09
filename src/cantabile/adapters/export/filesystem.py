"""Filesystem report writer adapter."""

from __future__ import annotations

import csv
import json
import re
from html import escape
from pathlib import Path
from typing import Any

from cantabile.ports.report import PlaylistReport, ReportWriteResult


class FilesystemReportWriter:
    """Write Cantabile report artifacts to a local folder."""

    def write(self, report: PlaylistReport, out_dir: Path) -> ReportWriteResult:
        target = out_dir / _slug(report.playlist_name)
        target.mkdir(parents=True, exist_ok=True)
        tracks_csv = target / "tracks.csv"
        observations_csv = target / "observations.csv"
        html_report = target / "report.html"
        _write_tracks_csv(report, tracks_csv)
        _write_observations_csv(report, observations_csv)
        html_report.write_text(_render_html(report), encoding="utf-8")
        return ReportWriteResult(target, tracks_csv, observations_csv, html_report)


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip()).strip("_")
    return cleaned or "playlist"


def _value_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _feature_columns(report: PlaylistReport) -> list[str]:
    seen: set[str] = set()
    for row in report.tracks:
        seen.update(row.resolved)
    return sorted(seen)


def _write_tracks_csv(report: PlaylistReport, path: Path) -> None:
    features = _feature_columns(report)
    fields = [
        "seq",
        "track_id",
        "title",
        "artists",
        "album",
        "release_date",
        "duration_ms",
        "has_audio",
        "asset_confidence",
        "asset_path",
        "asset_url",
        "stems",
        "lyrics_status",
    ]
    fields.extend(f"resolved_{feature}" for feature in features)
    fields.extend(f"resolved_{feature}_source" for feature in features)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in report.tracks:
            item = {
                "seq": row.seq,
                "track_id": row.track_id,
                "title": row.title,
                "artists": row.artist_display,
                "album": row.album,
                "release_date": row.release_date,
                "duration_ms": row.duration_ms or "",
                "has_audio": "yes" if row.has_audio else "no",
                "asset_confidence": row.asset_confidence or "missing",
                "asset_path": row.asset_path,
                "asset_url": row.asset_url,
                "stems": json.dumps(row.stems, ensure_ascii=False) if row.stems else "",
                "lyrics_status": row.lyrics_status,
            }
            for feature in features:
                resolved = row.resolved.get(feature)
                item[f"resolved_{feature}"] = _value_text(resolved.value if resolved else None)
                item[f"resolved_{feature}_source"] = resolved.source if resolved else ""
            writer.writerow(item)


def _write_observations_csv(report: PlaylistReport, path: Path) -> None:
    fields = [
        "seq",
        "track_id",
        "title",
        "feature",
        "value",
        "source",
        "confidence",
        "unit",
        "analyzer_version",
        "observed_at",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in report.tracks:
            for obs in row.observations:
                writer.writerow({
                    "seq": row.seq,
                    "track_id": row.track_id,
                    "title": row.title,
                    "feature": obs.feature,
                    "value": _value_text(obs.value),
                    "source": obs.source,
                    "confidence": obs.confidence,
                    "unit": obs.unit,
                    "analyzer_version": obs.analyzer_version,
                    "observed_at": obs.observed_at,
                })


def _render_html(report: PlaylistReport) -> str:
    summary = report.summary
    rows = "\n".join(_track_row_html(row) for row in report.tracks)
    charts = "\n".join([
        _bars("Asset Confidence", summary.confidence_counts),
        _bars("Observation Provenance", summary.provenance_counts),
        _bars("Tempo Source", summary.tempo_source_counts),
        _bars("Structure", summary.structure_counts),
    ])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(report.playlist_name)} report</title>
  <style>{_CSS}</style>
</head>
<body>
  <header class="top">
    <div>
      <p class="eyebrow">Cantabile report</p>
      <h1>{escape(report.playlist_name)}</h1>
      <p class="meta">{escape(report.schema_version)} · generated {escape(report.generated_at)}</p>
    </div>
  </header>
  <main>
    <section class="metrics">
      {_metric("Tracks", summary.total_tracks)}
      {_metric("Audio", summary.audio_assets)}
      {_metric("Lyrics", summary.lyrics_tracks)}
      {_metric("MIR", summary.mir_tracks)}
      {_metric("Stemmed", summary.stemmed_tracks)}
    </section>
    <section class="charts">{charts}</section>
    <section class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th><th>Track</th><th>Tempo</th><th>Source</th><th>Audio</th>
            <th>Lyrics</th><th>Structure</th><th>Stems</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def _metric(label: str, value: int) -> str:
    return f'<article class="metric"><span>{escape(label)}</span><strong>{value}</strong></article>'


def _bars(title: str, counts: dict[str, int]) -> str:
    if not counts:
        return f'<article class="chart"><h2>{escape(title)}</h2><p class="empty">No data</p></article>'
    total = max(sum(counts.values()), 1)
    parts = []
    for label, value in sorted(counts.items()):
        pct = round((value / total) * 100, 1)
        parts.append(
            f'<div class="bar-row"><span>{escape(label)}</span><div class="bar">'
            f'<i style="width:{pct}%"></i></div><b>{value}</b></div>'
        )
    return f'<article class="chart"><h2>{escape(title)}</h2>{"".join(parts)}</article>'


def _track_row_html(row) -> str:
    tempo = row.resolved.get("tempo")
    structure = row.resolved.get("structure")
    stems = ", ".join(sorted(row.stems)) if row.stems else ""
    return f"""<tr>
  <td>{row.seq}</td>
  <td><strong>{escape(row.title)}</strong><small>{escape(row.artist_display)}</small></td>
  <td>{escape(_value_text(tempo.value if tempo else None))}</td>
  <td>{escape(tempo.source if tempo else "missing")}</td>
  <td><span class="pill {escape(row.asset_confidence or "missing")}">{escape(row.asset_confidence or "missing")}</span></td>
  <td>{escape(row.lyrics_status)}</td>
  <td>{escape(_value_text(structure.value if structure else None))}</td>
  <td>{escape(stems)}</td>
</tr>"""


_CSS = """
:root { color-scheme: light; --ink:#1c2429; --muted:#637078; --line:#d9e0e3;
  --paper:#f7f5f0; --panel:#ffffff; --accent:#2f6f73; --gold:#b9822b; }
* { box-sizing: border-box; }
body { margin:0; font:14px/1.45 Inter, ui-sans-serif, system-ui, -apple-system, sans-serif;
  color:var(--ink); background:var(--paper); }
.top { padding:32px clamp(20px,5vw,64px) 22px; border-bottom:1px solid var(--line);
  background:linear-gradient(135deg, #ffffff 0%, #edf5f3 100%); }
.eyebrow { margin:0 0 6px; color:var(--accent); text-transform:uppercase; letter-spacing:.08em;
  font-size:12px; font-weight:700; }
h1 { margin:0; font-size:clamp(30px,4vw,52px); letter-spacing:0; }
.meta { margin:8px 0 0; color:var(--muted); }
main { padding:24px clamp(20px,5vw,64px) 44px; }
.metrics { display:grid; grid-template-columns:repeat(auto-fit,minmax(135px,1fr)); gap:12px; }
.metric, .chart, .table-wrap { background:var(--panel); border:1px solid var(--line);
  border-radius:8px; box-shadow:0 10px 24px rgba(28,36,41,.05); }
.metric { padding:16px; min-height:86px; }
.metric span { display:block; color:var(--muted); }
.metric strong { display:block; margin-top:8px; font-size:30px; }
.charts { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:14px; margin-top:18px; }
.chart { padding:16px; min-height:150px; }
.chart h2 { margin:0 0 14px; font-size:16px; }
.bar-row { display:grid; grid-template-columns:94px 1fr 36px; gap:10px; align-items:center; margin:9px 0; }
.bar-row span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--muted); }
.bar { height:9px; background:#e7ecee; border-radius:999px; overflow:hidden; }
.bar i { display:block; height:100%; background:var(--accent); }
.empty { color:var(--muted); }
.table-wrap { margin-top:18px; overflow:auto; }
table { width:100%; border-collapse:collapse; min-width:860px; }
th, td { padding:12px 14px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }
th { font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; background:#fbfcfc; }
td small { display:block; color:var(--muted); margin-top:3px; }
.pill { display:inline-flex; align-items:center; min-width:68px; justify-content:center;
  border-radius:999px; padding:4px 9px; font-weight:700; background:#edf0f1; color:#536168; }
.pill.high, .pill.override { background:#dff1e8; color:#17613d; }
.pill.medium { background:#fff1d8; color:#805617; }
.pill.low { background:#fde5de; color:#9b3b25; }
"""
