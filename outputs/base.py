"""Interface comum dos backends de saída.

Cada backend implementa execute(do, args, value). 'do' é o nome da ação;
'args' vem do perfil; 'value' é o valor cru do MIDI (útil para faders).
"""
from __future__ import annotations

from typing import Any


class Backend:
    name: str = "base"

    def execute(self, do: str, args: dict[str, Any], value: int = 0) -> None:
        raise NotImplementedError
