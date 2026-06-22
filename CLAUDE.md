# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**apc-control** — controls an Akai APC mini on macOS to drive slides and screen FX (strobe/flash), with a Markdown **profile** system that maps the APC to any target software. Currently a prototype focused on macOS (Apple Silicon); kept structured so cross-platform comes later (divergence isolated in output backends). README is in English.

## Commands

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python main.py                                # GUI default (PySide6 window)
python main.py --headless profiles/powerpoint.md  # CLI/headless mode, no window

pytest tests/test_profiles.py -v             # Markdown profile parser tests (7 PASS expected)
```

If the APC hardware or MIDI libs are missing, `MidiListener` falls back to a **simulated** mode that publishes a scripted set of events so the full pipeline (bus → mapper → backends) can be exercised without hardware. Backends with missing native libs (`pynput`, `osascript` off macOS) print `[name/dry]` lines instead of executing.

macOS permissions needed for real execution: **Privacy & Security → Accessibility** (for `pynput` key simulation) and **Automation** (for AppleScript control of PowerPoint/Keynote).

## Architecture

```
APC (MIDI in)
    │
    ▼
MidiListener ──► EventBus ──► Mapper(active profile) ──► Output Backends
    │                              │                      ├── keyboard    (pynput, universal)
    │                              │                      ├── applescript (osascript, macOS)
    │                              │                      └── fx ──► StrobeOverlay
    │                              ▼
    │                       LedController ──► APC (MIDI out, LED feedback)
    │
    └── GUI (PySide6) ◄── MidiBridge ◄── EventBus
            ├── LivePanel      — live event log + FX controls
            ├── BindingEditor  — learn/edit/save bindings
            └── ApcGrid        — visual 8×8 grid representation
```

### File responsibilities

- **`core/bus.py`** — `MidiEvent` (normalized note_on/note_off/control_change) + minimal synchronous pub/sub `EventBus`. Handler exceptions are swallowed with a log so the loop stays up.
- **`core/profiles.py`** — `Profile` and `Binding` dataclasses loaded from the Markdown table in `profiles/`. A binding maps `(input_type, number)` → `(backend, do, args)`. Swapping target software = swapping profile, no code change.
- **`core/mapper.py`** — subscribes to the bus, routes events to the binding's backend. CCs trigger continuously; notes only on press (release is suppressed). Passes the raw MIDI value as `value=` and the note as `note=`. `led_behavior(input_type, do)` infers LED feedback per action type (cc→none, `*_toggle`→toggle, else flash) and drives the `LedController`. Module-level `idle_notes(profile)` returns the note bindings to light at startup (faders excluded).
- **`midi/listener.py`** — opens the first port containing `APC_PORT_HINT` ("APC MINI"). Real and simulated loops both run on a daemon thread.
- **`midi/output.py`** — `LedController`; opens the APC's **output** port (reuses `APC_PORT_HINT`) and sends `note_on` back to light LEDs by velocity (`OFF/GREEN/RED/YELLOW_BLINK` — varies by firmware). `set_idle(notes)` lights the mapped pads green at startup and records each pad's resting color; actions return to that idle color instead of going dark. `flash` (momentary red, auto-off timer → restore idle), `set` (toggle: red steady / restore idle), `clear` (restore idle), `blink` (hardware blink). `close` turns all idle pads off. Falls back to `[led/dry]` without hardware/`mido`.
- **`outputs/base.py`** — every backend implements `execute(do, args, value=0, note=None) -> bool | None` (toggles return their new state for LED feedback). Add new backends by subclassing `Backend` and registering in `main.build_backends()`.
- **`outputs/fx_bridge.py`** — `FxBackend`; bridges mapper actions to `StrobeOverlay`. Defines `MAX_SAFE_HZ = 3.0` (single source of truth for the photosensitivity cap).
- **`fx/strobe.py`** — PySide6 frameless/translucent/always-on-top overlay for strobe/flash/blackout over any app. Imports `MAX_SAFE_HZ` from `outputs/fx_bridge.py`.
- **`gui/signals.py`** — Qt signal definitions (`FxSignals`) shared across the GUI.
- **`gui/midi_bridge.py`** — bridges the thread-safe `EventBus` into Qt signals so GUI widgets receive `MidiEvent` objects on the main thread.
- **`gui/_macos.py`** — macOS-specific helpers (window level, permission checks).
- **`gui/apc_grid.py`** — visual representation of the APC mini 8×8 grid; highlights active pads.
- **`gui/binding_editor.py`** — editor tab; supports MIDI Learn (press a pad to fill the form) and saves bindings back to the Markdown profile.
- **`gui/live_panel.py`** — live tab; shows event log, Flash button, Strobe enable checkbox + rate slider.
- **`gui/main_window.py`** — `QMainWindow` that hosts `LivePanel` and `BindingEditor` tabs.
- **`gui/app.py`** — entry point for GUI mode; wires `MidiBridge`, signals, overlays, and starts the Qt event loop.

### Adding a backend

1. Create `outputs/<name>.py` with a `Backend` subclass that handles the `do` strings you want.
2. Register it in `main.build_backends()` under its profile key.
3. Reference it from a profile via the `Backend` column in the Markdown table.

### Adding a profile

Create `profiles/<name>.md` with a header and a `## Bindings` Markdown table with columns: `Input`, `N`, `Backend`, `Action`, `Args`. See `profiles/powerpoint.md` for the canonical example. The `Args` column uses `key=value` pairs separated by commas (e.g., `key=right, slide=1`); empty cell means no args.

**`Binding.args` is always `dict[str, str]`** — consumers are responsible for casting to the correct type (e.g., `int(args["slide"])`).

## Conventions

- Code is Python 3.10+ (uses `X | None`, `list[...]`). Comments and docstrings are in Portuguese — keep new code in the same language to stay consistent. (English is acceptable in this CLAUDE.md and in technical identifiers.)
- TODOs intended for future implementation use the tag `# TODO(claude-code):`.
- **Strobe safety rule**: `MAX_SAFE_HZ = 3.0` lives in `outputs/fx_bridge.py` (single source of truth). `fx/strobe.py` imports it from there. Do NOT raise this cap without also adding a user-facing warning in the UI.

## APC mini MIDI reference

- 8×8 grid: notes 0–63 (note_on / note_off).
- Faders: control_change CC 48–56 (8 faders + master), values 0–127.
- Round / side buttons: notes 64–98 (varies by firmware — confirm on device).
- LED feedback: send `note_on` back on the same note; velocity 0/1/3/5 = off / green / red / yellow.
