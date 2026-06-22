# apc-control

Control an **Akai APC mini** on macOS to advance slides, trigger screen effects
(strobe/flash), and drive any software — using a Markdown **profile** system that
maps the APC to any application.

> Prototype focused on **macOS (Apple Silicon)**. The code is structured to go
> cross-platform later (the divergence stays isolated in the output backends).

---

> ⚠️ **Photosensitivity warning**
> The strobe effect is capped at **3.0 Hz** (`MAX_SAFE_HZ`). The GUI shows a
> warning before enabling the strobe for the first time. People with
> photosensitive epilepsy should be careful with any flashing effect.

---

## Architecture

```
APC (MIDI in)
    │
    ▼
MidiListener ──► EventBus ──► Mapper (active profile) ──► Output Backends
    │                                                     ├── keyboard    (pynput, universal)
    │                                                     ├── applescript (osascript, macOS)
    │                                                     └── fx ──► StrobeOverlay (over any app)
    │
    └── LedController ──► APC (MIDI out, LED feedback)

GUI (PySide6)
    ├── LivePanel     — live event log + FX controls
    ├── BindingEditor — learn/edit bindings and save them to the profile
    ├── ApcGrid       — visual representation of the APC 8×8 grid
    └── MidiBridge    — bridge between the EventBus and Qt signals
```

Core concepts:
- **EventBus**: everything the APC emits becomes a `MidiEvent` published on the bus.
- **Profile** (Markdown in `profiles/`): maps note/CC → action. Switching software = switching profile.
- **Output backends** (`outputs/`): each abstract action is executed by a registered backend.
- **FX overlay** (`fx/strobe.py`): strobe/flash/blackout run on top of any app.
- **LED feedback** (`midi/output.py`): mapped pads light up so you can see what's bound (see below).

## LED feedback

When the app starts, every pad that has a **note** binding in the active profile
lights up **green** (idle) — so you can tell at a glance which pads do something.
Pressing a pad changes its color and then returns to idle:

| Action type                         | On press         | After          |
| ----------------------------------- | ---------------- | -------------- |
| Momentary (slide, `ppt_goto`, flash)| flashes **red**  | back to green  |
| Toggle ON (strobe / blackout)       | **red** (steady) | —              |
| Toggle OFF                          | —                | back to green  |

Faders (CC inputs) have no LED. On shutdown all pads are turned off. Without APC
hardware (or `mido`), the controller falls back to a dry-run that prints
`[led/dry] ...` lines instead of sending MIDI.

## Setup (macOS, M1)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Permissions to grant under **Settings → Privacy & Security**:
- **Accessibility** → for the `keyboard` backend (pynput) to simulate keystrokes.
- **Automation** → for the `applescript` backend to control PowerPoint/Keynote.

## GUI vs --headless

```bash
# GUI (default) — PySide6 window with live log, FX controls, and binding editor
python main.py

# Headless (CLI) — loads the profile and runs without a window; Ctrl+C to quit
python main.py --headless profiles/powerpoint.md
```

In either mode, if no APC is connected the app enters **simulation**: it
publishes a scripted set of events automatically so the full pipeline can be
exercised without hardware.

## Profiles (Markdown format)

Profiles live in `profiles/` as `.md` files. Each profile has a descriptive
header and a `## Bindings` table with the columns:
`Input`, `N` (note or CC number), `Backend`, `Action`, and `Args`.

Example (`profiles/powerpoint.md`):

```markdown
# PowerPoint

Example profile for slide navigation.

## Bindings
| Input | N  | Backend     | Action          | Args                                        |
|-------|----|-------------|-----------------|---------------------------------------------|
| note  | 0  | keyboard    | key             | key=right                                   |
| note  | 1  | keyboard    | key             | key=left                                    |
| note  | 24 | fx          | strobe_toggle   |                                             |
| note  | 25 | fx          | flash           |                                             |
| cc    | 48 | fx          | strobe_rate     |                                             |
```

The `Args` column uses `key=value` pairs separated by commas (e.g.
`key=right, slide=1`). An empty cell means no arguments. The parser lives in
`core/profiles.py`.

## APC mini reference

- 8×8 grid: notes 0–63 (note_on/note_off).
- Faders: control_change, CC 48–56 (8 faders + master), values 0–127.
- Round / side buttons: notes 64–98 (varies by firmware — confirm on device).
- LED feedback: send `note_on` back on the same note; velocity 0/1/3/6 =
  off/green/red/yellow-blink (varies by firmware).
