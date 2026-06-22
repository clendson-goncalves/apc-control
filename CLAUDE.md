# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**apcdeck** — controls an Akai APC mini on macOS to drive slides, screen FX (strobe/flash), and AI prompts, with a YAML **profile** system that maps the APC to any target software. Currently a prototype focused on macOS (Apple Silicon); kept structured so cross-platform comes later (divergence isolated in output backends). README is in Portuguese.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py                       # loads profiles/powerpoint.yaml
python main.py profiles/keynote.yaml # alternate profile
```

No test suite, linter, or build step is configured. If the APC hardware or MIDI libs are missing, `MidiListener` falls back to a SIMULATED mode that publishes a scripted set of events so the full pipeline (bus → mapper → backends) can be exercised without hardware. Backends with missing native libs (`pynput`, `osascript` off macOS) print `[name/dry]` lines instead of executing.

macOS permissions needed for real execution: **Privacy & Security → Accessibility** (for `pynput` key simulation) and **Automation** (for AppleScript control of PowerPoint/Keynote).

## Architecture

```
APC (MIDI in) → MidiListener → EventBus → Mapper(active profile) → Output Backends
                                                                   ├── keyboard   (pynput, universal)
                                                                   ├── applescript (osascript, macOS)
                                                                   ├── fx          (own overlay)
                                                                   ├── ai          (stub)
                                                                   ├── osc         (TODO)
                                                                   └── shell       (TODO)
```

- **`core/bus.py`** — `MidiEvent` (normalized note_on/note_off/control_change) + minimal synchronous pub/sub `EventBus`. Handler exceptions are swallowed with a log so the loop stays up.
- **`core/profiles.py`** — `Profile` and `Binding` dataclasses loaded from YAML in `profiles/`. A binding maps `(input_type, number)` → `(backend, do, args)`. Swapping target software = swapping profile, no code change.
- **`core/mapper.py`** — subscribes to the bus, routes events to the binding's backend. CCs trigger continuously; notes only on press (release is suppressed). Passes the raw MIDI value as `value=` so fader-driven actions can use it.
- **`midi/listener.py`** — opens the first port containing `APC_PORT_HINT` ("APC MINI"). Real and simulated loops both run on a daemon thread.
- **`outputs/base.py`** — every backend implements `execute(do, args, value)`. Add new backends by subclassing `Backend` and registering in `main.build_backends()`.
- **`fx/strobe.py`** — PySide6 overlay (frameless / translucent / always-on-top) that draws strobe/flash/blackout over any app. Currently a stub.

### Adding a backend

1. Create `outputs/<name>.py` with a `Backend` subclass that handles the `do` strings you want.
2. Register it in `main.build_backends()` under its profile key.
3. Reference it from a profile YAML via `action: { backend: <name>, do: <action>, args: {...} }`.

### Adding a profile

YAML with `name`, `description`, and a `bindings` list. Each entry has `input: { type: note|cc, number: N }` and `action: { backend, do, args }`. See `profiles/powerpoint.yaml` for the full pattern.

## Conventions

- Code is Python 3.10+ (uses `X | None`, `list[...]`). Comments and docstrings are in Portuguese — keep new code in the same language to stay consistent.
- TODOs intended for future implementation use the tag `# TODO(claude-code):`.
- **Strobe safety rule**: `MAX_SAFE_HZ = 3.0` (photosensitivity). Do NOT raise this cap without also adding a user-facing warning in the UI. The cap appears in both `outputs/fx_bridge.py` and `fx/strobe.py`.

## APC mini MIDI reference

- 8×8 grid: notes 0–63 (note_on / note_off).
- Faders: control_change CC 48–56 (8 faders + master), values 0–127.
- Round / side buttons: notes 64–98 (varies by firmware — confirm on device).
- LED feedback: send `note_on` back on the same note; velocity 0/1/3/5 = off / green / red / yellow. Not yet implemented.
