"""MIR analyzer test on a synthetic click track.

Generates a 12-second click train at a known tempo, writes a wav, and runs the
analyzer on it. Asserts it emits a positive felt tempo and a competing "tempo"
Observation tagged audio-provenance. No external audio, no network.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
sf = pytest.importorskip("soundfile")
pytest.importorskip("librosa")

from cantabile.adapters.analyzers.mir import MIRAnalyzer
from cantabile.domain.models import AudioAsset, Track
from cantabile.domain.value_objects import Confidence, Provenance, TrackId


def _click_track(path: Path, bpm: float = 120.0, seconds: float = 12.0, sr: int = 22050):
    n = int(seconds * sr)
    y = np.zeros(n, dtype=np.float32)
    step = int(sr * 60.0 / bpm)
    click = np.hanning(64).astype(np.float32)
    for start in range(0, n - 64, step):
        y[start:start + 64] += click
    sf.write(str(path), y, sr)


def test_mir_emits_tempo_and_structure():
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "click.wav"
        _click_track(wav, bpm=120.0)
        track = Track(id=TrackId("spotify:track:c"), title="Click", artists=["Synth"],
                      duration_ms=12000)
        asset = AudioAsset(track_id=track.id, source=Provenance.AUDIO,
                           source_url="local", file_path=str(wav))
        obs = MIRAnalyzer().analyze(track, asset)
        by_feature = {o.feature: o for o in obs}
        assert "felt_tempo" in by_feature
        assert by_feature["felt_tempo"].value > 0
        # MIR emits a "tempo" that outranks the Spotify projection
        assert "tempo" in by_feature
        assert by_feature["tempo"].source is Provenance.AUDIO
        assert by_feature["tempo"].confidence is Confidence.HIGH
