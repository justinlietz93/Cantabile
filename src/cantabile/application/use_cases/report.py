"""Use case: build a versioned report read model for a playlist.

The report is a projection of stored Cantabile facts. It does not add new
scores or predictions; it resolves each feature through the existing
Observation trust rule and exposes the raw observations alongside that view.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from cantabile.domain.models import Playlist
from cantabile.domain.observation import Observation, resolve
from cantabile.domain.value_objects import TrackId
from cantabile.ports.report import (
    PlaylistReport,
    PlaylistReportSummary,
    ReportObservation,
    ResolvedFeature,
    TrackReportRow,
)
from cantabile.ports.store import StorePort

REPORT_SCHEMA_VERSION = "cantabile.report.v1"

REPORT_FEATURES = (
    "tempo",
    "felt_tempo",
    "tempo_variability",
    "tempo_min",
    "tempo_max",
    "section_count",
    "loop_score",
    "structure",
    "lyrics",
    "audio_duration",
    "energy",
    "valence",
    "danceability",
    "acousticness",
    "instrumentalness",
    "liveness",
    "speechiness",
    "loudness",
    "key",
    "mode",
    "time_signature",
)

_MIR_FEATURES = {
    "felt_tempo",
    "tempo_variability",
    "tempo_min",
    "tempo_max",
    "section_count",
    "loop_score",
    "structure",
}


def build_playlist_report(playlist: Playlist, store: StorePort) -> PlaylistReport:
    """Return a complete report DTO for one playlist."""

    tracks = [_build_track_row(entry.position + 1, entry.track_id.value, entry.added_at, store)
              for entry in playlist.entries]
    return PlaylistReport(
        schema_version=REPORT_SCHEMA_VERSION,
        playlist_name=playlist.name,
        playlist_source=playlist.source,
        generated_at=datetime.now(timezone.utc).isoformat(),
        summary=_summarize(tracks),
        tracks=tracks,
    )


def _build_track_row(seq: int, track_id: str, added_at: Any, store: StorePort) -> TrackReportRow:
    track = store.get_track(TrackId(track_id))
    if track is None:
        return TrackReportRow(
            seq=seq,
            track_id=track_id,
            title="",
            artists=[],
            added_at=added_at.isoformat() if added_at else "",
            missing_track=True,
        )

    observations = store.get_observations(track.id)
    asset = store.get_asset(track.id)
    stems = store.get_stems(track.id)
    resolved = _resolved_features(observations)
    lyrics = resolved.get("lyrics")
    return TrackReportRow(
        seq=seq,
        track_id=track.id.value,
        title=track.title,
        artists=track.artists,
        album=track.album or "",
        release_date=track.release_date or "",
        duration_ms=track.duration_ms,
        added_at=added_at.isoformat() if added_at else "",
        asset_path=asset.file_path if asset and asset.file_path else "",
        asset_url=asset.source_url if asset else "",
        asset_source=asset.source.value if asset else "",
        asset_confidence=asset.match_confidence.value if asset else "",
        asset_duration_sec=asset.duration_sec if asset else None,
        has_audio=bool(asset and asset.file_path),
        stems=stems,
        lyrics_status=_lyrics_status(lyrics),
        observations=[_observation_dto(o) for o in observations],
        resolved=resolved,
    )


def _resolved_features(observations: list[Observation]) -> dict[str, ResolvedFeature]:
    resolved: dict[str, ResolvedFeature] = {}
    for feature in REPORT_FEATURES:
        obs = resolve(observations, feature)
        if obs is not None:
            resolved[feature] = ResolvedFeature(
                value=obs.value,
                source=obs.source.value,
                confidence=obs.confidence.value,
                unit=obs.unit or "",
                analyzer_version=obs.analyzer_version or "",
                observed_at=obs.observed_at.isoformat(),
            )
    return resolved


def _observation_dto(obs: Observation) -> ReportObservation:
    return ReportObservation(
        feature=obs.feature,
        value=obs.value,
        source=obs.source.value,
        confidence=obs.confidence.value,
        unit=obs.unit or "",
        analyzer_version=obs.analyzer_version or "",
        observed_at=obs.observed_at.isoformat(),
    )


def _lyrics_status(lyrics: ResolvedFeature | None) -> str:
    if lyrics is None:
        return "missing"
    value = str(lyrics.value).strip().lower()
    if value == "[instrumental]":
        return "instrumental"
    if value == "[not found]":
        return "none"
    return "present" if str(lyrics.value).strip() else "empty"


def _summarize(rows: list[TrackReportRow]) -> PlaylistReportSummary:
    confidence: Counter[str] = Counter()
    provenance: Counter[str] = Counter()
    structures: Counter[str] = Counter()
    tempo_sources: Counter[str] = Counter()
    features: Counter[str] = Counter()

    for row in rows:
        confidence[row.asset_confidence or "missing"] += 1
        tempo = row.resolved.get("tempo")
        tempo_sources[tempo.source if tempo else "missing"] += 1
        structure = row.resolved.get("structure")
        if structure:
            structures[str(structure.value)] += 1
        for obs in row.observations:
            provenance[obs.source] += 1
            features[obs.feature] += 1

    return PlaylistReportSummary(
        total_tracks=len(rows),
        missing_tracks=sum(1 for row in rows if row.missing_track),
        audio_assets=sum(1 for row in rows if row.has_audio),
        stemmed_tracks=sum(1 for row in rows if row.stems),
        lyrics_tracks=sum(1 for row in rows if row.lyrics_status in {"present", "instrumental"}),
        lyrics_checked=sum(1 for row in rows if row.lyrics_status in {"present", "instrumental", "none"}),
        mir_tracks=sum(1 for row in rows if any(f in row.resolved for f in _MIR_FEATURES)),
        confidence_counts=dict(confidence),
        provenance_counts=dict(provenance),
        structure_counts=dict(structures),
        tempo_source_counts=dict(tempo_sources),
        feature_counts=dict(features),
    )
