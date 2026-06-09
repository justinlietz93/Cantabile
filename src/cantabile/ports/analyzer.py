"""Analyzer port: the contract every enricher implements.

An Analyzer consumes a Track (and optionally its AudioAsset) and emits
Observations. Lyrics lookup, MIR tempo/section analysis, and a future tab
generator are all Analyzers. Adding one is registering a new adapter; the
core and the pipeline never change.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from cantabile.domain.models import AudioAsset, Track
from cantabile.domain.observation import Observation


@runtime_checkable
class AnalyzerPort(Protocol):
    name: str

    def applies_to(self, track: Track, asset: Optional[AudioAsset]) -> bool: ...
    def analyze(self, track: Track, asset: Optional[AudioAsset]) -> list[Observation]: ...
