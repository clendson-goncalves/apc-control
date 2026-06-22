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

    def __init__(self) -> None:
        self.signals = None        # GUI injeta FxSignals; None = modo dry
        self._strobe_on = False
        self._blackout_on = False

    def execute(
        self, do: str, args: dict[str, Any], value: int = 0, note: int | None = None
    ) -> bool | None:
        if do == "strobe_toggle":
            self._strobe_on = not self._strobe_on
            if self.signals:
                self.signals.strobe.emit(self._strobe_on)
            else:
                print(f"[fx/dry] strobo {'ON' if self._strobe_on else 'OFF'}")
        elif do == "strobe_rate":
            hz = min(round((value / 127) * MAX_SAFE_HZ, 2), MAX_SAFE_HZ)
            if self.signals:
                self.signals.rate.emit(hz)
            else:
                print(f"[fx/dry] rate -> {hz} Hz")
        elif do == "flash":
            if self.signals:
                self.signals.flash.emit()
            else:
                print("[fx/dry] flash!")
        elif do == "blackout_toggle":
            self._blackout_on = not self._blackout_on
            if self.signals:
                self.signals.blackout.emit()
            else:
                print(f"[fx/dry] blackout {'ON' if self._blackout_on else 'OFF'}")
        else:
            print(f"[fx] ação desconhecida: {do}")
