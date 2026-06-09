"""Use case: persist an already-parsed playlist into the store.

Pure orchestration: imports only domain and the StorePort. The actual CSV
parsing is an adapter concern (cantabile.adapters.ingest.exportify) and is
performed by the composition root, which then hands the domain objects here.
This keeps the application layer free of any concrete I/O, enforced by the
import contract.
"""

from __future__ import annotations

from cantabile.domain.models import Playlist, Track
from cantabile.domain.observation import Observation
from cantabile.ports.store import StorePort


def persist_import(
    playlist: Playlist,
    tracks: list[Track],
    observations: list[Observation],
    store: StorePort,
) -> str:
    for t in tracks:
        store.upsert_track(t)
    store.upsert_playlist(playlist)
    for o in observations:
        store.add_observation(o)
    return playlist.name
