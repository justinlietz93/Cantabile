"""Stem-separation tests: store roundtrip, MIR drum-stem preference, Demucs
command building and output location. No real Demucs run (it needs torch and
minutes of CPU); the heavy path is exercised on the user's machine.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

sf = pytest.importorskip("soundfile")
pytest.importorskip("librosa")

from cantabile.adapters.analyzers.mir import MIRAnalyzer
from cantabile.adapters.separators.demucs import DemucsSeparator
from cantabile.adapters.store.sqlite_store import SqliteStore
from cantabile.domain.models import AudioAsset, Track
from cantabile.domain.value_objects import Provenance, TrackId


def _click(path: Path, bpm: float, seconds: float = 14.0, sr: int = 22050):
    n = int(seconds * sr)
    y = np.zeros(n, dtype=np.float32)
    step = int(sr * 60.0 / bpm)
    click = np.hanning(64).astype(np.float32)
    for s in range(0, n - 64, step):
        y[s:s + 64] += click
    sf.write(str(path), y, sr)


def test_stems_store_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        store = SqliteStore(Path(d) / "s.db")
        tid = TrackId("spotify:track:s")
        store.set_stems(tid, {"drums": "/x/drums.flac", "other": "/x/other.flac"})
        got = store.get_stems(tid)
        assert got == {"drums": "/x/drums.flac", "other": "/x/other.flac"}
        store.close()


def test_mir_prefers_drum_stem_for_tempo():
    with tempfile.TemporaryDirectory() as d:
        mix = Path(d) / "mix.wav"
        drums = Path(d) / "drums.wav"
        _click(mix, bpm=90.0)      # the full mix pulse
        _click(drums, bpm=150.0)   # the drum stem pulse (clearly different)
        track = Track(id=TrackId("spotify:track:d"), title="T", artists=["A"],
                      duration_ms=14000)
        asset = AudioAsset(track_id=track.id, source=Provenance.AUDIO, source_url="local",
                           file_path=str(mix), stems={"drums": str(drums)})
        by = {o.feature: o for o in MIRAnalyzer().analyze(track, asset)}
        # tempo should reflect the 150 drum stem, not the 90 mix
        assert by["felt_tempo"].value > 120
        assert by["felt_tempo"].analyzer_version == "mir/1+stems"


def test_demucs_command_and_locate():
    sep = DemucsSeparator(model="htdemucs", device="cpu", segment=7.0, fmt="flac")
    cmd = sep.build_command(Path("/music/song.wav"), Path("/out"))
    assert "-n" in cmd and "htdemucs" in cmd
    assert "-d" in cmd and "cpu" in cmd
    assert "--segment" in cmd and "--flac" in cmd
    assert cmd[-1] == "/music/song.wav"

    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        track_dir = out / "htdemucs" / "song"
        track_dir.mkdir(parents=True)
        for stem in ("drums", "bass", "vocals", "other"):
            (track_dir / f"{stem}.flac").write_bytes(b"x")
        stems = DemucsSeparator.locate_stems(out, "htdemucs", Path("/music/song.wav"))
        assert set(stems) == {"drums", "bass", "vocals", "other"}
        assert stems["drums"].endswith("htdemucs/song/drums.flac")
