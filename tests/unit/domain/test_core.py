"""Core behaviour tests: the trust resolver and a CSV->store roundtrip."""

from __future__ import annotations

import tempfile
from pathlib import Path

from cantabile.adapters.ingest.exportify import read_playlist
from cantabile.adapters.store.sqlite_store import SqliteStore
from cantabile.application.use_cases.import_playlist import persist_import
from cantabile.domain.observation import Observation, resolve
from cantabile.domain.value_objects import Confidence, Provenance, TrackId


def test_resolver_prefers_audio_over_spotify():
    tid = TrackId("spotify:track:x")
    obs = [
        Observation(tid, "tempo", 160.0, Provenance.SPOTIFY, Confidence.MEDIUM, "bpm"),
        Observation(tid, "tempo", 107.7, Provenance.AUDIO, Confidence.HIGH, "bpm"),
    ]
    winner = resolve(obs, "tempo")
    assert winner is not None
    assert winner.source is Provenance.AUDIO
    assert winner.value == 107.7


def test_import_roundtrip():
    csv = ("Track URI,Track Name,Artist Name(s),Duration (ms),Tempo,Energy\n"
           "spotify:track:1,Forever Flame,Miracle Of Sound,252000,95.0,0.75\n"
           "spotify:track:2,Mobius Pt I,Chimp Spanner,268000,160.0,0.77\n")
    with tempfile.TemporaryDirectory() as d:
        csv_path = Path(d) / "Mini.csv"
        csv_path.write_text(csv, encoding="utf-8")
        store = SqliteStore(Path(d) / "t.db")
        playlist, tracks, observations = read_playlist(csv_path)
        name = persist_import(playlist, tracks, observations, store)
        assert name == "Mini"
        assert store.get_playlist("Mini").size == 2
        assert store.get_track(TrackId("spotify:track:2")).primary_artist == "Chimp Spanner"
        tempo = store.get_observations(TrackId("spotify:track:1"), "tempo")
        assert tempo and tempo[0].source is Provenance.SPOTIFY
        store.close()
