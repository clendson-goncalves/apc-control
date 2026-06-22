"""Backend FX: efeitos de tela próprios (strobo/flash/blackout).

Independente do software-alvo — é uma janela overlay sua, funciona por cima
de qualquer coisa. Aqui fica apenas a PONTE (recebe ações do mapper e repassa
ao overlay). O overlay em si (PySide6) está em fx/strobe.py.

Ações:
  strobe_toggle              liga/desliga strobo
  strobe_rate  (fader)       value 0-127 -> frequência (LIMITAR a ~3 Hz!)
  flash                      flash branco único
  blackout_toggle            tela preta on/off

TODO(claude-code): instanciar o StrobeOverlay e conectar estes métodos a ele.
"""
from __future__ import annotations

from typing import Any

from outputs.base import Backend

MAX_SAFE_HZ = 3.0  # segurança fotossensibilidade — NÃO remover sem aviso na UI


class FxBackend(Backend):
    name = "fx"

    def __init__(self, overlay: Any | None = None) -> None:
        self.overlay = overlay  # StrobeOverlay quando implementado
        self._strobe_on = False

    def execute(self, do: str, args: dict[str, Any], value: int = 0) -> None:
        if do == "strobe_toggle":
            self._strobe_on = not self._strobe_on
            print(f"[fx] strobo {'ON' if self._strobe_on else 'OFF'}")
            # TODO(claude-code): self.overlay.set_strobe(self._strobe_on)
        elif do == "strobe_rate":
            hz = round((value / 127) * MAX_SAFE_HZ, 2)
            print(f"[fx] strobo rate -> {hz} Hz (cap {MAX_SAFE_HZ})")
            # TODO(claude-code): self.overlay.set_rate(hz)
        elif do == "flash":
            print("[fx] flash!")
            # TODO(claude-code): self.overlay.flash()
        elif do == "blackout_toggle":
            print("[fx] blackout toggle")
            # TODO(claude-code): self.overlay.toggle_blackout()
        else:
            print(f"[fx] ação desconhecida: {do}")
