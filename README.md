# Cantabile

A playlist audio and structure lab. Import an Exportify CSV, fetch the real
recordings, and (next) analyze their structure from the waveform instead of
Spotify's lossy nine-scalar projection.

Built as a **Standards-Governed Hexagonal Monolith (SGHM)**: a domain-centered
core behind ports, swappable adapters, and a governance plane that enforces the
architecture mechanically so it can grow from CLI to GUI without a rewrite.

## The one rule

Dependencies point inward. `domain` depends on nothing; `ports` on `domain`;
`application` and `adapters` on `ports`; only `presentation` wires concrete
adapters. This isn't a guideline, it's a build check: `.importlinter` fails the
commit if any layer reaches outward.

```
src/cantabile/
  domain/        Track, Playlist, Observation, AudioAsset  (pure)
  ports/         StorePort, SourceProviderPort, AnalyzerPort  (contracts)
  adapters/      ingest (exportify) · providers (youtube) · suggesters · store (sqlite)
  application/   use_cases (import, acquire) · services (matching)
  presentation/  cli (composition root)
  shared/        settings  (leaf, no business rules)
governance/      import contracts · 500-LOC rule · CI gates
```

## Data model

Every fact is an `Observation`: a feature value tagged with its `Provenance`
and `Confidence`. Spotify's tempo and the audio's felt tempo coexist; a
resolver returns the higher-trust one. The store is SQLite (the source of
truth); CSV is import/export only.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # add ",lyrics,audio" for those analyzers
# ffmpeg must be on PATH for audio extraction
```

## Use

```bash
cantabile import inputs/Dominion.csv               # CSV -> SQLite
cantabile fetch --playlist Dominion --dry-run       # preview matches + suggestions
cantabile fetch --csv inputs/Dominion.csv           # import + fetch in one step
cantabile fetch --playlist Dominion --overrides overrides.csv
```

Settings come from env or `.env` (see `.env.example`); CLI flags override them.

## Governance

```bash
lint-imports                              # dependency direction
python governance/tools/enforce_size.py   # 500-LOC rule
```

Both run on every commit via `.pre-commit-config.yaml`.

## Roadmap

The fetch pipeline is the first plugin set. Next, against the same ports:
a lyrics analyzer (LRCLIB + Genius) and an MIR analyzer (felt tempo, sections,
loop-vs-line), each emitting `Observation`s into the store. Then a GUI as a new
presentation adapter, reading the store directly.
