"""Domain value objects.

Pure, immutable building blocks with no dependencies on any other layer.
Provenance and trust ranking live here because they are core domain concepts:
a Spotify-reported number and an audio-derived number are both facts, but they
are not equally trusted. The store keeps both; the resolver prefers the higher
rank. This is the "Spotify is a lossy projection" thesis expressed as a type.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class TrackId:
    """Stable identity for a track. The Spotify URI is the natural key because
    it links the same recording across every playlist in the corpus."""

    value: str

    @classmethod
    def from_uri(cls, uri: str) -> "TrackId":
        return cls(uri.strip())

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class Provenance(str, Enum):
    """Where a fact came from. Ordering encodes trust, not chronology."""

    MANUAL = "manual"            # a human pinned it; highest authority
    AUDIO = "audio"             # measured from the waveform (MIR)
    LYRICS_LRCLIB = "lrclib"
    LYRICS_GENIUS = "genius"
    SPOTIFY = "spotify"         # the projection; kept, but lowest trust

    @property
    def trust(self) -> int:
        return _TRUST_RANK[self]


_TRUST_RANK = {
    Provenance.MANUAL: 100,
    Provenance.AUDIO: 80,
    Provenance.LYRICS_LRCLIB: 60,
    Provenance.LYRICS_GENIUS: 55,
    Provenance.SPOTIFY: 10,
}


class Confidence(str, Enum):
    """Match / measurement confidence, shared across providers and analyzers."""

    OVERRIDE = "override"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"
