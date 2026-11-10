<img width="1774" height="887" alt="image" src="https://github.com/user-attachments/assets/947b5d3f-b121-4d60-b689-7fd6d3e30ba9" />

**A local music library and analysis workbench built around recordings, not just playlist metadata.**

> [!WARNING]
> **Cantabile is in active development and is unfinished.** This repository is experimental software, not a stable or fully validated music-analysis product. Some workflows work today; others have known correctness defects or still exist only on the roadmap. Back up your data, inspect downloaded recordings, and treat analysis results as estimates rather than verified musical facts.

**Version and release status (10 November 2026):**

- **This repository:** `0.1.0` — the source-based CLI and local browser GUI described below.
- **Next desktop build:** `0.2.0` — a separately developed **unreleased / pre-release** Linux desktop build. A package and substantial validation work are documented, but **that code and installer are not contained in this repository snapshot**.
- **Last documented 0.2.0 progress report:** 20 September 2026. The remaining acceptance work is listed [below](#upcoming-020-desktop-build--progress). No public release date is confirmed here.

[Get started](#quick-start--current-repository) · [Capabilities](#what-works-in-this-repository) · [Known limitations](#known-limitations) · [Upcoming desktop build](#upcoming-020-desktop-build--progress) · [Roadmap](#long-term-roadmap)

## What Cantabile is for

A playlist export describes *which tracks* you saved. Cantabile aims to connect that catalog to *which recordings* were actually acquired and *what can be measured from their audio*.

The intended workflow is:

```text
Playlist CSV
    │
    ▼
Track catalog + original metadata  ───────►  SQLite database
    │                                             ▲
    ▼                                             │
Review source candidates → Acquire audio         │
    │                                             │
    ├──► Lyrics lookup ───────────────────────────┤
    ├──► Waveform/MIR analysis ───────────────────┤
    └──► Optional stem separation ─► MIR ─────────┘
                                                  │
                                                  ▼
                                        Local GUI and reports
```

Measurements and imported metadata are kept as separate **Observations**, each labeled with a source and confidence category. The database can retain multiple values for the same feature instead of deleting an older estimate. This is a foundation for evidence-based analysis, **not a guarantee that a chosen source or measured result is correct**.

## What works in this repository

The table describes **the attached `0.1.0` source**, not features built separately for the upcoming desktop version.

| Component | Current state | What it does |
|---|---|---|
| Playlist import | Implemented | Reads Exportify-style CSVs, preserves playlist order and stores track metadata and available numeric Spotify features in SQLite. |
| Audio acquisition | Implemented, with matching defects | Searches YouTube through `yt-dlp`, previews candidates and downloads selected audio. Supports source suggestions and manual URL overrides, with limitations below. |
| Lyrics | Implemented, experimental | Retrieves text through LRCLIB with optional Genius fallback and caches results. Not time-aligned. |
| Basic MIR | Implemented, heuristic | Estimates tempo, tempo variation/range, section count and a loop/line proxy from audio. |
| Stem separation | Implemented, resource-intensive | Invokes Demucs for vocals, drums, bass and other; can be run on CPU. |
| Local database | Implemented | Persists tracks, playlists, audio-asset references, stems and observations in SQLite. |
| Reports | Implemented | Exports resolved track data, raw observations and an HTML report. |
| Browser interface | Implemented | Local FastAPI interface for inspecting data and running core workflows. **Not a packaged native desktop app in this checkout.** |
| Time-aligned musical structure | Not implemented | Precise section boundaries, named form labels, tempo maps and cross-section comparisons. |
| Full multilayer AI system | Not implemented | Embeddings, semantic audio search, vocal/lyrical interpretation, note/chord transcription, scores and tablature. |

### A note on accuracy

Spotify's reported features are retained as metadata, not accepted as ground truth. Cantabile prioritizes waveform-derived observations over Spotify-origin observations when resolving some features. But this is currently a **source-priority rule**, not a calibrated estimate of correctness. A misidentified recording can produce convincing but irrelevant measurements; rhythm estimators can also return half-time or double-time interpretations.

## Quick start — current repository

### Requirements

- Python **3.10 or newer**.
- **FFmpeg** installed and available on `PATH` (`ffmpeg -version` should work).
- A supported playlist CSV for importing. An internet connection is needed for source search, audio download and online lyrics lookup.
- Free storage for audio. Demucs and its dependencies require substantially more disk space and RAM than basic import/export.

Use a virtual environment from the extracted repository directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[gui,lyrics,audio]'
```

The last command installs the browser GUI, lyrics adapters and basic waveform-analysis dependencies. **Demucs is optional**; install it only if you need stem separation:

```bash
python -m pip install -e '.[separation]'
```

On Debian/Ubuntu, FFmpeg can typically be installed with `sudo apt install ffmpeg`. Heavy audio dependencies may need platform-specific setup.

### 1. Import your CSV

Export a playlist in Exportify-compatible CSV format. For a file named `playlist.csv`:

```bash
cantabile import /path/to/playlist.csv
```

The playlist is stored under the filename stem, here `playlist`. Expected columns include a track title and artist; Spotify URI, album, duration and audio-feature columns are used when supplied.

### 2. Preview proposed recordings

```bash
cantabile fetch --playlist playlist --dry-run
```

**Review the artist, title, duration difference and URL before downloading.** A `high` confidence label currently means that the candidate met the duration-based matching rule; it does **not** confirm the track's identity, mix or release version. The source matcher has a known wrong-song failure described below.

Once you've reviewed the proposed sources:

```bash
cantabile fetch --playlist playlist
```

To explicitly supply a source for playlist position 10:

```bash
cantabile fetch --playlist playlist --override '10=https://example.com/recording'
```

Manual overrides are reliable for entries without a saved asset, **but this version may skip an existing asset before applying a new override**. Do not assume an override corrected a previously downloaded wrong recording; verify the saved source. A `--overrides` file can also contain `seq,url` lines (see `overrides.example.csv`).

### 3. Retrieve lyrics and analyze audio

```bash
cantabile lyrics --playlist playlist
cantabile mir --playlist playlist
```

Lyrics are retrieved from LRCLIB, with an optional Genius fallback when `GENIUS_TOKEN` is configured. MIR requires downloaded audio and records approximate waveform-derived features. If you replace audio or want new results to supersede an earlier analysis, you may need `--force`:

```bash
cantabile mir --playlist playlist --force
```

### 4. Optional: separate stems

```bash
cantabile separate --playlist playlist --out /path/to/large-drive/stems
cantabile mir --playlist playlist --force
```

Demucs can be slow and memory-hungry on CPU-only machines. Start with a short recording before running a large playlist. **Use `mir --force` after separation in this repository**: the ordinary MIR skip rule does not reliably detect newly added stems.

### 5. Open the interface or export results

```bash
cantabile gui                         # local browser GUI
cantabile gui --port 8770 --no-open
cantabile export --playlist playlist
```

The GUI defaults to `http://127.0.0.1:8765`. Reports go under `./reports` by default and contain `tracks.csv`, `observations.csv` and `report.html` for the chosen playlist.

For the full command syntax, run `cantabile --help` or `cantabile <command> --help`.

## Storage and configuration

Copy `.env.example` to `.env` to change defaults. In **this source checkout**, paths are relative to your working directory unless you specify absolute locations.

| Variable | Default | Purpose |
|---|---|---|
| `CANTABILE_DB` | `cantabile.db` | SQLite database path |
| `CANTABILE_OUTPUT` | `./audio` | Downloaded audio |
| `CANTABILE_REPORTS_DIR` | `./reports` | CSV/HTML reports |
| `CANTABILE_STEMS_DIR` | `./stems` | Demucs outputs; use a drive with ample space |
| `CANTABILE_FORMAT` | `wav` | Download conversion format |
| `CANTABILE_TOLERANCE` | `7.0` | Duration difference (seconds) used for a high-confidence match |
| `CANTABILE_SEARCH_COUNT` | `6` | Source candidates requested per search |
| `CANTABILE_DEMUCS_MODEL` | `htdemucs` | Separation model |
| `CANTABILE_DEMUCS_DEVICE` | `cpu` | Separation device |
| `GENIUS_TOKEN` | unset | Optional lyrics fallback |

Additional settings are listed in `.env.example`, including cookies, proxy, TLS handling and separation format/segment options.

**Backups:** keep a copy of `cantabile.db` **and** the audio/stem directories. SQLite stores file references, not embedded recordings. Close the app before making a simple filesystem copy of its database.

**Audio formats:** saving YouTube audio as WAV or FLAC does **not** restore information lost in the source stream. Conversion can yield an uncompressed or losslessly encoded file, but the original online stream may already be lossy.

**Privacy:** the database, analysis results and reports are stored locally in this version. Source searches, downloads and lyrics retrieval contact third-party services when you invoke them. Cantabile is not an offline-only product.

## Known limitations

These are concrete issues in the current `0.1.0` checkout. They are not evidence that every corresponding bug remains in the separate `0.2.0` development build.

| Area | Known limitation | Consequence |
|---|---|---|
| Recording selection | Candidate scoring does not adequately validate the intended **track title**; channel/artist and duration can dominate. | A different song of similar length can be selected with `high` confidence. |
| Fallback search | Alternate query strings are prepared but not passed correctly to the provider. | Fallback searches can repeat the primary search. |
| Manual correction | Existing assets are skipped before a new override is processed. | Previously downloaded mistakes may resist correction. |
| Analysis freshness | MIR results are not tied to exact audio/stem revisions. | Existing results can remain after the input changes. |
| Completeness checks | A recorded stem can mark separation as already complete; stored asset paths are not always verified. | Missing or partial files may appear available. |
| Evidence/trust | Resolver priority is based on source type and recency rather than complete evidence validity. | A low-confidence measurement can outrank higher-confidence metadata. |
| Structure measures | `loop_score` is a raw statistical proxy, and `section_count` lacks timestamped boundaries or labels. | Do not interpret these outputs as calibrated probabilities or a full song-form analysis. |
| Validation | Offline tests cover selected units but do not prove correct matching, real-world acoustic accuracy or full end-to-end behavior. | Verify results on recordings you know. |

This project is suited to experimentation and development. It is **not suitable for unattended, high-confidence labeling of a music library** at the current revision.

## Upcoming 0.2.0 desktop build — progress

A **separate 0.2.0 development package** advances Cantabile beyond this source-only `0.1.0` snapshot. The status below is from its **20 September 2026 validation record**. It describes engineering work performed on that build, **not functionality installed from this repository ZIP**.

| Workstream | Last documented progress |
|---|---|
| Native Linux application | **Built and tested offscreen:** native Qt/pywebview window, launcher/icon, frozen executable and `.deb` package. Target platforms are Ubuntu 24.04 / Linux Mint 22, x86-64. |
| Persistent application state | **Implemented and tested:** saved paths and profiles, serialized jobs, logs, retry/cancellation, interrupted-job recovery and previous-database migration. |
| Library and acquisition | **Implemented and tested in controlled cases:** Spotify PKCE import, CSV import, preservation of imported lyrics, source override/refetch cases and source-job dispatch. Live provider acceptance is still required. |
| MIR and Demucs | **Executed in validation:** CPU analysis runtime setup, synthetic-audio MIR and a real four-stem Demucs run on a 12-second synthetic recording; MIR reran after stems changed. |
| Engineering checks | **Recorded passing:** 32 offline unit/integration tests, five dependency-direction contracts, Ruff, MyPy and the source-size gate. |
| Release acceptance | **Still open in the last record:** a clean install/upgrade/remove on the target desktop, live Spotify/YouTube workflows, external-drive unplug/recovery, real music accuracy and representative CPU/RAM benchmarking. |

The **installer and test results existed** in the September development package; this document does not claim that 0.2.0 has been publicly published or that those remaining checks were completed afterward. The goal of the next release is a usable native desktop foundation, **not completion of the full AI analysis roadmap**. No Windows or macOS installer is documented for this build.

## Long-term roadmap

Cantabile's intended scope extends far beyond global tempo, key or energy labels. The eventual system should preserve **what happens in a recording, when it happens, and the evidence supporting each claim**. The table below describes planned work, not shipped features.

| Stage | Planned result | Status |
|---|---|---|
| **1. Reliable evidence pipeline** | Verified recording identities; versioned assets and stems; analyzer inputs, model parameters and dependencies; validity-aware cached results. | **Priority development** |
| **2. Time-resolved MIR and musical form** | Beat, dynamics, timbre and harmony trajectories; timestamped sections, recurrences and optional verse/chorus labels. Evaluate librosa/MSAF and alternatives. | Planned |
| **3. Musical similarity** | Audio-window/section embeddings, searchable musical distance and passage-level comparison. Evaluate MERT-class models. | Planned |
| **4. Acoustic semantics** | Evidence-linked, time-varying instrumentation/texture/atmosphere tags and text-to-audio search. Evaluate CLAP-class models. | Planned |
| **5. Vocals and lyrics** | Vocal text recovery, line-to-audio alignment, acoustic vocal delivery and lyrical meaning as separate layers. Evaluate Whisper-class components and singing-specific methods. | Planned |
| **6. Combined track and playlist analysis** | Explanations linked to audio intervals; section-to-section relationships, theme changes, track comparisons and optional transition suggestions. | Planned |
| **7. Instrument transcription and notation** | Note events, chord timelines, piano MIDI/sheet music, MusicXML and guitar tablature. Evaluate Onsets and Frames, Omnizart, and a separate audio-to-notes + Fretting-Transformer pipeline. | Planned |

All seven analysis outputs remain in scope; none should be marked complete just because a model library can be installed. Model choice, quality, cost, licensing and performance must be evaluated against representative music. Four generic Demucs stems are **not** equivalent to isolated piano or guitar inputs.

Before expanding the interface, the next engineering steps are to version analysis artifacts, attach each observation to its actual input and time interval, and execute dependent analyses through registered backend contracts. Each milestone should ship with reproducible tests, inspectable data, a useful UI view and an export path.

## Architecture and development

The current project uses ports-and-adapters (hexagonal) boundaries:

| Path | Responsibility |
|---|---|
| `src/cantabile/domain/` | Track and playlist models, observations, resolution rules |
| `src/cantabile/ports/` | Interfaces for data stores, audio sources, analyzers and separation |
| `src/cantabile/application/` | Import, acquisition, analysis, separation and reporting workflows |
| `src/cantabile/adapters/` | CSV, SQLite, YouTube, lyrics, MIR, Demucs and export implementations |
| `src/cantabile/presentation/` | CLI and local browser GUI |
| `tests/` and `governance/` | Tests and dependency/size rules |

For a development environment, install the relevant optional dependencies above, then run:

```bash
python -m pytest -q
lint-imports --no-cache
python governance/tools/enforce_size.py
```

The `0.1.0` tests contain known fixture problems and are **not all clean in the current review**; a passing source check should not be confused with real recording and desktop acceptance testing. Runtime quality checks should include wrong-title/same-duration matches, source overrides, missing files, interrupted separations, changed audio inputs and stem-dependent reanalysis.

## License

[MIT](LICENSE). Dependencies and optional models carry their own licenses; model weights need separate review before redistribution.
