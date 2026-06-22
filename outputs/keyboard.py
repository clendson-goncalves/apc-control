"""Backend universal: simula teclas via pynput.

Funciona com qualquer app que tenha atalhos de teclado (PowerPoint, Keynote,
navegador, players). Manda a tecla para o app em foco.

Ações:
  key   -> args: { key: "right" }            tecla única
  combo -> args: { keys: ["cmd", "shift", "f"] }   atalho combinado
  text  -> args: { text: "olá" }             digita texto
"""
from __future__ import annotations

from typing import Any

from outputs.base import Backend


def _try_import_pynput():
    try:
        from pynput.keyboard import Controller, Key  # type: ignore
        return Controller, Key
    except Exception:
        return None, None


class KeyboardBackend(Backend):
    name = "keyboard"

    def __init__(self) -> None:
        Controller, Key = _try_import_pynput()
        self._Key = Key
        self._kbd = Controller() if Controller else None

    def _resolve(self, name: str):
        # nomes especiais (right, left, space, esc...) viram pynput Key.*
        if self._Key and hasattr(self._Key, name):
            return getattr(self._Key, name)
        return name  # caractere literal

    def execute(self, do: str, args: dict[str, Any], value: int = 0) -> None:
        if self._kbd is None:
            print(f"[keyboard/dry] {do} {args}")
            return

        if do == "key":
            k = self._resolve(args["key"])
            self._kbd.press(k); self._kbd.release(k)
        elif do == "combo":
            keys = [self._resolve(k) for k in args["keys"]]
            for k in keys:
                self._kbd.press(k)
            for k in reversed(keys):
                self._kbd.release(k)
        elif do == "text":
            self._kbd.type(args.get("text", ""))
        else:
            print(f"[keyboard] ação desconhecida: {do}")
