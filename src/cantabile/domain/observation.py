"""The Observation: the universal unit of knowledge about a track.

Every fact Cantabile learns is an Observation. Spotify's tempo, the audio's
felt tempo, a lyric, a section count: all are Observations of some feature,
each tagged with where it came from and how confident we are. Multiple
Observations of the same feature coexist. `resolve` picks the trusted one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from cantabile.domain.value_objects import Confidence, Provenance, TrackId


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Observation:
    track_id: TrackId
    feature: str                       # e.g. "tempo", "energy", "section_count"
    value: Any                         # JSON-serialisable scalar or structure
    source: Provenance
    confidence: Confidence = Confidence.MEDIUM
    unit: Optional[str] = None         # e.g. "bpm"
    analyzer_version: Optional[str] = None
    observed_at: datetime = field(default_factory=_now)


def resolve(observations: Iterable[Observation], feature: str) -> Optional[Observation]:
    """Return the most trustworthy Observation of `feature`.

    Highest provenance trust wins; ties break on recency. Returns None if the
    feature was never observed. This is how a consumer asks for "the tempo"
    and gets the audio-derived value over the Spotify projection automatically.
    """
    candidates = [o for o in observations if o.feature == feature]
    if not candidates:
        return None
    return max(candidates, key=lambda o: (o.source.trust, o.observed_at))
