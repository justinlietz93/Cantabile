"""Use case: acquire the real audio for every track in a playlist.

Pure orchestration over ports. For each track in order: skip if already have
an asset; honour a manual override; otherwise search the provider across the
primary then alternate queries, pick the best unclaimed candidate, download
it, and persist an AudioAsset plus an audio-duration Observation. Weak matches
collect alternate-source suggestions. Knows nothing about YouTube or SQLite.
"""

from __future__ import annotations

import time
import unicodedata
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from cantabile.application.services.match import (
    alt_queries, candidate_key, pick_best, rank_suggestions)
from cantabile.domain.models import AudioAsset, Playlist
from cantabile.domain.observation import Observation
from cantabile.domain.value_objects import Confidence, Provenance, TrackId
from cantabile.ports.source import SourceProviderPort, SuggesterPort
from cantabile.ports.store import StorePort

_SITE_PROVENANCE = {"youtube": Provenance.AUDIO, "bandcamp": Provenance.AUDIO,
                    "soundcloud": Provenance.AUDIO}


@dataclass
class AcquireConfig:
    out_dir: Path
    fmt: str = "wav"
    quality: str = "0"
    tolerance: float = 7.0
    search_count: int = 6
    sleep: float = 1.0
    dry_run: bool = False
    suggest: bool = True
    overrides: dict[int, str] = field(default_factory=dict)


@dataclass
class TrackOutcome:
    seq: int
    artist: str
    title: str
    confidence: Confidence
    url: str = ""
    delta: Optional[float] = None
    filename: str = ""
    status: str = ""
    suggestions: list = field(default_factory=list)


def _slug(text: str, maxlen: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip()
    text = re.sub(r"[\s_-]+", "_", text)
    return text[:maxlen].strip("_") or "track"


def acquire_playlist(
    playlist: Playlist,
    store: StorePort,
    provider: SourceProviderPort,
    suggesters: list[SuggesterPort],
    cfg: AcquireConfig,
    on_progress: Optional[Callable[["TrackOutcome"], None]] = None,
) -> list[TrackOutcome]:
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    pad = max(3, len(str(playlist.size)))
    claimed: set[str] = set()
    outcomes: list[TrackOutcome] = []

    def record(outcome: TrackOutcome) -> None:
        outcomes.append(outcome)
        if on_progress is not None:
            on_progress(outcome)

    for entry in playlist.entries:
        track = store.get_track(entry.track_id)
        if track is None:
            continue
        seq = entry.position + 1
        target = track.duration_sec
        oc = TrackOutcome(seq=seq, artist=track.primary_artist, title=track.title,
                          confidence=Confidence.NONE)

        if not cfg.dry_run and store.get_asset(track.id) is not None:
            oc.status = "skipped-exists"
            record(oc)
            continue

        stem = cfg.out_dir / f"{seq:0{pad}d}_{_slug(track.primary_artist)}_-_{_slug(track.title)}"

        # ---- manual override ---------------------------------------------- #
        if seq in cfg.overrides:
            url = cfg.overrides[seq]
            oc.url, oc.confidence = url, Confidence.OVERRIDE
            found = provider.probe_duration(url)
            if found and target:
                oc.delta = round(abs(found - target), 1)
            _finalize(track.id, url, oc, stem, target, store, provider, cfg)
            record(oc)
            continue

        # ---- search + match ---------------------------------------------- #
        candidates: list = []
        seen: set[str] = set()
        best, delta, conf = None, None, Confidence.NONE
        queries = [f"{track.primary_artist} {track.title}"] + alt_queries(
            track.primary_artist, track.title, ", ".join(track.artists))
        for q in queries:
            artist, _, title = q.partition(" ")
            for c in provider.search(track.primary_artist, track.title, cfg.search_count):
                k = candidate_key(c)
                if k and k not in seen:
                    seen.add(k)
                    candidates.append(c)
            best, delta, conf = pick_best(track.primary_artist, target, candidates,
                                          cfg.tolerance, claimed)
            if best is not None and conf in (Confidence.HIGH, Confidence.MEDIUM):
                break

        oc.confidence, oc.delta = conf, delta
        if best:
            claimed.add(candidate_key(best))
            oc.url = best.url
            _finalize(track.id, best.url, oc, stem, target, store, provider, cfg)
        else:
            oc.status = "no-candidate"

        if cfg.suggest and conf in (Confidence.LOW, Confidence.NONE, Confidence.MEDIUM):
            sug = []
            for s in suggesters:
                sug.extend(s.suggest(track.primary_artist, track.title, target))
            oc.suggestions = rank_suggestions(track.primary_artist, track.title, sug)[:3]

        record(oc)
        if not cfg.dry_run and best:
            time.sleep(cfg.sleep)

    return outcomes


def _finalize(track_id: TrackId, url: str, oc: TrackOutcome, stem: Path,
              target: Optional[float], store: StorePort,
              provider: SourceProviderPort, cfg: AcquireConfig) -> None:
    """Download (unless dry-run) and persist the asset + duration observation."""
    if cfg.dry_run:
        oc.status = "dry-run"
        oc.filename = stem.name + "." + cfg.fmt
        return
    try:
        produced = provider.download(url, stem, cfg.fmt, cfg.quality)
        oc.filename, oc.status = produced.name, "downloaded"
        asset = AudioAsset(
            track_id=track_id, source=_SITE_PROVENANCE.get(provider.name, Provenance.AUDIO),
            source_url=url, file_path=str(produced),
            duration_sec=provider.probe_duration(url), match_confidence=oc.confidence,
            fetched_at=datetime.now(timezone.utc))
        store.upsert_asset(asset)
        if asset.duration_sec:
            store.add_observation(Observation(
                track_id=track_id, feature="audio_duration", value=asset.duration_sec,
                source=Provenance.AUDIO, confidence=oc.confidence, unit="s"))
    except Exception as e:  # noqa: BLE001 - report, don't crash the batch
        oc.status = f"failed: {e}"
