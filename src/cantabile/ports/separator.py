"""Separator port: split a track into stems (drums, bass, vocals, other).

A contract only. The concrete Demucs implementation lives in adapters. Returns
a mapping of stem name to file path on disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class SeparatorPort(Protocol):
    name: str

    def separate(self, audio_path: Path, out_dir: Path) -> dict[str, str]:
        """Separate one audio file. Return {stem_name: file_path}."""
        ...
