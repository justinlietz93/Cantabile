"""Use case: separate every fetched track in a playlist into stems.

Pure orchestration over ports. For each track that has a downloaded audio asset
and no stems yet, run the separator and record the stem paths in the store.
Resumable: a track that already has stems is skipped unless forced. This is a
heavy, deliberate stage, run it once per playlist and the results are cached.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cantabile.domain.models import Playlist
from cantabile.ports.separator import SeparatorPort
from cantabile.ports.store import StorePort


@dataclass
class SeparateOutcome:
    seq: int
    artist: str
    title: str
    stems: int = 0
    status: str = ""


def separate_playlist(
    playlist: Playlist,
    store: StorePort,
    separator: SeparatorPort,
    out_dir: Path,
    force: bool = False,
) -> list[SeparateOutcome]:
    out_dir.mkdir(parents=True, exist_ok=True)
    outcomes: list[SeparateOutcome] = []
    for entry in playlist.entries:
        track = store.get_track(entry.track_id)
        if track is None:
            continue
        oc = SeparateOutcome(entry.position + 1, track.primary_artist, track.title)
        asset = store.get_asset(track.id)
        if not asset or not asset.file_path or not Path(asset.file_path).exists():
            oc.status = "no-audio"
            outcomes.append(oc)
            continue
        if not force and store.get_stems(track.id):
            oc.status = "skipped-existing"
            oc.stems = len(store.get_stems(track.id))
            outcomes.append(oc)
            continue
        try:
            stems = separator.separate(Path(asset.file_path), out_dir)
            store.set_stems(track.id, stems)
            oc.stems, oc.status = len(stems), "separated"
        except Exception as e:  # noqa: BLE001 - report, keep going
            oc.status = f"failed: {e}"
        outcomes.append(oc)
    return outcomes
