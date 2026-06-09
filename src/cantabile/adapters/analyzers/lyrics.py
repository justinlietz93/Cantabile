"""Lyrics analyzer (LRCLIB exact + fuzzy, Genius fallback).

Implements AnalyzerPort. For a track it looks up lyrics and emits a single
Observation: feature "lyrics", value the text (or "[instrumental]"), tagged
with the provenance of whichever source answered. A shared on-disk JSON cache
makes reruns instant and avoids hammering the APIs, exactly as in the original
standalone script this was ported from.

Requires the optional extra:  pip install -e ".[lyrics]"
Genius is optional; set GENIUS_TOKEN in the environment to enable it. Without
it, the analyzer runs LRCLIB-only.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup

from cantabile.domain.models import AudioAsset, Track
from cantabile.domain.observation import Observation
from cantabile.domain.value_objects import Confidence, Provenance

_LRCLIB = "https://lrclib.net/api"
_GENIUS_API = "https://api.genius.com"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_LRCLIB_PAUSE = 0.34
_GENIUS_PAUSE = 0.6
_MAX_RETRIES = 3
_RETRY_BACKOFF = 2.0


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


class LyricsAnalyzer:
    name = "lyrics"
    feature = "lyrics"   # the use case skips tracks that already have this

    def __init__(self, cache_path: Optional[str] = None,
                 genius_token: Optional[str] = None, insecure: bool = False) -> None:
        cache = cache_path or os.getenv("CANTABILE_LYRICS_CACHE") or "lyrics_cache.json"
        self._cache_path = Path(cache)
        self._genius_token = genius_token or os.getenv("GENIUS_TOKEN", "").strip()
        self._verify = not insecure
        self._cache: dict[str, Any] = self._load_cache()

    # ------------------------------ port API ------------------------------ #
    def applies_to(self, track: Track, asset: Optional[AudioAsset]) -> bool:
        return bool(track.title and track.primary_artist)

    def analyze(self, track: Track, asset: Optional[AudioAsset]) -> list[Observation]:
        artist_full = ", ".join(track.artists)
        primary = track.primary_artist
        album = track.album or ""
        dur_s = round((track.duration_ms or 0) / 1000)
        key = self._key(artist_full, track.title, album, dur_s)

        if key in self._cache:
            entry = self._cache[key]
        else:
            entry = self._lookup(primary, track.title, album, dur_s)
            self._cache[key] = entry
            self._save_cache()

        text, source = entry.get("lyrics") or "", entry.get("source") or ""
        if not text or not source:
            return []   # genuine miss: store nothing, the cache remembers we tried
        prov = Provenance.LYRICS_LRCLIB if source == "lrclib" else Provenance.LYRICS_GENIUS
        conf = Confidence.MEDIUM if text == "[instrumental]" else Confidence.HIGH
        return [Observation(track_id=track.id, feature="lyrics", value=text,
                            source=prov, confidence=conf, analyzer_version="lyrics/1")]

    # ------------------------------ lookup -------------------------------- #
    def _lookup(self, primary: str, track: str, album: str, dur_s: int) -> dict:
        res = self._lrclib(primary, track, album, dur_s)
        time.sleep(_LRCLIB_PAUSE)
        if res == "[instrumental]":
            return {"lyrics": "[instrumental]", "source": "lrclib"}
        if res:
            return {"lyrics": res, "source": "lrclib"}
        g = self._genius(primary, track)
        if g:
            return {"lyrics": g, "source": "genius"}
        return {"lyrics": "", "source": ""}

    def _lrclib(self, artist: str, track: str, album: str, dur_s: int) -> Optional[str]:
        r = self._get(f"{_LRCLIB}/get", params={
            "artist_name": artist, "track_name": track, "album_name": album, "duration": dur_s})
        if r is not None:
            d = r.json()
            if d.get("instrumental"):
                return "[instrumental]"
            if d.get("plainLyrics"):
                return d["plainLyrics"].strip()
        r = self._get(f"{_LRCLIB}/search", params={"q": f"{artist} {track}"})
        if r is not None:
            results = r.json()
            if isinstance(results, list) and results:
                def score(it):
                    try:
                        return abs(int(it.get("duration", 0)) - dur_s)
                    except (TypeError, ValueError):
                        return 10 ** 9
                best = sorted(results, key=score)[0]
                if best.get("instrumental"):
                    return "[instrumental]"
                if best.get("plainLyrics"):
                    return best["plainLyrics"].strip()
        return None

    def _genius(self, artist: str, track: str) -> Optional[str]:
        if not self._genius_token:
            return None
        headers = {"Authorization": f"Bearer {self._genius_token}"}
        r = self._get(f"{_GENIUS_API}/search", params={"q": f"{artist} {track}"}, headers=headers)
        time.sleep(_GENIUS_PAUSE)
        if r is None:
            return None
        hits = r.json().get("response", {}).get("hits", [])
        if not hits:
            return None
        want_t, want_a = _norm(track), _norm(artist)

        def hit_score(h):
            res = h.get("result", {})
            t = _norm(res.get("title", ""))
            a = _norm(res.get("primary_artist", {}).get("name", ""))
            s = 0
            if want_t and (want_t in t or t in want_t):
                s += 2
            if want_a and (want_a in a or a in want_a):
                s += 2
            return s

        best = max(hits, key=hit_score)
        if hit_score(best) == 0:
            return None
        url = best.get("result", {}).get("url")
        return self._genius_scrape(url) if url else None

    def _genius_scrape(self, url: str) -> Optional[str]:
        r = self._get(url)
        time.sleep(_GENIUS_PAUSE)
        if r is None:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        containers = soup.find_all("div", attrs={"data-lyrics-container": "true"})
        if not containers:
            legacy = soup.find("div", class_="lyrics")
            return (legacy.get_text("\n").strip() or None) if legacy else None
        parts = []
        for c in containers:
            for br in c.find_all("br"):
                br.replace_with("\n")
            parts.append(c.get_text())
        text = re.sub(r"^\d+\s+Contributors.*?Lyrics", "", "\n".join(parts).strip(),
                      flags=re.DOTALL).strip()
        return text or None

    # ------------------------------ http / cache -------------------------- #
    def _get(self, url: str, params: dict | None = None,
             headers: dict | None = None) -> Optional[requests.Response]:
        h = {"User-Agent": _UA}
        if headers:
            h.update(headers)
        for attempt in range(_MAX_RETRIES):
            try:
                r = requests.get(url, params=params, headers=h, timeout=20, verify=self._verify)
                if r.status_code == 404:
                    return None
                if r.status_code == 200:
                    return r
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(_RETRY_BACKOFF * (2 ** attempt))
                    continue
                return None
            except requests.RequestException:
                time.sleep(_RETRY_BACKOFF * (2 ** attempt))
        return None

    def _key(self, artist: str, track: str, album: str, dur_s: int) -> str:
        return f"{artist.lower().strip()}|||{track.lower().strip()}|||{album.lower().strip()}|||{dur_s}"

    def _load_cache(self) -> dict:
        if self._cache_path.exists():
            try:
                return json.loads(self._cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_cache(self) -> None:
        tmp = self._cache_path.with_suffix(self._cache_path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._cache, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._cache_path)
