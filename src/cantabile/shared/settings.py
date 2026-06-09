"""Shared cross-cutting config. No business rules, importable by any layer.

Reads environment (and a .env if python-dotenv is installed) and parses the
overrides file. Settings are plain data; the composition root turns them into
adapters.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _env(key: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(key)
    return v if v not in (None, "") else default


def _env_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    db_path: str = _env("CANTABILE_DB", "cantabile.db")
    output_dir: str = _env("CANTABILE_OUTPUT", "./audio")
    audio_format: str = _env("CANTABILE_FORMAT", "wav")
    tolerance: float = float(_env("CANTABILE_TOLERANCE", "7.0"))
    search_count: int = int(_env("CANTABILE_SEARCH_COUNT", "6"))
    sleep: float = float(_env("CANTABILE_SLEEP", "1.0"))
    insecure: bool = _env_bool("CANTABILE_INSECURE")
    cookiefile: Optional[str] = _env("CANTABILE_COOKIES")
    proxy: Optional[str] = _env("CANTABILE_PROXY")
    # stem separation
    stems_dir: str = _env("CANTABILE_STEMS_DIR", "./stems")
    demucs_model: str = _env("CANTABILE_DEMUCS_MODEL", "htdemucs")
    demucs_segment: float = float(_env("CANTABILE_DEMUCS_SEGMENT", "7.0"))
    demucs_format: str = _env("CANTABILE_DEMUCS_FORMAT", "flac")
    demucs_device: str = _env("CANTABILE_DEMUCS_DEVICE", "cpu")


def load_overrides(path: Optional[str], inline: Optional[list[str]]) -> dict[int, str]:
    ov: dict[int, str] = {}
    if path:
        p = Path(path).expanduser()
        if p.exists():
            for raw in p.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = re.split(r"[,\t]", line, maxsplit=1)
                if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip():
                    ov[int(parts[0].strip())] = parts[1].strip()
    for item in (inline or []):
        if "=" in item:
            seq, url = item.split("=", 1)
            if seq.strip().isdigit():
                ov[int(seq.strip())] = url.strip()
    return ov
