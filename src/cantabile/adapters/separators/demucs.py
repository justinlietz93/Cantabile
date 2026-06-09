"""Demucs stem separator (runs via subprocess).

Implements SeparatorPort by shelling out to `python -m demucs`, so PyTorch is
only loaded in a child process when you actually separate, never at import.
Defaults are tuned for a CPU-only, 8 GB machine: device cpu, a small segment to
cap peak memory, and FLAC output (lossless, ~half the size of WAV) so stems for
a whole corpus fit on an external drive.

Requires the optional extra:  pip install -e ".[separation]"   (pulls torch)
and ffmpeg on PATH.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional


class DemucsSeparator:
    name = "demucs"

    def __init__(self, model: str = "htdemucs", device: str = "cpu",
                 segment: Optional[float] = 7.0, fmt: str = "flac",
                 two_stems: Optional[str] = None, jobs: int = 1) -> None:
        self.model = model
        self.device = device
        self.segment = segment      # seconds per chunk; lower = less RAM
        self.fmt = fmt              # flac | wav | mp3
        self.two_stems = two_stems  # e.g. "vocals" for a vocals/no_vocals split
        self.jobs = jobs            # keep at 1 on low-RAM machines

    def build_command(self, audio_path: Path, out_dir: Path) -> list[str]:
        cmd = [sys.executable, "-m", "demucs", "-n", self.model,
               "-d", self.device, "-o", str(out_dir), "-j", str(self.jobs)]
        if self.segment:
            cmd += ["--segment", str(self.segment)]
        if self.fmt == "flac":
            cmd += ["--flac"]
        elif self.fmt == "mp3":
            cmd += ["--mp3"]
        if self.two_stems:
            cmd += ["--two-stems", self.two_stems]
        cmd.append(str(audio_path))
        return cmd

    def separate(self, audio_path: Path, out_dir: Path) -> dict[str, str]:
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = self.build_command(audio_path, out_dir)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
            raise RuntimeError("demucs failed: " + " | ".join(tail))
        return self.locate_stems(out_dir, self.model, audio_path)

    @staticmethod
    def locate_stems(out_dir: Path, model: str, audio_path: Path) -> dict[str, str]:
        """Map stem name -> path from Demucs's output layout:
        <out_dir>/<model>/<track basename>/<stem>.<ext>"""
        track_dir = out_dir / model / audio_path.stem
        stems: dict[str, str] = {}
        if track_dir.is_dir():
            for f in sorted(track_dir.iterdir()):
                if f.suffix.lower() in (".flac", ".wav", ".mp3"):
                    stems[f.stem] = str(f)
        return stems
