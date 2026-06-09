"""Alternate-source suggesters: Bandcamp and SoundCloud.

Both implement SuggesterPort. SoundCloud (via yt-dlp scsearch) returns
durations, so its suggestions carry a real delta. Bandcamp's public search
returns the track but no duration, so those are marked unverified and get
their duration probed only if the user pins one.
"""

from __future__ import annotations

import json
import re
import ssl
import urllib.request
from typing import Optional

import yt_dlp

from cantabile.ports.source import Suggestion

_BC_URL = re.compile(r"https?://[^\s\"']+\.bandcamp\.com/(?:track|album)/[^\s\"']+")


class BandcampSuggester:
    name = "bandcamp"

    def __init__(self, insecure: bool = False) -> None:
        self._insecure = insecure

    def suggest(self, artist: str, title: str, target: Optional[float]) -> list[Suggestion]:
        out: list[Suggestion] = []
        try:
            body = json.dumps({"search_text": f"{artist} {title}", "search_filter": "t"}).encode()
            req = urllib.request.Request(
                "https://bandcamp.com/api/bcsearch_public_api/1/autocomplete_elastic",
                data=body, headers={"Content-Type": "application/json",
                                    "User-Agent": "Mozilla/5.0 cantabile"})
            ctx = ssl._create_unverified_context() if self._insecure else None
            with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
                data = json.load(resp)
        except Exception:  # noqa: BLE001
            return out
        for r in ((data.get("auto") or {}).get("results") or []):
            if r.get("type") != "t":
                continue
            url = next((v for v in r.values() if isinstance(v, str) and _BC_URL.search(v)),
                       r.get("item_url_root") or "")
            if not url:
                continue
            out.append(Suggestion(self.name, r.get("band_name") or "", r.get("name") or "",
                                  url, None, None, "duration unverified"))
            if len(out) >= 4:
                break
        return out


class SoundCloudSuggester:
    name = "soundcloud"

    def __init__(self, insecure: bool = False) -> None:
        self._net = {"nocheckcertificate": insecure}

    def suggest(self, artist: str, title: str, target: Optional[float]) -> list[Suggestion]:
        out: list[Suggestion] = []
        try:
            opts = {"quiet": True, "no_warnings": True, "extract_flat": True,
                    "skip_download": True, **self._net}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"scsearch5:{artist} {title}", download=False)
        except Exception:  # noqa: BLE001
            return out
        for e in (info or {}).get("entries") or []:
            if not e:
                continue
            dur = e.get("duration")
            delta = abs(dur - target) if (target and dur) else None
            note = f"{delta:+.0f}s" if delta is not None else "no duration"
            out.append(Suggestion(self.name, e.get("uploader") or e.get("channel") or "",
                                  e.get("title") or "",
                                  e.get("url") or e.get("webpage_url") or "", dur, delta, note))
        return out
