"""Domain entities.

These are the nouns of the system. They hold structure and identity, no
behaviour that touches the outside world. A Track is identified by its
TrackId and appears in many playlists; its position is a property of the
membership (PlaylistEntry), not of the track.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from cantabile.domain.value_objects import Confidence, Provenance, TrackId


@dataclass
class Track:
    id: TrackId
    title: str
    artists: list[str]
    album: Optional[str] = None
    release_date: Optional[str] = None
    duration_ms: Optional[int] = None

    @property
    def primary_artist(self) -> str:
        return self.artists[0] if self.artists else ""

    @property
    def duration_sec(self) -> Optional[float]:
        return self.duration_ms / 1000.0 if self.duration_ms else None


@dataclass
class PlaylistEntry:
    position: int                  # 0-based sequence in the playlist
    track_id: TrackId
    added_at: Optional[datetime] = None


@dataclass
class Playlist:
    name: str
    entries: list[PlaylistEntry] = field(default_factory=list)
    source: str = "exportify"

    @property
    def size(self) -> int:
        return len(self.entries)


@dataclass
class AudioAsset:
    """A resolved, downloaded audio file for a track, with provenance."""

    track_id: TrackId
    source: Provenance            # which site family it came from
    source_url: str
    file_path: Optional[str] = None
    duration_sec: Optional[float] = None
    match_confidence: Confidence = Confidence.NONE
    fetched_at: Optional[datetime] = None
