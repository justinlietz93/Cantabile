"""Source ports: how Cantabile reaches the outside world for audio.

A SourceProvider finds and downloads the real recording for a track. A
Suggester proposes alternate sources when the primary match is weak. Both are
contracts; concrete YouTube / Bandcamp / SoundCloud code lives in adapters.

Candidate and Suggestion are plain contract types (data carried across the
port boundary), so they live with the port, not in any adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable


@dataclass
class Candidate:
    """A possible source match returned by a provider's search."""

    provider: str
    id: str
    title: str
    channel: str
    url: str
    duration: Optional[float] = None    # seconds, if the provider reports it


@dataclass
class Suggestion:
    """An alternate-source proposal for a track that matched poorly."""

    source: str
    artist: str
    title: str
    url: str
    duration: Optional[float] = None
    delta: Optional[float] = None       # |found - target| seconds, if known
    note: str = ""


@runtime_checkable
class SourceProviderPort(Protocol):
    name: str

    def search(self, artist: str, title: str, n: int) -> list[Candidate]: ...
    def probe_duration(self, url: str) -> Optional[float]: ...
    def download(self, url: str, out_stem: Path, fmt: str, quality: str) -> Path: ...


@runtime_checkable
class SuggesterPort(Protocol):
    name: str

    def suggest(self, artist: str, title: str, target: Optional[float]) -> list[Suggestion]: ...
