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

from cantabile.adapters.ingest.exportify import read_playlist
from cantabile.adapters.providers.youtube import YouTubeProvider
from cantabile.adapters.store.sqlite_store import SqliteStore
from cantabile.adapters.suggesters.bandcamp_soundcloud import (
    BandcampSuggester, SoundCloudSuggester)
from cantabile.application.use_cases.acquire_audio import AcquireConfig, acquire_playlist
from cantabile.application.use_cases.import_playlist import persist_import
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


def cmd_import(args, settings: Settings) -> None:
    store = SqliteStore(settings.db_path)
    name = _import_csv(args.csv, store)
    pl = store.get_playlist(name)
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
    suggesters = [SoundCloudSuggester(settings.insecure), BandcampSuggester(settings.insecure)]
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
    return p


def main() -> None:
    args = build_parser().parse_args()
    settings = Settings()
    if args.cmd == "import":
        cmd_import(args, settings)
    elif args.cmd == "fetch":
        cmd_fetch(args, settings)


if __name__ == "__main__":
    main()
