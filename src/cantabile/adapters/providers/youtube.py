"""YouTube source provider (yt-dlp).

Implements SourceProviderPort: flat search for candidates, duration probe, and
audio-only download. Contains no matching or dedup logic; that lives in the
application matching service. Network options (insecure TLS, cookies, proxy)
are passed in at construction by the composition root.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yt_dlp

from cantabile.ports.source import Candidate


class YouTubeProvider:
    name = "youtube"

    def __init__(self, insecure: bool = False, cookiefile: Optional[str] = None,
                 proxy: Optional[str] = None) -> None:
        self._net = {"nocheckcertificate": insecure}
        if cookiefile:
            self._net["cookiefile"] = cookiefile
        if proxy:
            self._net["proxy"] = proxy

    def search(self, artist: str, title: str, n: int) -> list[Candidate]:
        query = f"{artist} {title}".strip()
        opts = {"quiet": True, "no_warnings": True, "extract_flat": True,
                "skip_download": True, "default_search": "ytsearch", **self._net}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
        out: list[Candidate] = []
        for e in (info or {}).get("entries") or []:
            if not e:
                continue
            vid = e.get("id") or ""
            out.append(Candidate(
                provider=self.name, id=vid, title=e.get("title") or "",
                channel=e.get("channel") or e.get("uploader") or "",
                url=e.get("url") or e.get("webpage_url")
                    or (f"https://www.youtube.com/watch?v={vid}" if vid else ""),
                duration=e.get("duration")))
        return out

    def probe_duration(self, url: str) -> Optional[float]:
        try:
            opts = {"quiet": True, "no_warnings": True, "skip_download": True, **self._net}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            return info.get("duration") if info else None
        except Exception:  # noqa: BLE001
            return None

    def download(self, url: str, out_stem: Path, fmt: str, quality: str) -> Path:
        out_stem.parent.mkdir(parents=True, exist_ok=True)
        opts = {"quiet": True, "no_warnings": True, "noplaylist": True,
                "format": "bestaudio/best", "outtmpl": str(out_stem) + ".%(ext)s",
                "postprocessors": [{"key": "FFmpegExtractAudio",
                                    "preferredcodec": fmt, "preferredquality": quality}],
                **self._net}
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        produced = out_stem.with_suffix("." + fmt)
        if not produced.exists():
            matches = list(out_stem.parent.glob(out_stem.name + ".*"))
            if matches:
                produced = matches[0]
        return produced
