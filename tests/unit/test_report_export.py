"""Report and export tests."""

from __future__ import annotations

import csv
from argparse import Namespace

from cantabile.adapters.export.filesystem import FilesystemReportWriter
from cantabile.adapters.store.sqlite_store import SqliteStore
from cantabile.application.use_cases.report import build_playlist_report
from cantabile.domain.models import AudioAsset, Playlist, PlaylistEntry, Track
from cantabile.domain.observation import Observation
from cantabile.domain.value_objects import Confidence, Provenance, TrackId
from cantabile.presentation.cli.app import cmd_export
from cantabile.shared.settings import Settings


def _seed_store(path) -> SqliteStore:
    store = SqliteStore(path)
    tid = TrackId("spotify:track:one")
    track = Track(
        id=tid,
        title="A <Track>",
        artists=["One & Two"],
        album="Angles",
        release_date="2024",
        duration_ms=180000,
    )
    store.upsert_track(track)
    store.upsert_playlist(Playlist("Mini", [PlaylistEntry(0, tid)]))
    store.add_observation(Observation(tid, "tempo", 160.0, Provenance.SPOTIFY, unit="bpm"))
    store.add_observation(
        Observation(tid, "tempo", 108.0, Provenance.AUDIO, Confidence.HIGH, "bpm")
    )
    store.add_observation(Observation(tid, "lyrics", "hello <world>", Provenance.LYRICS_LRCLIB))
    store.upsert_asset(
        AudioAsset(
            track_id=tid,
            source=Provenance.AUDIO,
            source_url="https://example.test/audio",
            file_path="/tmp/audio.wav",
            duration_sec=181.2,
            match_confidence=Confidence.HIGH,
        )
    )
    store.set_stems(tid, {"drums": "/tmp/drums.flac"})
    return store


def test_report_resolves_audio_tempo_and_missing_fields(tmp_path):
    store = _seed_store(tmp_path / "cantabile.db")
    missing = TrackId("spotify:track:missing")
    store.upsert_playlist(Playlist("Mixed", [PlaylistEntry(0, missing)]))

    report = build_playlist_report(store.get_playlist("Mini"), store)
    row = report.tracks[0]
    assert report.schema_version == "cantabile.report.v1"
    assert row.resolved["tempo"].source == "audio"
    assert row.resolved["tempo"].value == 108.0
    assert row.has_audio is True
    assert row.lyrics_status == "present"
    assert row.stems == {"drums": "/tmp/drums.flac"}

    missing_report = build_playlist_report(store.get_playlist("Mixed"), store)
    missing_row = missing_report.tracks[0]
    assert missing_row.missing_track is True
    assert missing_row.has_audio is False
    assert missing_row.lyrics_status == "missing"
    assert missing_row.stems == {}
    store.close()


def test_iter_playlists_and_filesystem_writer(tmp_path):
    store = _seed_store(tmp_path / "cantabile.db")
    store.upsert_playlist(Playlist("Another", []))
    assert [playlist.name for playlist in store.iter_playlists()] == ["Another", "Mini"]

    report = build_playlist_report(store.get_playlist("Mini"), store)
    result = FilesystemReportWriter().write(report, tmp_path / "reports")
    assert result.tracks_csv.exists()
    assert result.observations_csv.exists()
    assert result.html_report.exists()

    html = result.html_report.read_text(encoding="utf-8")
    assert "A &lt;Track&gt;" in html
    assert "One &amp; Two" in html
    with result.tracks_csv.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["resolved_tempo"] == "108.0"
    assert rows[0]["resolved_tempo_source"] == "audio"
    store.close()


def test_cli_export_smoke(tmp_path, capsys):
    store = _seed_store(tmp_path / "cantabile.db")
    store.close()
    settings = Settings(db_path=str(tmp_path / "cantabile.db"), reports_dir=str(tmp_path / "reports"))
    cmd_export(Namespace(playlist="Mini", out=None), settings)
    output = capsys.readouterr().out
    assert "Exported 'Mini'" in output
    assert (tmp_path / "reports" / "Mini" / "tracks.csv").exists()
    assert (tmp_path / "reports" / "Mini" / "report.html").exists()
