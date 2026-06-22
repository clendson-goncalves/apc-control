"""apcdeck — ponto de entrada.

Liga tudo: listener MIDI -> EventBus -> Mapper(perfil) -> backends.
Roda no M1. Sem APC/libs, entra em modo simulado para validar o fluxo.

Uso:
    python main.py                       # usa profiles/powerpoint.yaml
    python main.py profiles/keynote.yaml
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from core.bus import EventBus
from core.mapper import Mapper
from core.profiles import load_profile
from midi.listener import MidiListener
from outputs.ai import AiBackend
from outputs.applescript import AppleScriptBackend
from outputs.fx_bridge import FxBackend
from outputs.keyboard import KeyboardBackend


def build_backends() -> dict:
    return {
        "keyboard": KeyboardBackend(),
        "applescript": AppleScriptBackend(),
        "fx": FxBackend(overlay=None),   # TODO(claude-code): passar StrobeOverlay
        "ai": AiBackend(),
        # "osc": OscBackend(),           # TODO(claude-code)
    }


def main() -> None:
    profile_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("profiles/powerpoint.yaml")
    profile = load_profile(profile_path)

    print("=" * 56)
    print(f" apcdeck — perfil: {profile.name}")
    print(f" bindings: {len(profile.bindings)}")
    print("=" * 56)

    bus = EventBus()
    backends = build_backends()
    mapper = Mapper(profile, backends)

    bus.subscribe(mapper.handle)

    listener = MidiListener(bus)
    ports = listener.list_ports()
    print(f"[MIDI] portas disponíveis: {ports or '(nenhuma / lib ausente)'}")
    listener.start()

    print("\nPronto. Aperte os botões da APC (ou veja a simulação). Ctrl+C para sair.\n")
    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nencerrando…")
        listener.stop()


if __name__ == "__main__":
    main()
