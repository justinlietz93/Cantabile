<img width="1774" height="887" alt="cantabile_banner" src="https://github.com/user-attachments/assets/30c5114e-93aa-4280-a9a6-4460908b848a" />

---

Cantabile turns a Spotify playlist into a trustworthy, analyzable library of the
real recordings. You export a playlist to CSV, Cantabile imports it, finds and
downloads the actual audio for each track, and stores everything in one local
database you can build analysis on top of.

It exists because Spotify's own numbers lie to you. Spotify describes each song
with nine scalar "audio features" (tempo, energy, valence, and so on). Those are
a lossy projection. On at least one real track the reported tempo was off by
half again the felt tempo. So Cantabile keeps the Spotify numbers but treats
them as the least trustworthy source, and is built to replace them with values
measured from the waveform itself.

---

## What it does today

- **Imports an Exportify CSV** into a local SQLite database: the tracks, the
  playlist order, and Spotify's nine audio features (stored as low-trust facts).
- **Finds the real recording** for each track on YouTube and downloads
  audio only (the video is discarded during extraction).
- **Matches by duration**, not just title, so it grabs the studio cut and not a
  live version, a remix, or a one-hour loop. It picks the candidate whose length
  is closest to Spotify's duration for that track.
- **Tells cover artists apart.** If two playlist entries are both "Abyss
  Watchers" by different YouTube artists, it matches each to its own channel
  instead of grabbing the same video twice.
- **Refuses duplicates.** No two tracks in a run can resolve to the same video.
- **Rates each match** high / medium / low so you know which ones to eyeball.
- **Suggests alternates** for weak matches by searching SoundCloud (which gives
  real durations) and Bandcamp (which finds self-released artists that never
  reached YouTube). Suggestions print as paste-ready override lines.
- **Lets you pin a source by hand** (an override) for any track, using any
  site yt-dlp supports: YouTube, Bandcamp, or SoundCloud.
- **Is resumable.** Rerun it and it skips tracks already downloaded.
- **Names files in playlist order**, zero-padded and ASCII-safe, so they sort
  correctly and never break on non-Latin characters.
- **Looks up lyrics** for every track (LRCLIB first, Genius as fallback) and
  stores them as Observations, marking instrumentals and caching results so
  reruns are instant.
- **Measures structure from the audio** (MIR): felt tempo, how much the tempo
  breathes, section count, and whether a piece loops or runs as a line. The
  felt tempo is stored as a high-trust `tempo` Observation, so it overrides
  Spotify's often-wrong number automatically.
- **Separates tracks into stems** (Demucs): drums, bass, vocals, other. When
  stems exist, MIR reads tempo off the drum stem and harmonic structure off the
  instrument stem, so a steady kick under a rubato lead no longer smears the
  measurement.
- **Exports reports** as CSV plus a polished local HTML report from the same
  resolved Observation view used by the app.
- **Runs a local browser GUI** for import, fetch, lyrics, MIR, separation, and
  export workflows without changing the domain/application architecture.

---

## How it works

Think of it as three stages over one database.

**1. Import.** You point Cantabile at an Exportify CSV. It reads every track,
its position in the playlist, and its Spotify features, and writes them to the
database. Each track is identified by its Spotify URI, so the same song is
recognized across all your playlists. Every Spotify feature is stored as an
*Observation*: a single fact (`tempo = 160`) tagged with where it came from
(`spotify`) and how much to trust it (low).

**2. Fetch.** For each track in order, Cantabile searches YouTube, scores the
results, and downloads the best one. Scoring is mostly "how close is this
video's length to Spotify's length," nudged by whether the channel name matches
the track's artist, and pushed down if the title looks like a live cut or loop.
The chosen video is recorded as an *AudioAsset* (where the file is, what URL it
came from, how confident the match was), and its measured length is stored as a
high-trust Observation.

**3. Analyze (coming).** Analyzers read the downloaded audio and write more
Observations: a felt tempo measured from the waveform, a section count, a
loop-vs-line score. Because an audio-measured tempo outranks Spotify's, anything
that later asks the database for "the tempo" gets the real one automatically,
while Spotify's wrong number stays on record for comparison.

The database is the source of truth. CSV is only how data gets in (import) and,
later, out (export). Audio files live on disk; the database holds the facts.

### Confidence levels

| Level | Meaning |
|-------|---------|
| `high` | Found a video within the tolerance window (default 7s) of Spotify's length |
| `medium` | Within 3x tolerance, or no Spotify duration to anchor on |
| `low` | Further off; review before trusting |
| `none` | No candidate found at all |
| `override` | You pinned this source by hand |

---

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .                 # core (import + fetch)
pip install -e ".[all]"          # + lyrics, audio, separation, and GUI
pip install -e ".[all,dev]"      # + every feature plus governance/test tools
```

`ffmpeg` must be on your PATH (it extracts the audio):
macOS `brew install ffmpeg`, Debian/Ubuntu `sudo apt install ffmpeg`,
Windows `winget install ffmpeg`.

---

## Using it

### Import a playlist

```bash
cantabile import inputs/Dominion.csv
```

Reads the CSV into the database. Prints how many tracks landed. Run it for as
many playlists as you like; they all share one database.

### Fetch the audio

```bash
# preview only: shows matches and suggestions, downloads nothing
cantabile fetch --playlist Dominion --dry-run

# import and fetch in one step
cantabile fetch --csv inputs/Dominion.csv

# fetch a playlist you already imported
cantabile fetch --playlist Dominion
```

Always dry-run first. Read the output, eyeball anything marked `low` or
`medium`, then run for real.

Each line of output looks like:

```
[ 10/58] high     ( +0.4s) RichaadEB - Abyss Watchers  downloaded
```

That is: track 10 of 58, a high-confidence match, the chosen video is 0.4s off
Spotify's length, and the file was downloaded.

### Fix the ones it got wrong

For weak matches, Cantabile prints suggestions you can paste straight into an
overrides file:

```
  # 39 No Oath - Carbon Plague  (low)
      39,https://nooath.bandcamp.com/track/carbon-plague   # bandcamp: No Oath - Carbon Plague [duration unverified]
```

Put good lines in a file (see `overrides.example.csv`) and rerun:

```bash
cantabile fetch --playlist Dominion --overrides overrides.csv
```

Or pin one inline without a file:

```bash
cantabile fetch --playlist Dominion --override 10=https://youtu.be/PYEVWZTv_ZY
```

An override accepts any yt-dlp-supported URL, so a Bandcamp or SoundCloud link
works for tracks that aren't on YouTube.

### Look up lyrics

```bash
cantabile lyrics --playlist Dominion           # LRCLIB, with Genius if a token is set
cantabile lyrics --csv inputs/Dominion.csv      # import + look up in one step
cantabile lyrics --playlist Dominion --force    # re-fetch even if already stored
```

For each track it tries LRCLIB (exact match on artist/title/album/duration,
then a fuzzy search), and falls back to Genius if you set a `GENIUS_TOKEN`.
Instrumentals are marked, results are cached to a JSON file so reruns are
instant, and tracks that already have lyrics are skipped unless you pass
`--force`. Lyrics land in the database as Observations tagged with their
source (lrclib or genius), not in a CSV column.

To enable Genius fallback, get a free token from the Genius API and set it:

```bash
export GENIUS_TOKEN="your_token"
```

### Analyze audio (MIR)

Once a playlist's audio is fetched, measure its structure from the waveform:

```bash
cantabile mir --playlist Dominion           # analyze fetched audio
cantabile mir --playlist Dominion --force    # re-analyze even if already done
```

For each track with audio it stores: `felt_tempo` and a competing `tempo`
(both audio-provenance, so the resolver returns these over Spotify's),
`tempo_variability` (how much the pulse breathes), `tempo_min`/`tempo_max`,
`section_count`, a `loop_score`, and a `structure` value of `loop` or `line`.
Tracks without fetched audio are skipped. Needs the audio extra
(`pip install -e ".[audio]"`) and ffmpeg.

If you've separated stems first (see below), MIR automatically reads tempo from
the drum stem and structure from the instrument stem, which is more accurate
for dense or polyrhythmic music.

### Separate into stems

Split each fetched track into drums, bass, vocals, and other, using Demucs:

```bash
cantabile separate --playlist Dominion
cantabile separate --playlist Dominion --two-stems vocals   # lighter: vocals/no_vocals
cantabile separate --playlist Dominion --out /mnt/bigdrive/cantabile_stems
```

This is the heavy stage. It needs the separation extra (`pip install -e
".[separation]"`, which pulls PyTorch) and ffmpeg. Read this before running it:

- **CPU-only unless you have an NVIDIA GPU.** On an integrated GPU it runs on
  the CPU, a few minutes per track. A full playlist is an overnight job. It's
  cached hard, so you pay the cost once; rerun only adds new tracks.
- **Watch your RAM.** On an 8 GB machine, close other apps and keep the default
  small `--segment` (lower it further if you hit swap thrash). Each chunk is
  processed separately to cap peak memory.
- **Put stems on a big drive.** They're large even as FLAC. Set
  `CANTABILE_STEMS_DIR` (or `--out`) to an external drive, never the system disk.

After separating, rerun `cantabile mir` and it will analyze from the stems.

### Export CSVs and an HTML report

```bash
cantabile export --playlist Dominion
cantabile export --playlist Dominion --out /mnt/reports
```

The export creates a playlist folder containing `tracks.csv`,
`observations.csv`, and `report.html`. The track CSV contains the resolved
trusted value for each observed feature; the observations CSV keeps the raw
source facts.

### Run the GUI

```bash
cantabile gui
cantabile gui --port 8770 --no-open
```

The GUI is local-only by default at `127.0.0.1:8765`. It uses the same store,
use cases, and report/export path as the CLI.

### fetch flags

| Flag | Meaning |
|------|---------|
| `--csv PATH` | Import this CSV, then fetch it |
| `--playlist NAME` | Fetch a playlist already in the database |
| `--dry-run` | Match and suggest only; download nothing |
| `--no-suggest` | Skip the Bandcamp/SoundCloud suggestion pass |
| `--overrides PATH` | A CSV of `seq,url` pins |
| `--override SEQ=URL` | A single inline pin (repeatable) |

---

## Configuration

Everything else is set by environment variables, or a `.env` file in the project
root (copy `.env.example`). These are read once at startup.

| Variable | Default | Meaning |
|----------|---------|---------|
| `CANTABILE_DB` | `cantabile.db` | the database file (your source of truth) |
| `CANTABILE_OUTPUT` | `./audio` | where downloaded audio folders go |
| `CANTABILE_FORMAT` | `wav` | `wav`/`flac` lossless (best for analysis), or `mp3`/`m4a`/`opus` |
| `CANTABILE_TOLERANCE` | `7.0` | seconds of length drift still counted "high" |
| `CANTABILE_SEARCH_COUNT` | `6` | YouTube candidates considered per track |
| `CANTABILE_SLEEP` | `1.0` | seconds between downloads (politeness) |
| `CANTABILE_REPORTS_DIR` | `./reports` | where report/export bundles are written |
| `CANTABILE_INSECURE` | `false` | skip TLS verification (only for self-signed proxies) |
| `CANTABILE_COOKIES` | | path to a cookies.txt for age/region-restricted videos |
| `CANTABILE_PROXY` | | proxy URL |

---

## Where your data lives

- **`cantabile.db`** — the SQLite database. Tracks, playlists, Observations,
  and audio assets. This is the thing to back up. You can open it with any
  SQLite browser and query it directly.
- **`audio/<PlaylistName>/`** — the numbered audio files, e.g.
  `001_Miracle_Of_Sound_-_Forever_Flame.wav`.
- **`reports/<PlaylistName>/`** — CSV and HTML report bundles.

The database has six tables: `tracks`, `playlists`, `playlist_entries`
(the ordering), `observations` (every fact with its source and confidence), and
`assets` (one downloaded file per track), plus `stems`.

---

## Troubleshooting

- **`ffmpeg not found`** — install it and make sure it's on PATH.
- **TLS / certificate errors** — only on networks with a self-signed proxy; set
  `CANTABILE_INSECURE=true`.
- **"Sign in to confirm you're not a bot"** — YouTube is rate-limiting your IP.
  Export a cookies.txt from your browser and set `CANTABILE_COOKIES`.
- **A track isn't on YouTube** (small self-released artists) — it'll match
  poorly. Check the Bandcamp suggestion and pin it as an override.
- **Wrong recording pulled** — lower `CANTABILE_TOLERANCE`, or pin the correct
  URL as an override.

---

## Architecture (the short version)

Cantabile is a Standards-Governed Hexagonal Monolith. A pure core (the data
model and rules) sits behind ports (contracts); concrete things like YouTube and
SQLite are adapters that plug into those ports; the CLI is a thin shell on top.
The one rule is that dependencies point inward, and it's enforced mechanically:
`lint-imports` fails the build if any inner layer reaches outward. That's what
lets the tool grow a GUI and new analyzers later without a rewrite.

```bash
lint-imports --no-cache                   # check the dependency rule
python governance/tools/enforce_size.py   # 500-LOC rule
pytest -q                                  # tests
```

These also run on every commit via `.pre-commit-config.yaml`. The full set of
rules is in `governance/policies/architecture_contracts.md`.

---

## Roadmap

Done: import, audio fetch with matching/dedup/overrides/suggestions, the lyrics
analyzer (LRCLIB + Genius), the MIR analyzer (felt tempo, variability, sections,
loop-vs-line), Demucs stem separation feeding stem-aware MIR, CSV/HTML export,
and a local workflow GUI.
