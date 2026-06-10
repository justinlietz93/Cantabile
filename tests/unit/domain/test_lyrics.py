"""Lyrics analyzer wiring test (no network).

Seeds the on-disk cache with a placeholder so analyze() returns from cache and
never touches LRCLIB or Genius. Verifies the Observation it emits carries the
right feature, value, and provenance.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("requests")
pytest.importorskip("bs4")

from cantabile.adapters.analyzers.lyrics import LyricsAnalyzer
from cantabile.domain.models import Track
from cantabile.domain.value_objects import Confidence, Provenance, TrackId


def test_lyrics_from_cache_emits_observation():
    track = Track(id=TrackId("spotify:track:9"), title="Placeholder Song",
                  artists=["Test Artist"], album="Test Album", duration_ms=180000)
    with tempfile.TemporaryDirectory() as d:
        cache_path = Path(d) / "cache.json"
        key = ("test artist|||placeholder song|||test album|||180")
        cache_path.write_text(json.dumps(
            {key: {"lyrics": "placeholder lyric body for test", "source": "lrclib"}}),
            encoding="utf-8")

        analyzer = LyricsAnalyzer(cache_path=str(cache_path))
        obs = analyzer.analyze(track, None)
        assert len(obs) == 1
        assert obs[0].feature == "lyrics"
        assert obs[0].source is Provenance.LYRICS_LRCLIB
        assert obs[0].value == "placeholder lyric body for test"


def test_instrumental_from_cache():
    track = Track(id=TrackId("spotify:track:10"), title="Mobius",
                  artists=["Chimp Spanner"], duration_ms=268000)
    with tempfile.TemporaryDirectory() as d:
        cache_path = Path(d) / "cache.json"
        key = "chimp spanner|||mobius||||268"
        cache_path.write_text(json.dumps(
            {key: {"lyrics": "[instrumental]", "source": "lrclib"}}), encoding="utf-8")
        analyzer = LyricsAnalyzer(cache_path=str(cache_path))
        obs = analyzer.analyze(track, None)
        assert obs and obs[0].value == "[instrumental]"


def test_miss_records_not_found_marker():
    track = Track(id=TrackId("spotify:track:11"), title="No Lyrics Here",
                  artists=["Nobody"], duration_ms=120000)
    with tempfile.TemporaryDirectory() as d:
        cache_path = Path(d) / "cache.json"
        key = "nobody|||no lyrics here||||120"
        cache_path.write_text(json.dumps({key: {"lyrics": "", "source": ""}}), encoding="utf-8")
        analyzer = LyricsAnalyzer(cache_path=str(cache_path))
        obs = analyzer.analyze(track, None)
        assert len(obs) == 1
        assert obs[0].value == "[not found]"
        assert obs[0].confidence is Confidence.NONE
