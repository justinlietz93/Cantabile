"""SQLite adapter implementing StorePort.

This is the source of truth. CSV is import/export only. One local file holds
tracks, playlists, observations, and audio assets, so corpus-wide questions
("which playlists loop", "every track with high tempo variance") become
queries instead of impossible scatter-gather across CSVs.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from cantabile.domain.models import AudioAsset, Playlist, PlaylistEntry, Track
from cantabile.domain.observation import Observation
from cantabile.domain.value_objects import Confidence, Provenance, TrackId

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id TEXT PRIMARY KEY, title TEXT, artists_json TEXT,
    album TEXT, release_date TEXT, duration_ms INTEGER
);
CREATE TABLE IF NOT EXISTS playlists (
    name TEXT PRIMARY KEY, source TEXT
);
CREATE TABLE IF NOT EXISTS playlist_entries (
    playlist_name TEXT, position INTEGER, track_id TEXT, added_at TEXT,
    PRIMARY KEY (playlist_name, position)
);
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id TEXT, feature TEXT, value_json TEXT, source TEXT,
    confidence TEXT, unit TEXT, analyzer_version TEXT, observed_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_obs_track_feature ON observations (track_id, feature);
CREATE TABLE IF NOT EXISTS assets (
    track_id TEXT PRIMARY KEY, source TEXT, source_url TEXT, file_path TEXT,
    duration_sec REAL, match_confidence TEXT, fetched_at TEXT
);
CREATE TABLE IF NOT EXISTS stems (
    track_id TEXT, stem_name TEXT, file_path TEXT,
    PRIMARY KEY (track_id, stem_name)
);
"""


def _dt(s: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(s) if s else None


class SqliteStore:
    def __init__(self, path: str | Path) -> None:
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ---- tracks ----------------------------------------------------------- #
    def upsert_track(self, t: Track) -> None:
        self._conn.execute(
            "INSERT INTO tracks (id,title,artists_json,album,release_date,duration_ms) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
            "title=excluded.title, artists_json=excluded.artists_json, album=excluded.album, "
            "release_date=excluded.release_date, duration_ms=excluded.duration_ms",
            (t.id.value, t.title, json.dumps(t.artists), t.album, t.release_date, t.duration_ms),
        )
        self._conn.commit()

    def _row_to_track(self, r: sqlite3.Row) -> Track:
        return Track(TrackId(r["id"]), r["title"], json.loads(r["artists_json"] or "[]"),
                     r["album"], r["release_date"], r["duration_ms"])

    def get_track(self, track_id: TrackId) -> Optional[Track]:
        r = self._conn.execute("SELECT * FROM tracks WHERE id=?", (track_id.value,)).fetchone()
        return self._row_to_track(r) if r else None

    def iter_tracks(self) -> Iterable[Track]:
        for r in self._conn.execute("SELECT * FROM tracks"):
            yield self._row_to_track(r)

    # ---- playlists -------------------------------------------------------- #
    def upsert_playlist(self, p: Playlist) -> None:
        self._conn.execute(
            "INSERT INTO playlists (name,source) VALUES (?,?) "
            "ON CONFLICT(name) DO UPDATE SET source=excluded.source", (p.name, p.source))
        self._conn.execute("DELETE FROM playlist_entries WHERE playlist_name=?", (p.name,))
        self._conn.executemany(
            "INSERT INTO playlist_entries (playlist_name,position,track_id,added_at) VALUES (?,?,?,?)",
            [(p.name, e.position, e.track_id.value,
              e.added_at.isoformat() if e.added_at else None) for e in p.entries])
        self._conn.commit()

    def get_playlist(self, name: str) -> Optional[Playlist]:
        head = self._conn.execute("SELECT * FROM playlists WHERE name=?", (name,)).fetchone()
        if not head:
            return None
        rows = self._conn.execute(
            "SELECT * FROM playlist_entries WHERE playlist_name=? ORDER BY position", (name,))
        entries = [PlaylistEntry(r["position"], TrackId(r["track_id"]), _dt(r["added_at"]))
                   for r in rows]
        return Playlist(name=head["name"], entries=entries, source=head["source"])

    # ---- observations ----------------------------------------------------- #
    def add_observation(self, o: Observation) -> None:
        self._conn.execute(
            "INSERT INTO observations "
            "(track_id,feature,value_json,source,confidence,unit,analyzer_version,observed_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (o.track_id.value, o.feature, json.dumps(o.value), o.source.value,
             o.confidence.value, o.unit, o.analyzer_version, o.observed_at.isoformat()))
        self._conn.commit()

    def get_observations(self, track_id: TrackId, feature: Optional[str] = None) -> list[Observation]:
        if feature:
            rows = self._conn.execute(
                "SELECT * FROM observations WHERE track_id=? AND feature=?",
                (track_id.value, feature))
        else:
            rows = self._conn.execute(
                "SELECT * FROM observations WHERE track_id=?", (track_id.value,))
        return [Observation(
            track_id=TrackId(r["track_id"]), feature=r["feature"],
            value=json.loads(r["value_json"]), source=Provenance(r["source"]),
            confidence=Confidence(r["confidence"]), unit=r["unit"],
            analyzer_version=r["analyzer_version"], observed_at=_dt(r["observed_at"])) for r in rows]

    # ---- assets ----------------------------------------------------------- #
    def upsert_asset(self, a: AudioAsset) -> None:
        self._conn.execute(
            "INSERT INTO assets (track_id,source,source_url,file_path,duration_sec,match_confidence,fetched_at) "
            "VALUES (?,?,?,?,?,?,?) ON CONFLICT(track_id) DO UPDATE SET "
            "source=excluded.source, source_url=excluded.source_url, file_path=excluded.file_path, "
            "duration_sec=excluded.duration_sec, match_confidence=excluded.match_confidence, "
            "fetched_at=excluded.fetched_at",
            (a.track_id.value, a.source.value, a.source_url, a.file_path, a.duration_sec,
             a.match_confidence.value, a.fetched_at.isoformat() if a.fetched_at else None))
        self._conn.commit()

    def get_asset(self, track_id: TrackId) -> Optional[AudioAsset]:
        r = self._conn.execute("SELECT * FROM assets WHERE track_id=?", (track_id.value,)).fetchone()
        if not r:
            return None
        return AudioAsset(TrackId(r["track_id"]), Provenance(r["source"]), r["source_url"],
                          r["file_path"], r["duration_sec"], Confidence(r["match_confidence"]),
                          _dt(r["fetched_at"]))

    # ---- stems ------------------------------------------------------------ #
    def set_stems(self, track_id: TrackId, stems: dict[str, str]) -> None:
        self._conn.execute("DELETE FROM stems WHERE track_id=?", (track_id.value,))
        self._conn.executemany(
            "INSERT INTO stems (track_id, stem_name, file_path) VALUES (?,?,?)",
            [(track_id.value, name, path) for name, path in stems.items()])
        self._conn.commit()

    def get_stems(self, track_id: TrackId) -> dict[str, str]:
        rows = self._conn.execute(
            "SELECT stem_name, file_path FROM stems WHERE track_id=?", (track_id.value,))
        return {r["stem_name"]: r["file_path"] for r in rows}

    def close(self) -> None:
        self._conn.close()
