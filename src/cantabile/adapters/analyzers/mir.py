"""MIR analyzer: measures structure from the waveform.

Implements AnalyzerPort. Given a track's downloaded AudioAsset it computes the
felt tempo (which corrects Spotify's often-wrong number), how much that tempo
breathes, how many sections the piece has, and whether it closes back on itself
(loop) or moves in one direction (line). Each is emitted as an audio-provenance
Observation, so the resolver prefers these over the Spotify projection.

Requires the optional extra:  pip install -e ".[audio]"   (and ffmpeg on PATH)
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional

import librosa
import numpy as np
from scipy.signal import find_peaks
from scipy.spatial.distance import cdist

from cantabile.domain.models import AudioAsset, Track
from cantabile.domain.observation import Observation
from cantabile.domain.value_objects import Confidence, Provenance

_SR = 22050
_HOP = 512


class MIRAnalyzer:
    name = "mir"
    feature = "felt_tempo"   # sentinel the use case checks for "already analyzed"

    def applies_to(self, track: Track, asset: Optional[AudioAsset]) -> bool:
        return bool(asset and asset.file_path and Path(asset.file_path).exists())

    def analyze(self, track: Track, asset: Optional[AudioAsset]) -> list[Observation]:
        if not self.applies_to(track, asset):
            return []
        assert asset is not None and asset.file_path is not None
        warnings.filterwarnings("ignore")

        # Prefer stems when present: drums drive tempo, the harmonic bed drives
        # structure. Falls back to the full mix when stems aren't available.
        stems = asset.stems or {}
        tempo_src = stems.get("drums") or asset.file_path
        struct_src = stems.get("other") or stems.get("no_drums") or asset.file_path
        version = "mir/1+stems" if stems else "mir/1"

        def load(path):
            try:
                y, _ = librosa.load(path, sr=_SR, mono=True)
                return y
            except Exception:  # noqa: BLE001
                return None

        y_tempo = load(tempo_src)
        if y_tempo is None or y_tempo.size < _SR * 5:
            return []

        def obs(feature, value, unit=None, conf=Confidence.HIGH):
            return Observation(track_id=track.id, feature=feature, value=value,
                               source=Provenance.AUDIO, confidence=conf, unit=unit,
                               analyzer_version=version)

        out: list[Observation] = []

        # ---- tempo: from the drum stem if we have it --------------------- #
        oenv = librosa.onset.onset_strength(y=y_tempo, sr=_SR, hop_length=_HOP)
        dtempo = librosa.feature.tempo(onset_envelope=oenv, sr=_SR, hop_length=_HOP,
                                       aggregate=None)
        felt = float(np.median(dtempo))
        out.append(obs("felt_tempo", round(felt, 1), "bpm"))
        out.append(obs("tempo", round(felt, 1), "bpm"))   # outranks Spotify's tempo
        out.append(obs("tempo_variability", round(float(dtempo.std()), 1), "bpm"))
        out.append(obs("tempo_min", round(float(dtempo.min()), 1), "bpm"))
        out.append(obs("tempo_max", round(float(dtempo.max()), 1), "bpm"))

        # ---- structure: from the harmonic bed if we have it -------------- #
        y_struct = load(struct_src) if struct_src != tempo_src else y_tempo
        if y_struct is None:
            y_struct = y_tempo
        soenv = librosa.onset.onset_strength(y=y_struct, sr=_SR, hop_length=_HOP)
        _, beats = librosa.beat.beat_track(onset_envelope=soenv, sr=_SR, hop_length=_HOP)
        if len(beats) >= 24:
            beat_frames = [int(b) for b in beats]
            chroma = librosa.feature.chroma_cqt(y=y_struct, sr=_SR, hop_length=_HOP)
            mfcc = librosa.feature.mfcc(y=y_struct, sr=_SR, hop_length=_HOP, n_mfcc=13)
            cs = librosa.util.sync(chroma, beat_frames, aggregate=np.median)
            ms = librosa.util.sync(mfcc, beat_frames, aggregate=np.mean)
            feat = np.vstack([librosa.util.normalize(cs, axis=0),
                              librosa.util.normalize(ms, axis=0)])
            n = feat.shape[1]
            ssm = 1.0 - cdist(feat.T, feat.T, metric="cosine")
            out.append(obs("section_count", self._section_count(ssm, n)))
            loop_z = self._loop_z(feat, n)
            out.append(obs("loop_score", round(loop_z, 2)))
            out.append(obs("structure", "loop" if loop_z > 0.5 else "line",
                           conf=Confidence.MEDIUM))

        return out

    # ------------------------------------------------------------------ #
    @staticmethod
    def _section_count(ssm: np.ndarray, n: int) -> int:
        L = min(16, max(4, n // 8))
        kernel = np.outer(np.sign(np.arange(-L, L + 1)),
                          np.sign(np.arange(-L, L + 1))).astype(float)
        win = np.hanning(2 * L + 1)
        kernel *= np.outer(win, win)
        padded = np.pad(ssm, L, mode="edge")
        nov = np.zeros(n)
        for i in range(n):
            nov[i] = np.sum(padded[i:i + 2 * L + 1, i:i + 2 * L + 1] * kernel)
        nov = np.maximum(nov, 0.0)
        if nov.max() > 0:
            nov /= nov.max()
        peaks, _ = find_peaks(nov, height=0.35, distance=max(8, n // 24))
        return int(len(peaks) + 1)

    @staticmethod
    def _loop_z(feat: np.ndarray, n: int) -> float:
        k = max(4, n // 12)
        head = feat[:, :k].mean(axis=1)
        tail = feat[:, -k:].mean(axis=1)

        def cos(a, b):
            return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

        loop_sim = cos(head, tail)
        rng = np.random.default_rng(0)
        base = np.array([cos(head, feat[:, i:i + k].mean(axis=1))
                         for i in (rng.integers(0, n - k) for _ in range(200))])
        spread = base.std() or 1e-9
        return (loop_sim - base.mean()) / spread
