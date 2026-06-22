"""apc-control — ponto de entrada.

Liga MidiListener -> EventBus -> Mapper(perfil) -> backends.
Padrão abre a GUI. Use --headless para o loop antigo (CLI sem PySide6).

Uso:
    python main.py                                  # GUI, profiles/powerpoint.md
    python main.py profiles/keynote.md              # GUI com este perfil
    python main.py --headless profiles/x.md         # modo CLI (sem GUI)
"""
from __future__ import annotations

import argparse
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
        "fx": FxBackend(),
        "ai": AiBackend(),
    }


def run_headless(profile_path: Path) -> None:
    profile = load_profile(profile_path)
    print("=" * 56)
    print(f" apc-control — perfil: {profile.name}")
    print(f" bindings: {len(profile.bindings)}")
    print("=" * 56)

    bus = EventBus()
    backends = build_backends()
    mapper = Mapper(profile, backends)
    bus.subscribe(mapper.handle)

    listener = MidiListener(bus)
    print(f"[MIDI] portas disponíveis: {listener.list_ports() or '(nenhuma)'}")
    listener.start()

    print("\nPronto. Aperte os botões da APC. Ctrl+C para sair.\n")
    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nencerrando…")
        listener.stop()


def main() -> None:
    parser = argparse.ArgumentParser(prog="apc-control")
    parser.add_argument(
        "profile", nargs="?", default="profiles/powerpoint.md", type=Path,
        help="caminho do perfil .md (default: profiles/powerpoint.md)",
    )
    parser.add_argument("--headless", action="store_true", help="modo CLI sem GUI")
    args = parser.parse_args()

    if args.headless:
        run_headless(args.profile)
    else:
        from gui.app import run_gui   # import lazy: headless não precisa de Qt
        run_gui(args.profile)


if __name__ == "__main__":
    main()
