"""Use case: run analyzers over a playlist's tracks and persist Observations.

Generic and reusable: the same use case will drive the future MIR analyzer.
Pure orchestration over ports. Resumable, an analyzer that declares a `feature`
is skipped for any track that already has an Observation of that feature, so
reruns don't refetch or duplicate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cantabile.domain.models import Playlist
from cantabile.ports.analyzer import AnalyzerPort
from cantabile.ports.store import StorePort


@dataclass
class AnalyzeOutcome:
    seq: int
    artist: str
    title: str
    results: dict[str, int] = field(default_factory=dict)  # analyzer name -> obs count
    status: str = ""


def analyze_playlist(
    playlist: Playlist,
    store: StorePort,
    analyzers: list[AnalyzerPort],
    force: bool = False,
) -> list[AnalyzeOutcome]:
    outcomes: list[AnalyzeOutcome] = []
    for entry in playlist.entries:
        track = store.get_track(entry.track_id)
        if track is None:
            continue
        oc = AnalyzeOutcome(seq=entry.position + 1, artist=track.primary_artist,
                            title=track.title)
        asset = store.get_asset(track.id)
        if asset is not None:
            asset.stems = store.get_stems(track.id)   # let analyzers use stems if present
        for analyzer in analyzers:
            if not analyzer.applies_to(track, asset):
                continue
            feature = getattr(analyzer, "feature", None)
            if not force and feature and store.get_observations(track.id, feature):
                oc.results[analyzer.name] = 0
                oc.status = "skipped-existing"
                continue
            observations = analyzer.analyze(track, asset)
            for obs in observations:
                store.add_observation(obs)
            oc.results[analyzer.name] = len(observations)
        outcomes.append(oc)
    return outcomes
