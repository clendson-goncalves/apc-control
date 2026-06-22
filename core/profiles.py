"""Carregador de perfis.

Um perfil mapeia entradas da APC (notas/CCs) para ações abstratas.
Trocar de software-alvo = carregar outro perfil. Nenhum código muda.

Formato YAML (ver profiles/powerpoint.yaml):

    name: PowerPoint
    description: ...
    bindings:
      - input: { type: note, number: 0 }
        action: { backend: keyboard, do: key, args: { key: right } }
      - input: { type: cc, number: 48 }
        action: { backend: fx, do: strobe_rate }
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Binding:
    input_type: str           # "note" | "cc"
    number: int
    backend: str              # "keyboard" | "applescript" | "fx" | "osc" | "ai" | "shell"
    do: str                   # nome da ação dentro do backend
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class Profile:
    name: str
    description: str
    bindings: list[Binding]

    def find(self, input_type: str, number: int) -> Binding | None:
        for b in self.bindings:
            if b.input_type == input_type and b.number == number:
                return b
        return None


def load_profile(path: str | Path) -> Profile:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    bindings: list[Binding] = []
    for raw in data.get("bindings", []):
        inp = raw["input"]
        act = raw["action"]
        bindings.append(
            Binding(
                input_type=inp["type"],
                number=int(inp["number"]),
                backend=act["backend"],
                do=act["do"],
                args=act.get("args", {}) or {},
            )
        )
    return Profile(
        name=data.get("name", "unnamed"),
        description=data.get("description", ""),
        bindings=bindings,
    )
