"""Carregador de perfis em Markdown.

Um perfil é um arquivo .md com:
  - H1 = nome do perfil
  - prosa após o H1 = descrição (até o "## Bindings")
  - tabela markdown sob "## Bindings" com colunas:
        | Input | N | Backend | Action | Args |
    onde Args é "k=v, k2=v2" (valores sempre string;
    consumidores fazem coerção, ex.: int(args["slide"])).

Trocar de software-alvo = trocar de perfil. Nenhum código muda.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Binding:
    input_type: str               # "note" | "cc"
    number: int
    backend: str                  # "keyboard" | "applescript" | "fx" | ...
    do: str                       # nome da ação dentro do backend
    args: dict[str, str] = field(default_factory=dict)


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


_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
_SEP_CELL_RE = re.compile(r"^:?-+:?$")


def _parse_args(s: str) -> dict[str, str]:
    s = s.strip()
    if not s:
        return {}
    out: dict[str, str] = {}
    for pair in s.split(","):
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _render_args(args: dict[str, str]) -> str:
    return ", ".join(f"{k}={v}" for k, v in args.items())


def parse_markdown(text: str) -> Profile:
    name = ""
    desc_lines: list[str] = []
    rows: list[list[str]] = []
    in_bindings = False
    in_description = False

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            name = stripped[2:].strip()
            in_description = True
            in_bindings = False
            continue
        if stripped.startswith("## Bindings"):
            in_description = False
            in_bindings = True
            continue
        if in_bindings and _ROW_RE.match(stripped):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            rows.append(cells)
            continue
        if in_description:
            desc_lines.append(line)

    bindings: list[Binding] = []
    for cells in rows:
        if len(cells) < 5:
            continue
        # pula header e separador
        if cells[0].lower() == "input" or _SEP_CELL_RE.match(cells[0]):
            continue
        input_type, number, backend, do, args_str = cells[:5]
        try:
            n = int(number)
        except ValueError:
            continue
        bindings.append(Binding(input_type, n, backend, do, _parse_args(args_str)))

    return Profile(
        name=name or "unnamed",
        description="\n".join(desc_lines).strip(),
        bindings=bindings,
    )


def render_markdown(profile: Profile) -> str:
    header = ("Input", "N", "Backend", "Action", "Args")
    data_rows = [
        (b.input_type, str(b.number), b.backend, b.do, _render_args(b.args))
        for b in profile.bindings
    ]
    all_rows = [header] + data_rows
    widths = [max(len(r[i]) for r in all_rows) for i in range(5)]

    def fmt(row: tuple[str, ...]) -> str:
        return "| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(row)) + " |"

    sep = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    table = [fmt(header), sep] + [fmt(r) for r in data_rows]

    parts = [f"# {profile.name}", ""]
    if profile.description:
        parts.append(profile.description)
        parts.append("")
    parts.append("## Bindings")
    parts.extend(table)
    return "\n".join(parts) + "\n"


def load_profile(path: str | Path) -> Profile:
    return parse_markdown(Path(path).read_text(encoding="utf-8"))


def save_profile(profile: Profile, path: str | Path) -> None:
    Path(path).write_text(render_markdown(profile), encoding="utf-8")
