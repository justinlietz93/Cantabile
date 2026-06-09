"""Candidate matching: pick the best source for a track.

Provider-agnostic. Given the Candidates a provider returned, choose the one
whose duration is closest to the Spotify duration, rewarding a channel that
carries the track's artist (so RichaadEB's cover beats GeoffPlaysGuitar's),
penalising live/cover/loop uploads, and refusing any video already claimed by
another track in the same run. This is orchestration logic, so it lives in the
application layer, not inside any provider adapter.
"""

from __future__ import annotations

import difflib
import re
from typing import Optional

from cantabile.domain.value_objects import Confidence
from cantabile.ports.source import Candidate

_BAD_HINTS = re.compile(
    r"\b(live|cover|reaction|lyric video|karaoke|instrumental cover|sped up|slowed|"
    r"remix|tutorial|guitar lesson|how to play|8d audio|nightcore|loop|1 hour|extended)\b",
    re.IGNORECASE,
)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def candidate_key(c: Candidate) -> str:
    return c.id or c.url or ""


def _artist_bonus(artist: str, c: Candidate) -> float:
    a = _norm(artist)
    if not a:
        return 0.0
    if a in _norm(c.channel):
        return 45.0
    if a in _norm(c.title):
        return 12.0
    return 0.0


def confidence_for(delta: Optional[float], has_target: bool, tol: float) -> Confidence:
    if delta is None:
        return Confidence.MEDIUM if not has_target else Confidence.LOW
    if delta <= tol:
        return Confidence.HIGH
    if delta <= tol * 3:
        return Confidence.MEDIUM
    return Confidence.LOW


def pick_best(
    artist: str,
    target_sec: Optional[float],
    candidates: list[Candidate],
    tol: float,
    claimed: set[str],
) -> tuple[Optional[Candidate], Optional[float], Confidence]:
    pool = [c for c in candidates if candidate_key(c) and candidate_key(c) not in claimed]
    if not pool:
        return None, None, Confidence.NONE
    scored = []
    for c in pool:
        duration = c.duration
        if target_sec is not None and duration is not None:
            raw_delta = abs(duration - target_sec)
            delta: Optional[float] = raw_delta
            score: float = raw_delta
        else:
            delta = None
            score = 600.0
        score += 30.0 if _BAD_HINTS.search(c.title) else 0.0
        score -= _artist_bonus(artist, c)
        scored.append((score, delta, c))
    scored.sort(key=lambda x: x[0])
    _, delta, best = scored[0]
    return best, delta, confidence_for(delta, bool(target_sec), tol)


def alt_queries(artist: str, title: str, artists_full: str = "") -> list[str]:
    qs = [f"{artist} {title} audio", f"{title} {artist}"]
    if artists_full and artists_full != artist:
        qs.append(f"{artists_full} {title}")
    return [re.sub(r"\s+", " ", q.strip()) for q in qs]


def rank_suggestions(artist: str, title: str, suggestions: list) -> list:
    def key(s):
        if getattr(s, "delta", None) is not None:
            return (0, s.delta)
        ratio = (0.5 * difflib.SequenceMatcher(None, _norm(artist), _norm(s.artist)).ratio()
                 + 0.5 * difflib.SequenceMatcher(None, _norm(title), _norm(s.title)).ratio())
        return (1, -ratio)
    seen, uniq = set(), []
    for s in sorted(suggestions, key=key):
        if s.url and s.url not in seen:
            seen.add(s.url)
            uniq.append(s)
    return uniq
