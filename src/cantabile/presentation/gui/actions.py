"""GUI workflow wiring over Cantabile use cases."""

from __future__ import annotations

import tempfile
from contextlib import suppress
from dataclasses import asdict
from pathlib import Path
from typing import Any

from cantabile.adapters.export.filesystem import FilesystemReportWriter
from cantabile.adapters.ingest.exportify import read_playlist
from cantabile.adapters.providers.youtube import YouTubeProvider
from cantabile.adapters.store.sqlite_store import SqliteStore
from cantabile.adapters.suggesters.bandcamp_soundcloud import BandcampSuggester, SoundCloudSuggester
from cantabile.application.use_cases.acquire_audio import AcquireConfig, acquire_playlist
from cantabile.application.use_cases.import_playlist import persist_import
from cantabile.application.use_cases.report import build_playlist_report
from cantabile.ports.report import ReportWriteResult
from cantabile.ports.source import SuggesterPort
from cantabile.presentation.gui.jobs import LogFn
from cantabile.shared.settings import Settings, load_overrides


def gui_state(settings: Settings, selected: str = "") -> dict[str, Any]:
    """Return the current GUI state payload."""

    store = SqliteStore(settings.db_path)
    try:
        playlists = list(store.iter_playlists())
        chosen = selected or (playlists[0].name if playlists else "")
        report = None
        if chosen:
            playlist = store.get_playlist(chosen)
            if playlist is not None:
                report = _gui_report(build_playlist_report(playlist, store))
        return {
            "playlists": [
                {"name": playlist.name, "source": playlist.source, "size": playlist.size}
                for playlist in playlists
            ],
            "selected": chosen,
            "report": report,
        }
    finally:
        store.close()


def import_csv(path: Path, settings: Settings, log: LogFn) -> dict[str, Any]:
    """Import a CSV file into the configured store."""

    store = SqliteStore(settings.db_path)
    try:
        log(f"Reading {path.name}")
        playlist, tracks, observations = read_playlist(path)
        name = persist_import(playlist, tracks, observations, store)
        log(f"Imported {len(tracks)} tracks and {len(observations)} observations")
        return {"playlist": name, "tracks": len(tracks), "observations": len(observations)}
    finally:
        store.close()
        with suppress(OSError):
            path.unlink()


def fetch_playlist(
    playlist_name: str,
    settings: Settings,
    dry_run: bool,
    no_suggest: bool,
    overrides_text: str,
    log: LogFn,
) -> dict[str, Any]:
    """Fetch or dry-run source matching for a playlist."""

    store = SqliteStore(settings.db_path)
    override_path = _override_path(overrides_text)
    try:
        playlist = _playlist_or_raise(store, playlist_name)
        provider = YouTubeProvider(settings.insecure, settings.cookiefile, settings.proxy)
        suggesters: list[SuggesterPort] = [
            SoundCloudSuggester(settings.insecure),
            BandcampSuggester(settings.insecure),
        ]
        cfg = AcquireConfig(
            out_dir=Path(settings.output_dir) / playlist.name,
            fmt=settings.audio_format,
            tolerance=settings.tolerance,
            search_count=settings.search_count,
            sleep=settings.sleep,
            dry_run=dry_run,
            suggest=not no_suggest,
            overrides=load_overrides(str(override_path) if override_path else None, None),
        )
        log(f"{'Dry-running' if dry_run else 'Fetching'} {playlist.size} tracks")
        outcomes = acquire_playlist(playlist, store, provider, suggesters, cfg)
        counts: dict[str, int] = {}
        for outcome in outcomes:
            counts[outcome.status or "unknown"] = counts.get(outcome.status or "unknown", 0) + 1
        log("Fetch complete")
        return {"playlist": playlist.name, "tracks": len(outcomes), "status_counts": counts}
    finally:
        store.close()
        if override_path is not None:
            with suppress(OSError):
                override_path.unlink()


def analyze_lyrics(playlist_name: str, settings: Settings, force: bool, log: LogFn) -> dict[str, Any]:
    """Run the lyrics analyzer for a playlist."""

    from cantabile.adapters.analyzers.lyrics import LyricsAnalyzer
    from cantabile.application.use_cases.analyze import analyze_playlist

    store = SqliteStore(settings.db_path)
    try:
        playlist = _playlist_or_raise(store, playlist_name)
        log(f"Looking up lyrics for {playlist.size} tracks")
        outcomes = analyze_playlist(
            playlist,
            store,
            [LyricsAnalyzer(insecure=settings.insecure)],
            force=force,
        )
        found = sum(1 for item in outcomes if item.results.get("lyrics", 0) > 0)
        return {"playlist": playlist.name, "tracks": len(outcomes), "found": found}
    finally:
        store.close()


def analyze_mir(playlist_name: str, settings: Settings, force: bool, log: LogFn) -> dict[str, Any]:
    """Run the MIR analyzer for a playlist."""

    from cantabile.adapters.analyzers.mir import MIRAnalyzer
    from cantabile.application.use_cases.analyze import analyze_playlist

    store = SqliteStore(settings.db_path)
    try:
        playlist = _playlist_or_raise(store, playlist_name)
        log(f"Analyzing audio structure for {playlist.size} tracks")
        outcomes = analyze_playlist(playlist, store, [MIRAnalyzer()], force=force)
        done = sum(1 for item in outcomes if item.results.get("mir", 0) > 0)
        return {"playlist": playlist.name, "tracks": len(outcomes), "analyzed": done}
    finally:
        store.close()


def separate_stems(
    playlist_name: str,
    settings: Settings,
    force: bool,
    model: str,
    segment: float | None,
    two_stems: str,
    out: str,
    log: LogFn,
) -> dict[str, Any]:
    """Run Demucs stem separation for a playlist."""

    from cantabile.adapters.separators.demucs import DemucsSeparator
    from cantabile.application.use_cases.separate import separate_playlist

    store = SqliteStore(settings.db_path)
    try:
        playlist = _playlist_or_raise(store, playlist_name)
        separator = DemucsSeparator(
            model=model or settings.demucs_model,
            device=settings.demucs_device,
            segment=segment if segment is not None else settings.demucs_segment,
            fmt=settings.demucs_format,
            two_stems=two_stems or None,
        )
        out_dir = Path(out or settings.stems_dir)
        log(f"Separating {playlist.size} tracks with {separator.model} on {separator.device}")
        outcomes = separate_playlist(playlist, store, separator, out_dir, force=force)
        done = sum(1 for item in outcomes if item.status == "separated")
        return {"playlist": playlist.name, "tracks": len(outcomes), "separated": done}
    finally:
        store.close()


def export_playlist(playlist_name: str, settings: Settings, out: str, log: LogFn) -> dict[str, Any]:
    """Write CSV and HTML report artifacts for a playlist."""

    store = SqliteStore(settings.db_path)
    try:
        playlist = _playlist_or_raise(store, playlist_name)
        report = build_playlist_report(playlist, store)
        target = Path(out or settings.reports_dir)
        log(f"Writing report artifacts to {target}")
        result = FilesystemReportWriter().write(report, target)
        return _artifact_payload(result, settings)
    finally:
        store.close()


def _playlist_or_raise(store: SqliteStore, name: str):
    playlist = store.get_playlist(name)
    if playlist is None:
        raise ValueError(f"Playlist '{name}' not in store.")
    return playlist


def _override_path(text: str) -> Path | None:
    if not text.strip():
        return None
    tmp = tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8")
    with tmp:
        tmp.write(text)
    return Path(tmp.name)


def _artifact_payload(result: ReportWriteResult, settings: Settings) -> dict[str, Any]:
    base = Path(settings.reports_dir).resolve()
    links: dict[str, str] = {}
    for key, path in {
        "tracks_csv": result.tracks_csv,
        "observations_csv": result.observations_csv,
        "html_report": result.html_report,
    }.items():
        with suppress(ValueError):
            links[key] = "/generated/" + path.resolve().relative_to(base).as_posix()
    return {
        "out_dir": str(result.out_dir),
        "tracks_csv": str(result.tracks_csv),
        "observations_csv": str(result.observations_csv),
        "html_report": str(result.html_report),
        "links": links,
    }


def _gui_report(report) -> dict[str, Any]:
    payload = asdict(report)
    for row in payload["tracks"]:
        observations = row.pop("observations", [])
        row["observation_count"] = len(observations)
        if "lyrics" in row["resolved"]:
            row["resolved"]["lyrics"]["value"] = row["lyrics_status"]
    return payload
