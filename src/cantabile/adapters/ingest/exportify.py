"""Exportify CSV ingest adapter.

Parses an Exportify export into domain objects. Crucially, the nine Spotify
audio features become Observations tagged Provenance.SPOTIFY right here, so
the projection enters the system already marked as low-trust. Later an audio
analyzer can emit a higher-trust Observation of the same feature and the
resolver will prefer it, with the projection still on record.
"""

from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path

from cantabile.domain.models import Playlist, PlaylistEntry, Track
from cantabile.domain.observation import Observation
from cantabile.domain.value_objects import Confidence, Provenance, TrackId

# Spotify feature columns -> (feature name, unit)
_FEATURES = {
    "Tempo": ("tempo", "bpm"),
    "Energy": ("energy", None),
    "Valence": ("valence", None),
    "Danceability": ("danceability", None),
    "Acousticness": ("acousticness", None),
    "Instrumentalness": ("instrumentalness", None),
    "Liveness": ("liveness", None),
    "Speechiness": ("speechiness", None),
    "Loudness": ("loudness", "db"),
    "Key": ("key", None),
    "Mode": ("mode", None),
    "Time Signature": ("time_signature", None),
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _parse_dt(s: str | None):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def read_playlist(csv_path: str | Path) -> tuple[Playlist, list[Track], list[Observation]]:
    """Return (playlist, tracks, spotify_observations) from an Exportify CSV."""
    path = Path(csv_path)
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"empty CSV: {path}")

    lookup = {_norm(c): c for c in rows[0].keys()}

    def col(*cands: str):
        for c in cands:
            if _norm(c) in lookup:
                return lookup[_norm(c)]
        return None

    c_uri = col("Track URI", "Spotify URI", "URI")
    c_title = col("Track Name", "Track", "Name")
    c_artist = col("Artist Name(s)", "Artist", "Artists")
    c_album = col("Album Name", "Album")
    c_rel = col("Release Date")
    c_dur = col("Duration (ms)", "Duration")
    c_added = col("Added At")
    if not (c_title and c_artist):
        raise ValueError(f"missing Track/Artist columns; found {list(rows[0])}")

    name = path.stem
    tracks: list[Track] = []
    entries: list[PlaylistEntry] = []
    observations: list[Observation] = []

    for i, row in enumerate(rows):
        uri = (row.get(c_uri) or "").strip() if c_uri else ""
        tid = TrackId(uri or f"local:{name}:{i}")
        artists = [a.strip() for a in re.split(r"[;,]", row.get(c_artist, "")) if a.strip()]
        dur_ms = None
        if c_dur and row.get(c_dur):
            try:
                dur_ms = int(float(row[c_dur]))
            except ValueError:
                dur_ms = None
        tracks.append(Track(
            id=tid, title=row.get(c_title, "").strip(), artists=artists,
            album=(row.get(c_album) or None) if c_album else None,
            release_date=(row.get(c_rel) or None) if c_rel else None,
            duration_ms=dur_ms))
        entries.append(PlaylistEntry(
            position=i, track_id=tid,
            added_at=_parse_dt(row.get(c_added)) if c_added else None))

        for raw_col, (feat, unit) in _FEATURES.items():
            real = lookup.get(_norm(raw_col))
            if not real or row.get(real) in (None, ""):
                continue
            try:
                val = float(row[real])
            except ValueError:
                continue
            observations.append(Observation(
                track_id=tid, feature=feat, value=val, source=Provenance.SPOTIFY,
                confidence=Confidence.MEDIUM, unit=unit))

    playlist = Playlist(name=name, entries=entries, source="exportify")
    return playlist, tracks, observations
