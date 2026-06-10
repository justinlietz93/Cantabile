"""Report port and versioned export DTOs.

The application builds these transport-shaped objects from domain entities and
Observations. Presentation layers and concrete exporters consume this contract
instead of reaching into domain objects directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ReportObservation:
    """One stored Observation flattened for reporting/export."""

    feature: str
    value: Any
    source: str
    confidence: str
    unit: str = ""
    analyzer_version: str = ""
    observed_at: str = ""


@dataclass(frozen=True)
class ResolvedFeature:
    """The currently trusted value for a feature."""

    value: Any
    source: str
    confidence: str
    unit: str = ""
    analyzer_version: str = ""
    observed_at: str = ""


@dataclass(frozen=True)
class TrackReportRow:
    """A playlist-positioned track row for GUI, CSV, and HTML reports."""

    seq: int
    track_id: str
    title: str
    artists: list[str]
    album: str = ""
    release_date: str = ""
    duration_ms: int | None = None
    added_at: str = ""
    missing_track: bool = False
    asset_path: str = ""
    asset_url: str = ""
    asset_source: str = ""
    asset_confidence: str = ""
    asset_duration_sec: float | None = None
    has_audio: bool = False
    stems: dict[str, str] = field(default_factory=dict)
    lyrics_status: str = "missing"
    observations: list[ReportObservation] = field(default_factory=list)
    resolved: dict[str, ResolvedFeature] = field(default_factory=dict)

    @property
    def artist_display(self) -> str:
        """Return the artist list in a compact human-facing form."""
        return ", ".join(self.artists)


@dataclass(frozen=True)
class PlaylistReportSummary:
    """Aggregate counts for a playlist report."""

    total_tracks: int
    missing_tracks: int
    audio_assets: int
    stemmed_tracks: int
    lyrics_tracks: int
    mir_tracks: int
    lyrics_checked: int = 0
    confidence_counts: dict[str, int] = field(default_factory=dict)
    provenance_counts: dict[str, int] = field(default_factory=dict)
    structure_counts: dict[str, int] = field(default_factory=dict)
    tempo_source_counts: dict[str, int] = field(default_factory=dict)
    feature_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class PlaylistReport:
    """Versioned report contract for one playlist."""

    schema_version: str
    playlist_name: str
    playlist_source: str
    generated_at: str
    summary: PlaylistReportSummary
    tracks: list[TrackReportRow]


@dataclass(frozen=True)
class ReportWriteResult:
    """Paths produced by a report writer."""

    out_dir: Path
    tracks_csv: Path
    observations_csv: Path
    html_report: Path


@runtime_checkable
class ReportWriterPort(Protocol):
    """Persistence contract for rendered report artifacts."""

    def write(self, report: PlaylistReport, out_dir: Path) -> ReportWriteResult:
        """Write a report bundle and return produced artifact paths."""
        ...
