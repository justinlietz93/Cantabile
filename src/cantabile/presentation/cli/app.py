"""Cantabile CLI: the composition root.

This is the only module allowed to import every layer, because its whole job
is to wire concrete adapters to the use cases at the edge. It parses args,
builds the store, provider, and suggesters from settings, calls a use case,
and prints. No business logic lives here.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cantabile.adapters.export.filesystem import FilesystemReportWriter
from cantabile.adapters.ingest.exportify import read_playlist
from cantabile.adapters.providers.youtube import YouTubeProvider
from cantabile.adapters.store.sqlite_store import SqliteStore
from cantabile.adapters.suggesters.bandcamp_soundcloud import (
    BandcampSuggester, SoundCloudSuggester)
from cantabile.application.use_cases.acquire_audio import AcquireConfig, acquire_playlist
from cantabile.application.use_cases.import_playlist import persist_import
from cantabile.application.use_cases.report import build_playlist_report
from cantabile.ports.source import SuggesterPort
from cantabile.shared.settings import Settings, load_overrides


def _import_csv(csv_path: str, store: SqliteStore) -> str:
    playlist, tracks, observations = read_playlist(csv_path)
    return persist_import(playlist, tracks, observations, store)


def _print_outcomes(outcomes, total: int) -> None:
    for oc in outcomes:
        dlt = f"{oc.delta:+.1f}s" if oc.delta is not None else "  n/a"
        print(f"[{oc.seq:>3}/{total}] {oc.confidence.value:<8} ({dlt:>7}) "
              f"{oc.artist} - {oc.title[:34]}  {oc.status}")
    weak = [oc for oc in outcomes if oc.suggestions]
    if weak:
        print("\nSuggested overrides (paste into overrides.csv):")
        for oc in weak:
            print(f"  # {oc.seq} {oc.artist} - {oc.title}  ({oc.confidence.value})")
            for s in oc.suggestions:
                print(f"      {oc.seq},{s.url}    # {s.source}: {s.artist} - {s.title} [{s.note}]")


def cmd_lyrics(args, settings: Settings) -> None:
    # imported lazily so core commands don't require the [lyrics] extra
    from cantabile.adapters.analyzers.lyrics import LyricsAnalyzer
    from cantabile.application.use_cases.analyze import analyze_playlist

    store = SqliteStore(settings.db_path)
    name = args.playlist
    if args.csv:
        name = _import_csv(args.csv, store)
    playlist = store.get_playlist(name) if name else None
    if not playlist:
        store.close()
        sys.exit(f"Playlist '{name}' not in store. Import it first.")

    analyzer = LyricsAnalyzer(cache_path=args.cache, insecure=settings.insecure)
    print(f"Looking up lyrics for {playlist.size} tracks in '{name}'"
          f"{'' if analyzer._genius_token else '  (LRCLIB-only; set GENIUS_TOKEN for fallback)'}")
    print("-" * 60)
    outcomes = analyze_playlist(playlist, store, [analyzer], force=args.force)

    found = skipped = empty = 0
    for oc in outcomes:
        n = oc.results.get("lyrics", 0)
        if oc.status == "skipped-existing":
            tag, skipped = "skip", skipped + 1
        elif n > 0:
            tag, found = "ok", found + 1
        else:
            tag, empty = "--", empty + 1
        print(f"[{oc.seq:>3}/{playlist.size}] {tag:<4} {oc.artist[:20]:20} - {oc.title[:34]}")
    print(f"\nLyrics: {found} found, {skipped} already had them, {empty} none. "
          f"Stored in {settings.db_path}")
    store.close()


def cmd_mir(args, settings: Settings) -> None:
    # imported lazily so core commands don't require the [audio] extra
    from cantabile.adapters.analyzers.mir import MIRAnalyzer
    from cantabile.application.use_cases.analyze import analyze_playlist

    store = SqliteStore(settings.db_path)
    name = args.playlist
    if args.csv:
        name = _import_csv(args.csv, store)
    playlist = store.get_playlist(name) if name else None
    if not playlist:
        store.close()
        sys.exit(f"Playlist '{name}' not in store. Import it first.")

    print(f"Analyzing audio for {playlist.size} tracks in '{name}' "
          f"(needs fetched audio)\n" + "-" * 60)
    outcomes = analyze_playlist(playlist, store, [MIRAnalyzer()], force=args.force)

    done = skipped = noaudio = 0
    for oc in outcomes:
        n = oc.results.get("mir", 0)
        if oc.status == "skipped-existing":
            tag, skipped = "skip", skipped + 1
        elif n > 0:
            tag, done = "ok", done + 1
        else:
            tag, noaudio = "--", noaudio + 1
        print(f"[{oc.seq:>3}/{playlist.size}] {tag:<4} {oc.artist[:20]:20} - {oc.title[:30]}")
    print(f"\nMIR: {done} analyzed, {skipped} already done, {noaudio} without audio. "
          f"Stored in {settings.db_path}.\nRun a query to compare felt vs Spotify tempo.")
    store.close()


def cmd_separate(args, settings: Settings) -> None:
    # imported lazily so core commands don't require the [separation] extra (torch)
    from cantabile.adapters.separators.demucs import DemucsSeparator
    from cantabile.application.use_cases.separate import separate_playlist

    store = SqliteStore(settings.db_path)
    name = args.playlist
    playlist = store.get_playlist(name) if name else None
    if not playlist:
        store.close()
        sys.exit(f"Playlist '{name}' not in store. Import and fetch it first.")

    separator = DemucsSeparator(
        model=args.model or settings.demucs_model, device=settings.demucs_device,
        segment=args.segment if args.segment is not None else settings.demucs_segment,
        fmt=settings.demucs_format, two_stems=args.two_stems)
    out_dir = Path(args.out or settings.stems_dir)

    print(f"Separating '{name}' ({playlist.size} tracks) with {separator.model} on "
          f"{separator.device}\nStems -> {out_dir}  (this is slow on CPU; run once)\n" + "-" * 60)
    outcomes = separate_playlist(playlist, store, separator, out_dir, force=args.force)

    done = skipped = noaudio = failed = 0
    for oc in outcomes:
        if oc.status == "separated":
            tag, done = "ok", done + 1
        elif oc.status == "skipped-existing":
            tag, skipped = "skip", skipped + 1
        elif oc.status == "no-audio":
            tag, noaudio = "--", noaudio + 1
        else:
            tag, failed = "FAIL", failed + 1
        print(f"[{oc.seq:>3}/{playlist.size}] {tag:<4} {oc.artist[:20]:20} - {oc.title[:28]}  {oc.status}")
    print(f"\nSeparated {done}, skipped {skipped}, no audio {noaudio}, failed {failed}. "
          f"Stems recorded in {settings.db_path}.\nNow rerun 'cantabile mir' to analyze from stems.")
    store.close()


def cmd_import(args, settings: Settings) -> None:
    store = SqliteStore(settings.db_path)
    name = _import_csv(args.csv, store)
    pl = store.get_playlist(name)
    if pl is None:
        store.close()
        sys.exit(f"Import failed for '{name}'.")
    print(f"Imported '{name}': {pl.size} tracks -> {settings.db_path}")
    store.close()


def cmd_fetch(args, settings: Settings) -> None:
    store = SqliteStore(settings.db_path)
    name = args.playlist
    if args.csv:
        name = _import_csv(args.csv, store)
    if not name:
        sys.exit("Provide --csv to import+fetch, or --playlist <name> already imported.")
    playlist = store.get_playlist(name)
    if not playlist:
        sys.exit(f"Playlist '{name}' not in store. Import it first.")

    provider = YouTubeProvider(settings.insecure, settings.cookiefile, settings.proxy)
    suggesters: list[SuggesterPort] = [
        SoundCloudSuggester(settings.insecure),
        BandcampSuggester(settings.insecure),
    ]
    cfg = AcquireConfig(
        out_dir=Path(settings.output_dir) / name, fmt=settings.audio_format,
        tolerance=settings.tolerance, search_count=settings.search_count, sleep=settings.sleep,
        dry_run=args.dry_run, suggest=not args.no_suggest,
        overrides=load_overrides(args.overrides, args.override))

    print(f"Playlist : {name}\nTracks   : {playlist.size}\nOutput   : {cfg.out_dir}\n"
          f"Mode     : {'DRY RUN' if cfg.dry_run else 'download .' + cfg.fmt}\n" + "-" * 60)
    outcomes = acquire_playlist(playlist, store, provider, suggesters, cfg)
    _print_outcomes(outcomes, playlist.size)
    store.close()


def cmd_export(args, settings: Settings) -> None:
    store = SqliteStore(settings.db_path)
    playlist = store.get_playlist(args.playlist)
    if playlist is None:
        store.close()
        sys.exit(f"Playlist '{args.playlist}' not in store. Import it first.")
    report = build_playlist_report(playlist, store)
    result = FilesystemReportWriter().write(report, Path(args.out or settings.reports_dir))
    print(f"Exported '{playlist.name}' -> {result.out_dir}")
    print(f"  tracks       {result.tracks_csv}")
    print(f"  observations {result.observations_csv}")
    print(f"  report       {result.html_report}")
    store.close()


def cmd_gui(args, settings: Settings) -> None:
    try:
        from cantabile.presentation.gui.server import run_gui
    except ImportError as exc:
        raise SystemExit("Install the GUI extra first: pip install -e '.[gui]'") from exc
    run_gui(settings, host=args.host, port=args.port, open_browser=not args.no_open)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cantabile",
                                description="Playlist audio + structure lab (SGHM).")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("import", help="Import an Exportify CSV into the store")
    pi.add_argument("csv")

    pf = sub.add_parser("fetch", help="Acquire audio for a playlist")
    pf.add_argument("--csv", help="Exportify CSV to import then fetch")
    pf.add_argument("--playlist", help="Name of an already-imported playlist")
    pf.add_argument("--dry-run", action="store_true")
    pf.add_argument("--no-suggest", action="store_true")
    pf.add_argument("--overrides", help="CSV of seq,url override pins")
    pf.add_argument("--override", action="append", metavar="SEQ=URL")

    pl = sub.add_parser("lyrics", help="Look up lyrics (LRCLIB + Genius) into the store")
    pl.add_argument("--playlist", help="Name of an already-imported playlist")
    pl.add_argument("--csv", help="Exportify CSV to import then analyze")
    pl.add_argument("--cache", help="Path to the lyrics cache JSON")
    pl.add_argument("--force", action="store_true",
                    help="Re-fetch even if a track already has lyrics")

    pm = sub.add_parser("mir", help="Analyze fetched audio (felt tempo, sections, loop/line)")
    pm.add_argument("--playlist", help="Name of an already-imported playlist")
    pm.add_argument("--csv", help="Exportify CSV to import then analyze")
    pm.add_argument("--force", action="store_true",
                    help="Re-analyze even if a track already has MIR results")

    ps = sub.add_parser("separate", help="Split fetched audio into stems (Demucs)")
    ps.add_argument("--playlist", required=True, help="Name of an imported+fetched playlist")
    ps.add_argument("--model", help="Demucs model (default htdemucs)")
    ps.add_argument("--segment", type=float, help="Seconds per chunk; lower = less RAM")
    ps.add_argument("--two-stems", metavar="STEM",
                    help="Lighter split, e.g. 'vocals' for vocals/no_vocals")
    ps.add_argument("--out", help="Output dir for stems (point at a big drive)")
    ps.add_argument("--force", action="store_true", help="Re-separate even if stems exist")

    pe = sub.add_parser("export", help="Export playlist CSVs and an HTML report")
    pe.add_argument("--playlist", required=True, help="Name of an imported playlist")
    pe.add_argument("--out", help="Output directory for report artifacts")

    pg = sub.add_parser("gui", help="Run the local browser GUI")
    pg.add_argument("--host", default="127.0.0.1")
    pg.add_argument("--port", type=int, default=8765)
    pg.add_argument("--no-open", action="store_true", help="Do not open a browser tab")
    return p


def main() -> None:
    args = build_parser().parse_args()
    settings = Settings()
    if args.cmd == "import":
        cmd_import(args, settings)
    elif args.cmd == "fetch":
        cmd_fetch(args, settings)
    elif args.cmd == "lyrics":
        cmd_lyrics(args, settings)
    elif args.cmd == "mir":
        cmd_mir(args, settings)
    elif args.cmd == "separate":
        cmd_separate(args, settings)
    elif args.cmd == "export":
        cmd_export(args, settings)
    elif args.cmd == "gui":
        cmd_gui(args, settings)


if __name__ == "__main__":
    main()
