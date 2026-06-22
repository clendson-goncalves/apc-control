"""Entry point GUI: orquestra QApplication, bus, mapper, overlays, listener."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from core.bus import EventBus
from core.mapper import Mapper
from core.profiles import load_profile
from fx.strobe import StrobeOverlay
from gui.ai_overlay import AiOverlay
from gui.main_window import MainWindow
from gui.midi_bridge import MidiBridge
from gui.signals import AiSignals, FxSignals
from midi.listener import MidiListener
from outputs.ai import AiBackend
from outputs.applescript import AppleScriptBackend
from outputs.fx_bridge import FxBackend
from outputs.keyboard import KeyboardBackend


def run_gui(profile_path: Path) -> None:
    app = QApplication(sys.argv)

    # ---- backends + signals ----
    fx_signals = FxSignals()
    ai_signals = AiSignals()

    fx_backend = FxBackend(); fx_backend.signals = fx_signals
    ai_backend = AiBackend(); ai_backend.signals = ai_signals
    backends = {
        "keyboard": KeyboardBackend(),
        "applescript": AppleScriptBackend(),
        "fx": fx_backend,
        "ai": ai_backend,
    }

    # ---- bus + mapper ----
    bus = EventBus()
    profile = load_profile(profile_path)
    mapper = Mapper(profile, backends)
    bus.subscribe(mapper.handle)
    bridge = MidiBridge(bus)

    # ---- overlays + ligação dos signals ----
    fx_overlay = StrobeOverlay()
    fx_signals.strobe.connect(fx_overlay.set_strobe)
    fx_signals.rate.connect(fx_overlay.set_rate)
    fx_signals.flash.connect(fx_overlay.flash)
    fx_signals.blackout.connect(fx_overlay.toggle_blackout)

    ai_overlay = AiOverlay()
    ai_signals.token.connect(ai_overlay.append_token)
    ai_signals.done.connect(ai_overlay.on_done)
    ai_signals.error.connect(ai_overlay.on_error)
    ai_signals.dismiss.connect(ai_overlay.dismiss)

    # ---- listener + main window ----
    listener = MidiListener(bus)
    window = MainWindow(bridge, mapper, listener, fx_signals, ai_backend, profile_path)
    window.show()

    print(f"[apc-control] perfil: {profile.name} | bindings: {len(profile.bindings)}")
    listener.start()

    try:
        sys.exit(app.exec())
    finally:
        listener.stop()
