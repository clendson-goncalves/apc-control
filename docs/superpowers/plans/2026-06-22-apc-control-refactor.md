# apc-control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refatorar o protótipo "apcdeck" em "apc-control": trocar perfis YAML por Markdown, ganhar uma GUI PySide6 (editor de bindings + painel ao vivo), e implementar strobo e IA como overlays que funcionam sobre qualquer app.

**Architecture:** A `EventBus` síncrona continua sendo o ponto central. O `MidiListener` (thread daemon) publica eventos; o `Mapper` despacha para backends. A GUI assina o bus via um `MidiBridge(QObject)` que reemite cada evento como `Signal` (auto-marshalling para a thread do Qt). Backends FX e IA recebem um objeto `signals` (FxSignals/AiSignals) injetado pela GUI — em modo `--headless` o atributo fica `None` e os backends caem no print legado. Overlays (`StrobeOverlay`, `AiOverlay`) são janelas top-level frameless/translucent/always-on-top que sobem acima do menu bar via pyobjc no macOS.

**Tech Stack:** Python 3.10+, PySide6, mido + python-rtmidi, pynput, anthropic SDK (claude-haiku-4-5-20251001), pyobjc-framework-Cocoa, pytest (novo — só para o parser Markdown).

## Global Constraints

- Idioma: comentários e docstrings em português (consistente com a base atual).
- Segurança fotossensibilidade: `MAX_SAFE_HZ = 3.0` é hard cap. Fonte única em `outputs/fx_bridge.py`; `fx/strobe.py` importa de lá. GUI mostra aviso "AVISO FOTOSSENSIBILIDADE" antes de habilitar strobo pela primeira vez na sessão.
- Modos dry-run preservados: sem APC/mido → simulador. Sem pynput → `[keyboard/dry]`. Sem macOS → `[applescript/dry]`. Sem `ANTHROPIC_API_KEY` ou SDK → `[ai/dry]` que ainda emite tokens para o overlay.
- Plataforma alvo: macOS Apple Silicon. Evitar hardcode mac-only sem necessidade, mas pyobjc é aceito para subir overlay acima do menu bar.
- Sem novas abstrações para features não pedidas (sem backend OSC, sem auto-troca de perfil — ficam como TODO).
- AI model padrão: `claude-haiku-4-5-20251001` (rápido, streaming).
- Sem `--no-verify` em commits. Sem `git push` automático.

## File Layout

```
apc-control/
├── main.py                       # MODIFIED — argparse + run_headless/run_gui
├── requirements.txt              # MODIFIED — remove PyYAML; add PySide6, anthropic, pyobjc
├── core/
│   ├── bus.py                    # UNCHANGED
│   ├── mapper.py                 # UNCHANGED
│   └── profiles.py               # REWRITTEN — parser/serializador Markdown
├── midi/listener.py              # UNCHANGED
├── outputs/
│   ├── base.py                   # UNCHANGED
│   ├── keyboard.py               # UNCHANGED
│   ├── applescript.py            # MODIFIED — coerce slide=int
│   ├── fx_bridge.py              # MODIFIED — emite via self.signals
│   └── ai.py                     # REWRITTEN — Anthropic streaming + signals
├── fx/
│   └── strobe.py                 # REWRITTEN — StrobeOverlay real (PySide6)
├── gui/                          # NEW package
│   ├── __init__.py
│   ├── app.py                    # entry run_gui(); orquestra tudo
│   ├── signals.py                # FxSignals, AiSignals (QObject carriers)
│   ├── midi_bridge.py            # MidiBridge: bus → Signal
│   ├── _macos.py                 # raise_above_menu_bar() via pyobjc
│   ├── ai_overlay.py             # AiOverlay (texto streaming)
│   ├── apc_grid.py               # APCGrid (8x8 + 9 faders)
│   ├── binding_editor.py         # aba editor
│   ├── live_panel.py             # aba ao vivo
│   └── main_window.py            # QMainWindow + abas
├── profiles/
│   └── powerpoint.md             # NEW (substitui .yaml)
├── tests/                        # NEW
│   ├── __init__.py
│   └── test_profiles.py          # round-trip Markdown
├── CLAUDE.md                     # MODIFIED — novo arch + GUI + .md format
└── README.md                     # MODIFIED — rebrand + GUI + warning
```

---

## Task 1: Dependências + scaffold de testes

**Files:**
- Modify: `requirements.txt`
- Create: `tests/__init__.py` (vazio)

**Interfaces:**
- Produces: pytest disponível; `pip install -r requirements.txt` instala PySide6, anthropic, pyobjc.

- [ ] **Step 1: Atualizar `requirements.txt`**

```
mido>=1.3.0
python-rtmidi>=1.5.0
pynput>=1.7.6
PySide6>=6.6.0
anthropic>=0.40.0
pyobjc-framework-Cocoa>=10.0
pytest>=8.0.0
# Futuro (descomente quando for usar):
# python-osc>=1.8.0     # backend OSC (OBS/VJ)
```

- [ ] **Step 2: Criar `tests/__init__.py` vazio**

- [ ] **Step 3: Instalar deps**

Run: `source .venv/bin/activate && pip install -r requirements.txt`
Expected: instalação sem erros; `python -c "import PySide6, anthropic, AppKit, pytest"` retorna sem ImportError.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt tests/__init__.py
git commit -m "chore: add GUI/AI/test deps, remove PyYAML"
```

---

## Task 2: Markdown profile parser (TDD)

**Files:**
- Modify: `core/profiles.py` (reescrita)
- Create: `tests/test_profiles.py`

**Interfaces:**
- Produces:
  - `load_profile(path: str | Path) -> Profile`
  - `save_profile(profile: Profile, path: str | Path) -> None`
  - `parse_markdown(text: str) -> Profile`
  - `render_markdown(profile: Profile) -> str`
  - Dataclasses `Binding(input_type, number, backend, do, args: dict[str, str])` e `Profile(name, description, bindings)` — mesma forma de hoje, exceto `args` agora sempre `dict[str, str]` (consumidores fazem cast).

- [ ] **Step 1: Escrever testes que falham**

Criar `tests/test_profiles.py`:

```python
"""Testes do parser/serializer de perfis Markdown."""
from core.profiles import (
    Binding, Profile, parse_markdown, render_markdown, load_profile, save_profile,
)

SAMPLE_MD = """# PowerPoint

Perfil de exemplo.

## Bindings
| Input | N  | Backend  | Action | Args      |
|-------|----|----------|--------|-----------|
| note  | 0  | keyboard | key    | key=right |
| cc    | 48 | fx       | strobe_rate |      |
| note  | 56 | ai       | prompt | prompt=Resuma o slide |
"""


def test_parse_extracts_name_and_description():
    p = parse_markdown(SAMPLE_MD)
    assert p.name == "PowerPoint"
    assert "Perfil de exemplo." in p.description


def test_parse_extracts_bindings():
    p = parse_markdown(SAMPLE_MD)
    assert len(p.bindings) == 3
    assert p.bindings[0] == Binding("note", 0, "keyboard", "key", {"key": "right"})
    assert p.bindings[1] == Binding("cc", 48, "fx", "strobe_rate", {})
    assert p.bindings[2].args == {"prompt": "Resuma o slide"}


def test_args_with_multiple_pairs():
    md = SAMPLE_MD + "| note  | 1  | keyboard | combo  | keys=cmd+shift+f, hold=true |\n"
    p = parse_markdown(md)
    assert p.bindings[-1].args == {"keys": "cmd+shift+f", "hold": "true"}


def test_round_trip_preserves_bindings():
    p1 = parse_markdown(SAMPLE_MD)
    out = render_markdown(p1)
    p2 = parse_markdown(out)
    assert p1.name == p2.name
    assert p1.bindings == p2.bindings


def test_load_and_save(tmp_path):
    path = tmp_path / "x.md"
    path.write_text(SAMPLE_MD, encoding="utf-8")
    p = load_profile(path)
    out = tmp_path / "y.md"
    save_profile(p, out)
    p2 = load_profile(out)
    assert p.bindings == p2.bindings


def test_find_returns_binding_or_none():
    p = parse_markdown(SAMPLE_MD)
    assert p.find("note", 0).backend == "keyboard"
    assert p.find("cc", 48).do == "strobe_rate"
    assert p.find("note", 99) is None


def test_empty_args_renders_empty_column():
    p = Profile("X", "", [Binding("note", 0, "fx", "flash", {})])
    out = render_markdown(p)
    # ultima coluna vazia, mas a tabela continua valida
    assert "| note" in out
    p2 = parse_markdown(out)
    assert p2.bindings[0].args == {}
```

- [ ] **Step 2: Rodar testes — devem falhar**

Run: `pytest tests/test_profiles.py -v`
Expected: FAIL (módulo `core.profiles` ainda usa YAML; funções novas não existem).

- [ ] **Step 3: Reescrever `core/profiles.py`**

```python
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
    backend: str                  # "keyboard" | "applescript" | "fx" | "ai" | ...
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
```

- [ ] **Step 4: Rodar testes — devem passar**

Run: `pytest tests/test_profiles.py -v`
Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add core/profiles.py tests/test_profiles.py
git commit -m "feat: replace YAML profile loader with Markdown table parser"
```

---

## Task 3: Converter perfil de exemplo YAML → Markdown

**Files:**
- Create: `profiles/powerpoint.md`
- Delete: `profiles/powerpoint.yaml`

**Interfaces:**
- Consumes: parser do Task 2.

- [ ] **Step 1: Criar `profiles/powerpoint.md`**

```markdown
# PowerPoint

Perfil de exemplo. Navegação por teclado (universal) + slides diretos via
AppleScript + efeitos próprios + uma ação de IA. Ajuste os 'N' às notas
reais da sua APC mini (use o log do listener para descobri-las).

## Bindings
| Input | N  | Backend     | Action        | Args                                        |
|-------|----|-------------|---------------|---------------------------------------------|
| note  | 0  | keyboard    | key           | key=right                                   |
| note  | 1  | keyboard    | key           | key=left                                    |
| note  | 8  | keyboard    | key           | key=b                                       |
| note  | 16 | applescript | ppt_goto      | slide=1                                     |
| note  | 17 | applescript | ppt_goto      | slide=10                                    |
| note  | 24 | fx          | strobe_toggle |                                             |
| note  | 25 | fx          | flash         |                                             |
| note  | 26 | fx          | blackout_toggle |                                           |
| cc    | 48 | fx          | strobe_rate   |                                             |
| note  | 56 | ai          | prompt        | prompt=Explique o slide atual em uma frase. |
| note  | 57 | ai          | dismiss       |                                             |
```

- [ ] **Step 2: Validar que o parser lê**

Run: `python -c "from core.profiles import load_profile; p = load_profile('profiles/powerpoint.md'); print(p.name, len(p.bindings))"`
Expected: `PowerPoint 11`

- [ ] **Step 3: Deletar YAML antigo**

```bash
rm profiles/powerpoint.yaml
```

- [ ] **Step 4: Commit**

```bash
git add profiles/powerpoint.md profiles/powerpoint.yaml
git commit -m "feat: convert powerpoint profile to Markdown"
```

---

## Task 4: Coerção de tipos no AppleScript backend

**Files:**
- Modify: `outputs/applescript.py`

**Interfaces:**
- Consumes: `Binding.args: dict[str, str]` (sempre string agora).

- [ ] **Step 1: Adicionar coerção em `execute()`**

Substituir a parte que monta o template para coagir `slide` em `int` quando presente:

```python
def execute(self, do: str, args: dict[str, Any], value: int = 0) -> None:
    if do == "run":
        self._osascript(args.get("script", ""))
        return
    template = SCRIPTS.get(do)
    if template is None:
        print(f"[applescript] ação desconhecida: {do}")
        return
    # coerção: 'slide' chega como string vindo do perfil .md
    fmt_args = dict(args)
    if "slide" in fmt_args:
        try:
            fmt_args["slide"] = int(fmt_args["slide"])
        except (TypeError, ValueError):
            print(f"[applescript] slide inválido: {fmt_args['slide']!r}")
            return
    self._osascript(template.format(**fmt_args))
```

- [ ] **Step 2: Smoke test em dry-run**

Run (qualquer plataforma):
```bash
python -c "
from outputs.applescript import AppleScriptBackend
b = AppleScriptBackend()
b.execute('ppt_goto', {'slide': '5'})
"
```
Expected: nenhum traceback. No macOS, executa o osascript; fora, `[applescript/dry] ... slide number 5 ...`.

- [ ] **Step 3: Commit**

```bash
git add outputs/applescript.py
git commit -m "fix: coerce slide arg to int in applescript backend"
```

---

## Task 5: Renomear branding + argparse com `--headless`

**Files:**
- Modify: `main.py`

**Interfaces:**
- Produces:
  - `run_headless(profile_path: Path) -> None` — comportamento atual.
  - `run_gui(profile_path: Path) -> None` — stub que importa de `gui.app` (a função real chega no Task 12).
  - `main()` com `argparse`.

- [ ] **Step 1: Reescrever `main.py`**

```python
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
```

- [ ] **Step 2: Validar headless**

Run: `python main.py --headless profiles/powerpoint.md`
Expected: banner com "apc-control — perfil: PowerPoint", listener entra em modo SIMULADO, eventos imprimidos. Ctrl+C encerra.

- [ ] **Step 3: Validar que GUI ainda falha (ainda não implementada)**

Run: `python main.py`
Expected: `ModuleNotFoundError: No module named 'gui'` (esperado — chega no Task 12).

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: rename to apc-control, add --headless flag and argparse"
```

---

## Task 6: Sinais Qt e MidiBridge

**Files:**
- Create: `gui/__init__.py` (vazio)
- Create: `gui/signals.py`
- Create: `gui/midi_bridge.py`

**Interfaces:**
- Produces:
  - `FxSignals(QObject)` com `strobe: Signal(bool)`, `rate: Signal(float)`, `flash: Signal()`, `blackout: Signal()`.
  - `AiSignals(QObject)` com `token: Signal(str)`, `done: Signal()`, `error: Signal(str)`, `dismiss: Signal()`.
  - `MidiBridge(QObject)` com `event: Signal(object)`; construtor `__init__(self, bus: EventBus, parent=None)`.

- [ ] **Step 1: Criar `gui/__init__.py` vazio**

- [ ] **Step 2: Criar `gui/signals.py`**

```python
"""Portadores de sinais Qt para desacoplar backends (puros Python) da GUI.

Em modo --headless o atributo `.signals` do backend fica em None e os
backends caem no fluxo de print/dry-run.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class FxSignals(QObject):
    strobe = Signal(bool)
    rate = Signal(float)
    flash = Signal()
    blackout = Signal()


class AiSignals(QObject):
    token = Signal(str)
    done = Signal()
    error = Signal(str)
    dismiss = Signal()
```

- [ ] **Step 3: Criar `gui/midi_bridge.py`**

```python
"""Ponte EventBus → Signal Qt.

Subscreve no bus (chamado da thread do listener) e reemite via Signal.
A conexão Qt.AutoConnection garante que slots rodem na thread do receptor.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from core.bus import EventBus, MidiEvent


class MidiBridge(QObject):
    event = Signal(object)   # MidiEvent

    def __init__(self, bus: EventBus, parent=None) -> None:
        super().__init__(parent)
        bus.subscribe(self._on_event)

    def _on_event(self, ev: MidiEvent) -> None:
        self.event.emit(ev)
```

- [ ] **Step 4: Smoke import**

Run: `python -c "from gui.signals import FxSignals, AiSignals; from gui.midi_bridge import MidiBridge; print('ok')"`
Expected: `ok` (sem erros de import — confirma que PySide6 está instalado).

- [ ] **Step 5: Commit**

```bash
git add gui/__init__.py gui/signals.py gui/midi_bridge.py
git commit -m "feat: add Qt signal carriers and MIDI bus bridge"
```

---

## Task 7: Helper pyobjc para elevar overlay no macOS

**Files:**
- Create: `gui/_macos.py`

**Interfaces:**
- Produces: `raise_above_menu_bar(widget: QWidget) -> None` — no-op fora do macOS ou sem pyobjc.

- [ ] **Step 1: Criar `gui/_macos.py`**

```python
"""Eleva uma QWindow acima do menu bar e a torna visível em todos os Spaces.

Necessário para overlays cobrirem PowerPoint/Keynote em fullscreen.
Sem pyobjc instalado ou fora do macOS, vira no-op.
"""
from __future__ import annotations

import platform


def raise_above_menu_bar(widget) -> None:
    if platform.system() != "Darwin":
        return
    try:
        import objc  # type: ignore
        from AppKit import (  # type: ignore
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorStationary,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
        )
        # NSScreenSaverWindowLevel = 1000 — acima do menu bar (24) e dock
        NSScreenSaverWindowLevel = 1000
    except Exception as exc:
        print(f"[macos] pyobjc indisponível: {exc}")
        return

    try:
        view_ptr = int(widget.winId())
        view = objc.objc_object(c_void_p=view_ptr)
        win = view.window()
        if win is None:
            return
        win.setLevel_(NSScreenSaverWindowLevel)
        win.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
    except Exception as exc:
        print(f"[macos] falha ao elevar janela: {exc}")
```

- [ ] **Step 2: Commit**

```bash
git add gui/_macos.py
git commit -m "feat: macOS helper to raise overlay above menu bar"
```

---

## Task 8: FX overlay (StrobeOverlay)

**Files:**
- Modify: `fx/strobe.py` (substitui stub)
- Modify: `outputs/fx_bridge.py` (emite via `self.signals`)

**Interfaces:**
- Consumes: `FxSignals` (Task 6), `raise_above_menu_bar` (Task 7), `MAX_SAFE_HZ` de `outputs.fx_bridge`.
- Produces:
  - `StrobeOverlay(QWidget)` com slots `@Slot(bool) set_strobe`, `@Slot(float) set_rate`, `@Slot() flash`, `@Slot() toggle_blackout`.
  - `FxBackend.signals` (atributo opcional).

- [ ] **Step 1: Reescrever `fx/strobe.py`**

```python
"""Overlay de strobo/flash/blackout (PySide6).

Janela frameless, translúcida, always-on-top, fullscreen, sem foco.
QTimer alterna pintura branca/transparente a N Hz (cap MAX_SAFE_HZ).

⚠️ FOTOSSENSIBILIDADE: NÃO subir MAX_SAFE_HZ sem aviso à plateia na UI.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QWidget

from gui._macos import raise_above_menu_bar
from outputs.fx_bridge import MAX_SAFE_HZ


class StrobeOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        scr = QApplication.primaryScreen().geometry()
        self.setGeometry(scr)

        self._strobe_on = False
        self._strobe_white = False
        self._blackout = False
        self._flash_on = False
        self._hz = 1.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._end_flash)

        # eleva acima do menu bar quando a janela for materializada
        self.show()
        raise_above_menu_bar(self)
        self.hide()

    # ---- slots --------------------------------------------------------------
    @Slot(bool)
    def set_strobe(self, on: bool) -> None:
        self._strobe_on = on
        if on:
            self._start_strobe()
        else:
            self._timer.stop()
            self._strobe_white = False
        self._refresh()

    @Slot(float)
    def set_rate(self, hz: float) -> None:
        self._hz = max(0.1, min(hz, MAX_SAFE_HZ))
        if self._strobe_on:
            self._start_strobe()

    @Slot()
    def flash(self) -> None:
        self._flash_on = True
        self._refresh()
        self._flash_timer.start(100)   # 100 ms

    @Slot()
    def toggle_blackout(self) -> None:
        self._blackout = not self._blackout
        self._refresh()

    # ---- internos -----------------------------------------------------------
    def _start_strobe(self) -> None:
        # meio-período em ms: para `hz` ciclos por segundo, alterna a 2*hz toggles/s
        interval = max(10, int(1000 / (2 * self._hz)))
        self._timer.start(interval)

    def _tick(self) -> None:
        self._strobe_white = not self._strobe_white
        self.update()

    def _end_flash(self) -> None:
        self._flash_on = False
        self.update()
        self._refresh()

    def _refresh(self) -> None:
        any_active = self._strobe_on or self._blackout or self._flash_on
        if any_active and not self.isVisible():
            self.show()
            raise_above_menu_bar(self)
        elif not any_active and self.isVisible():
            self.hide()
        else:
            self.update()

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        if self._blackout:
            p.fillRect(self.rect(), QColor(0, 0, 0, 255))
            return
        if self._flash_on or (self._strobe_on and self._strobe_white):
            p.fillRect(self.rect(), QColor(255, 255, 255, 255))
            return
        # else: transparente — nada desenhado
```

- [ ] **Step 2: Modificar `outputs/fx_bridge.py` para emitir via signals**

Substituir a classe `FxBackend`:

```python
class FxBackend(Backend):
    name = "fx"

    def __init__(self) -> None:
        self.signals = None        # GUI injeta FxSignals; None = modo dry
        self._strobe_on = False
        self._blackout_on = False

    def execute(self, do: str, args: dict[str, Any], value: int = 0) -> None:
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
```

(O `__init__` antigo recebia `overlay`; agora recebe nada. `main.build_backends()` no Task 5 já chama sem argumentos — compatível.)

- [ ] **Step 3: Smoke headless (signals=None ainda dryruna)**

Run: `python main.py --headless profiles/powerpoint.md`
Expected: log mostra `[fx/dry] ...` em vez de erro.

- [ ] **Step 4: Commit**

```bash
git add fx/strobe.py outputs/fx_bridge.py
git commit -m "feat: implement strobe/flash/blackout overlay with Qt signals"
```

---

## Task 9: AI overlay (texto streaming)

**Files:**
- Create: `gui/ai_overlay.py`

**Interfaces:**
- Consumes: `AiSignals` (Task 6), `raise_above_menu_bar`.
- Produces: `AiOverlay(QWidget)` com slots `@Slot(str) append_token`, `@Slot() on_done`, `@Slot(str) on_error`, `@Slot() dismiss`.

- [ ] **Step 1: Criar `gui/ai_overlay.py`**

```python
"""Overlay de texto da IA: aparece sobre qualquer app, recebe tokens em streaming.

Auto-dismiss 12s após o stream encerrar; reset a cada novo token (mantém visível
durante a geração). Esc fecha; clicar também fecha (não tem
WA_TransparentForMouseEvents).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from gui._macos import raise_above_menu_bar

AUTO_DISMISS_MS = 12_000


class AiOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        scr = QApplication.primaryScreen().geometry()
        self.setGeometry(scr)

        self._label = QLabel("", self)
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet(
            "color: white; background: rgba(0, 0, 0, 200);"
            "padding: 32px; border-radius: 16px;"
        )
        font = QFont()
        font.setPointSize(36)
        font.setBold(True)
        self._label.setFont(font)

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(self._label)
        layout.addStretch()
        layout.setContentsMargins(120, 80, 120, 120)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    @Slot(str)
    def append_token(self, t: str) -> None:
        if not self.isVisible():
            self._label.setText("")
            self.show()
            raise_above_menu_bar(self)
        self._label.setText(self._label.text() + t)
        self._timer.stop()   # cancela auto-dismiss enquanto recebe

    @Slot()
    def on_done(self) -> None:
        self._timer.start(AUTO_DISMISS_MS)

    @Slot(str)
    def on_error(self, msg: str) -> None:
        self._label.setText(f"[erro IA] {msg}")
        if not self.isVisible():
            self.show()
            raise_above_menu_bar(self)
        self._timer.start(8000)

    @Slot()
    def dismiss(self) -> None:
        self._timer.stop()
        self.hide()

    def mousePressEvent(self, _ev) -> None:
        self.dismiss()

    def keyPressEvent(self, ev) -> None:
        if ev.key() == Qt.Key_Escape:
            self.dismiss()
```

- [ ] **Step 2: Commit**

```bash
git add gui/ai_overlay.py
git commit -m "feat: AI streaming text overlay (auto-dismiss, esc/click to close)"
```

---

## Task 10: AI backend com Anthropic streaming

**Files:**
- Modify: `outputs/ai.py` (reescrita)

**Interfaces:**
- Consumes: `AiSignals` (Task 6).
- Produces: `AiBackend.signals` (atributo opcional). Ação `prompt` dispara thread daemon que streama tokens. Ação `dismiss` emite `signals.dismiss`.

- [ ] **Step 1: Reescrever `outputs/ai.py`**

```python
"""Backend de IA: chama a API Anthropic e streama tokens para o overlay.

Modelo padrão: claude-haiku-4-5-20251001 (rápido, bom para resposta ao vivo).
Sem ANTHROPIC_API_KEY ou sem SDK instalado, cai em modo dry — emite
tokens fake para a GUI ainda funcionar.

Ações:
  prompt   -> args: { prompt: "texto" }     dispara stream em thread daemon
  dismiss  -> esconde o overlay
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any

from outputs.base import Backend

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _try_import_anthropic():
    try:
        import anthropic  # type: ignore
        return anthropic
    except Exception:
        return None


class AiBackend(Backend):
    name = "ai"

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.signals = None         # GUI injeta AiSignals; None = print
        self.model = model
        self._anthropic = _try_import_anthropic()
        self._client = None
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if self._anthropic and api_key:
            try:
                self._client = self._anthropic.Anthropic(api_key=api_key)
            except Exception as exc:
                print(f"[ai] cliente Anthropic falhou: {exc}")

    def execute(self, do: str, args: dict[str, Any], value: int = 0) -> None:
        if do == "prompt":
            prompt = args.get("prompt", "").strip()
            if not prompt:
                print("[ai] prompt vazio, ignorado")
                return
            threading.Thread(target=self._stream, args=(prompt,), daemon=True).start()
        elif do == "dismiss":
            if self.signals:
                self.signals.dismiss.emit()
            else:
                print("[ai/dry] dismiss")
        else:
            print(f"[ai] ação desconhecida: {do}")

    def _stream(self, prompt: str) -> None:
        if self._client is None:
            self._stream_dry(prompt)
            return
        try:
            with self._client.messages.stream(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for text in stream.text_stream:
                    self._emit_token(text)
            self._emit_done()
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            if self.signals:
                self.signals.error.emit(msg)
            else:
                print(f"[ai] erro: {msg}")

    def _stream_dry(self, prompt: str) -> None:
        fake = f"[ai/dry sem API key] resposta simulada para: {prompt}"
        for chunk in fake.split(" "):
            self._emit_token(chunk + " ")
            time.sleep(0.04)
        self._emit_done()

    def _emit_token(self, text: str) -> None:
        if self.signals:
            self.signals.token.emit(text)
        else:
            print(text, end="", flush=True)

    def _emit_done(self) -> None:
        if self.signals:
            self.signals.done.emit()
        else:
            print()   # quebra de linha
```

- [ ] **Step 2: Smoke headless (sem API key, deve printar)**

Run:
```bash
ANTHROPIC_API_KEY= python -c "
from outputs.ai import AiBackend
import time
b = AiBackend()
b.execute('prompt', {'prompt': 'oi'})
time.sleep(2)
"
```
Expected: imprime `[ai/dry sem API key] resposta simulada para: oi` palavra por palavra, depois quebra de linha.

- [ ] **Step 3: Commit**

```bash
git add outputs/ai.py
git commit -m "feat: AI backend with Anthropic streaming, dry-run fallback"
```

---

## Task 11: Widget visual da APC (grid 8x8 + faders)

**Files:**
- Create: `gui/apc_grid.py`

**Interfaces:**
- Produces:
  - `APCGrid(QWidget)` com `clicked = Signal(str, int)` emitido como `("note", n)` ou `("cc", n)`.
  - método `highlight(input_type: str, number: int)` que pisca o botão correspondente por 200 ms (usado pelo painel ao vivo para feedback visual).

- [ ] **Step 1: Criar `gui/apc_grid.py`**

```python
"""Widget 8x8 da APC mini + 9 faders. Cliques emitem (input_type, number).

Usado: (a) no editor para escolher qual entrada bindar; (b) no painel ao vivo
para piscar conforme eventos MIDI entram.
"""
from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QPushButton, QSlider, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

GRID_COLS = 8
GRID_ROWS = 8
FADER_CCS = list(range(48, 57))   # 8 faders + master (48..56)


class APCGrid(QWidget):
    clicked = Signal(str, int)   # ("note"|"cc", number)

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)

        # grid 8x8
        grid_box = QWidget()
        grid = QGridLayout(grid_box)
        grid.setSpacing(2)
        self._buttons: dict[int, QPushButton] = {}
        for n in range(GRID_COLS * GRID_ROWS):
            row, col = divmod(n, GRID_COLS)
            btn = QPushButton(str(n))
            btn.setFixedSize(42, 42)
            btn.setStyleSheet(self._style_for(False))
            btn.clicked.connect(lambda _checked=False, num=n: self.clicked.emit("note", num))
            grid.addWidget(btn, GRID_ROWS - 1 - row, col)   # linha 0 embaixo
            self._buttons[n] = btn
        outer.addWidget(grid_box)

        # faders
        faders_box = QWidget()
        fbox = QHBoxLayout(faders_box)
        self._faders: dict[int, QSlider] = {}
        for cc in FADER_CCS:
            col = QVBoxLayout()
            slider = QSlider(Qt.Vertical)
            slider.setRange(0, 127)
            slider.setFixedHeight(120)
            slider.sliderPressed.connect(lambda c=cc: self.clicked.emit("cc", c))
            col.addWidget(slider, alignment=Qt.AlignHCenter)
            col.addWidget(QLabel := __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel(f"CC{cc}"),
                          alignment=Qt.AlignHCenter)
            fbox.addLayout(col)
            self._faders[cc] = slider
        outer.addWidget(faders_box)

    def _style_for(self, lit: bool) -> str:
        bg = "#3aa757" if lit else "#222"
        return f"background:{bg}; color:white; font-size:10pt; border-radius:6px;"

    def highlight(self, input_type: str, number: int) -> None:
        if input_type == "note" and number in self._buttons:
            btn = self._buttons[number]
            btn.setStyleSheet(self._style_for(True))
            QTimer.singleShot(200, lambda: btn.setStyleSheet(self._style_for(False)))
        elif input_type == "cc" and number in self._faders:
            # nada para faders por ora; só o widget já reflete movimento
            pass
```

- [ ] **Step 2: Smoke** (import só)

Run: `python -c "from PySide6.QtWidgets import QApplication; import sys; QApplication(sys.argv); from gui.apc_grid import APCGrid; w = APCGrid(); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add gui/apc_grid.py
git commit -m "feat: APCGrid widget (8x8 grid + 9 faders) with click signal"
```

---

## Task 12: Aba editor de bindings

**Files:**
- Create: `gui/binding_editor.py`

**Interfaces:**
- Consumes: `APCGrid` (Task 11), `Profile`/`Binding`/`save_profile` (Task 2), `MidiBridge.event` (Task 6).
- Produces:
  - `BindingEditor(QWidget)` com construtor `(profile: Profile, profile_path: Path, bridge: MidiBridge)`.
  - método `set_profile(profile: Profile, path: Path)` para troca de perfil ao vivo.
  - sinal `profile_changed = Signal()` quando o usuário salva.

- [ ] **Step 1: Criar `gui/binding_editor.py`**

```python
"""Aba editor de bindings.

Tabela à esquerda, APC visual + formulário à direita. Botão Learn captura
o próximo evento MIDI do bridge.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.bus import MidiEvent
from core.profiles import Binding, Profile, save_profile
from gui.apc_grid import APCGrid
from gui.midi_bridge import MidiBridge

BACKENDS = ["keyboard", "applescript", "fx", "ai"]
ACTIONS = {
    "keyboard": ["key", "combo", "text"],
    "applescript": ["ppt_next", "ppt_prev", "ppt_goto", "keynote_next", "keynote_prev", "run"],
    "fx": ["strobe_toggle", "strobe_rate", "flash", "blackout_toggle"],
    "ai": ["prompt", "dismiss"],
}


class BindingEditor(QWidget):
    profile_changed = Signal()

    def __init__(self, profile: Profile, profile_path: Path, bridge: MidiBridge) -> None:
        super().__init__()
        self.profile = profile
        self.path = profile_path
        self._learning = False
        bridge.event.connect(self._on_midi)

        splitter = QSplitter(Qt.Horizontal)

        # --- esquerda: tabela ---
        left = QWidget(); left_l = QVBoxLayout(left)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Input", "N", "Backend", "Action", "Args"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._on_select)
        left_l.addWidget(self.table)
        btn_del = QPushButton("Remover selecionado")
        btn_del.clicked.connect(self._delete_selected)
        left_l.addWidget(btn_del)
        splitter.addWidget(left)

        # --- direita: APC + form ---
        right = QWidget(); right_l = QVBoxLayout(right)
        self.grid = APCGrid()
        self.grid.clicked.connect(self._on_grid_click)
        right_l.addWidget(self.grid)

        form = QHBoxLayout()
        self.input_type = QComboBox(); self.input_type.addItems(["note", "cc"])
        self.number = QSpinBox(); self.number.setRange(0, 127)
        self.backend = QComboBox(); self.backend.addItems(BACKENDS)
        self.backend.currentTextChanged.connect(self._on_backend_change)
        self.action = QComboBox(); self.action.addItems(ACTIONS["keyboard"])
        self.args = QLineEdit(); self.args.setPlaceholderText("k=v, k2=v2")
        form.addWidget(QLabel("tipo:")); form.addWidget(self.input_type)
        form.addWidget(QLabel("n:")); form.addWidget(self.number)
        form.addWidget(QLabel("backend:")); form.addWidget(self.backend)
        form.addWidget(QLabel("ação:")); form.addWidget(self.action)
        right_l.addLayout(form)
        right_l.addWidget(QLabel("args:"))
        right_l.addWidget(self.args)

        btn_row = QHBoxLayout()
        self.learn = QCheckBox("Learn (capturar próximo MIDI)")
        btn_add = QPushButton("Adicionar / Atualizar")
        btn_add.clicked.connect(self._add_or_update)
        btn_save = QPushButton("Salvar perfil (.md)")
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(self.learn); btn_row.addStretch()
        btn_row.addWidget(btn_add); btn_row.addWidget(btn_save)
        right_l.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1); splitter.setStretchFactor(1, 2)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        self._refill_table()

    # ---- pública ------------------------------------------------------------
    def set_profile(self, profile: Profile, path: Path) -> None:
        self.profile = profile
        self.path = path
        self._refill_table()

    # ---- internos -----------------------------------------------------------
    def _refill_table(self) -> None:
        self.table.setRowCount(len(self.profile.bindings))
        for i, b in enumerate(self.profile.bindings):
            args_str = ", ".join(f"{k}={v}" for k, v in b.args.items())
            for col, val in enumerate([b.input_type, str(b.number), b.backend, b.do, args_str]):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, col, item)

    def _on_select(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        b = self.profile.bindings[rows[0].row()]
        self.input_type.setCurrentText(b.input_type)
        self.number.setValue(b.number)
        self.backend.setCurrentText(b.backend)
        self._refresh_actions(b.backend, b.do)
        self.args.setText(", ".join(f"{k}={v}" for k, v in b.args.items()))

    def _on_backend_change(self, name: str) -> None:
        self._refresh_actions(name, None)

    def _refresh_actions(self, backend: str, current: str | None) -> None:
        self.action.clear()
        self.action.addItems(ACTIONS.get(backend, []))
        if current:
            self.action.setCurrentText(current)

    def _on_grid_click(self, input_type: str, number: int) -> None:
        self.input_type.setCurrentText(input_type)
        self.number.setValue(number)

    @Slot(object)
    def _on_midi(self, ev: MidiEvent) -> None:
        if not self.learn.isChecked():
            return
        it = "cc" if ev.kind == "control_change" else "note"
        self.input_type.setCurrentText(it)
        self.number.setValue(ev.number)
        self.learn.setChecked(False)

    def _parse_args(self, s: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for pair in s.split(","):
            pair = pair.strip()
            if "=" not in pair:
                continue
            k, v = pair.split("=", 1)
            out[k.strip()] = v.strip()
        return out

    def _add_or_update(self) -> None:
        it = self.input_type.currentText()
        n = self.number.value()
        new = Binding(it, n, self.backend.currentText(),
                      self.action.currentText(), self._parse_args(self.args.text()))
        # se já existe binding com (it, n), substitui
        for i, b in enumerate(self.profile.bindings):
            if b.input_type == it and b.number == n:
                self.profile.bindings[i] = new
                self._refill_table()
                return
        self.profile.bindings.append(new)
        self._refill_table()

    def _delete_selected(self) -> None:
        rows = sorted({r.row() for r in self.table.selectionModel().selectedRows()},
                      reverse=True)
        for r in rows:
            del self.profile.bindings[r]
        self._refill_table()

    def _save(self) -> None:
        try:
            save_profile(self.profile, self.path)
            self.profile_changed.emit()
            QMessageBox.information(self, "Salvo", f"Perfil salvo em {self.path}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
```

- [ ] **Step 2: Commit**

```bash
git add gui/binding_editor.py
git commit -m "feat: binding editor tab (table + APC grid + learn mode)"
```

---

## Task 13: Aba painel ao vivo

**Files:**
- Create: `gui/live_panel.py`

**Interfaces:**
- Consumes: `MidiBridge`, `APCGrid`, `MidiListener` (para `list_ports`), backends, `MAX_SAFE_HZ`.
- Produces: `LivePanel(QWidget)` com construtor `(bridge, listener, fx_backend, ai_backend, fx_signals, ai_signals)`.

- [ ] **Step 1: Criar `gui/live_panel.py`**

```python
"""Painel ao vivo: status MIDI, log de eventos, gatilhos manuais de FX/IA.

O aviso de fotossensibilidade aparece UMA vez por sessão antes do primeiro
strobo. Slider de rate é cap MAX_SAFE_HZ (3.0).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton,
    QSlider, QVBoxLayout, QWidget,
)

from core.bus import MidiEvent
from gui.apc_grid import APCGrid
from gui.midi_bridge import MidiBridge
from outputs.fx_bridge import MAX_SAFE_HZ

LOG_LIMIT = 200


class LivePanel(QWidget):
    def __init__(self, bridge: MidiBridge, listener, fx_signals, ai_backend) -> None:
        super().__init__()
        self.fx_signals = fx_signals
        self.ai_backend = ai_backend
        self._warned = False
        self._strobe_on = False

        layout = QVBoxLayout(self)

        # --- status MIDI ---
        status = QHBoxLayout()
        ports = listener.list_ports()
        connected = bool(listener._find_port()) if listener._mido else False
        dot = "🟢" if connected else "🔴"
        text = f"{dot} MIDI: {ports[0] if ports else '(nenhuma porta)'} {'(simulando)' if not connected else ''}"
        status.addWidget(QLabel(text))
        status.addStretch()
        layout.addLayout(status)

        # --- grid visual (espelho dos eventos) ---
        self.grid = APCGrid()
        layout.addWidget(self.grid)

        # --- log ---
        self.log = QListWidget()
        bridge.event.connect(self._on_event)
        layout.addWidget(QLabel("Log de eventos:"))
        layout.addWidget(self.log, stretch=1)

        # --- gatilhos manuais FX ---
        fx_row = QHBoxLayout()
        btn_flash = QPushButton("Flash"); btn_flash.clicked.connect(self._flash)
        self.btn_strobe = QPushButton("Strobo: OFF")
        self.btn_strobe.setCheckable(True)
        self.btn_strobe.toggled.connect(self._toggle_strobe)
        btn_blackout = QPushButton("Blackout"); btn_blackout.clicked.connect(self._blackout)
        self.rate = QSlider(Qt.Horizontal)
        self.rate.setRange(1, int(MAX_SAFE_HZ * 10))   # 0.1..3.0 em décimos
        self.rate.setValue(10)
        self.rate.valueChanged.connect(self._rate_changed)
        fx_row.addWidget(btn_flash)
        fx_row.addWidget(self.btn_strobe)
        fx_row.addWidget(btn_blackout)
        fx_row.addWidget(QLabel("Rate Hz:"))
        fx_row.addWidget(self.rate)
        layout.addLayout(fx_row)

        # --- gatilhos manuais IA ---
        ai_row = QHBoxLayout()
        self.prompt = QLineEdit()
        self.prompt.setPlaceholderText("Digite um prompt e Enter (overlay aparece sobre tudo)")
        self.prompt.returnPressed.connect(self._send_prompt)
        btn_send = QPushButton("Enviar à IA"); btn_send.clicked.connect(self._send_prompt)
        ai_row.addWidget(QLabel("IA:")); ai_row.addWidget(self.prompt, stretch=1); ai_row.addWidget(btn_send)
        layout.addLayout(ai_row)

    # ---- handlers ----------------------------------------------------------
    @Slot(object)
    def _on_event(self, ev: MidiEvent) -> None:
        line = f"{ev.kind:<14} number={ev.number:<3} value={ev.value}"
        self.log.addItem(line)
        while self.log.count() > LOG_LIMIT:
            self.log.takeItem(0)
        self.log.scrollToBottom()
        it = "cc" if ev.kind == "control_change" else "note"
        self.grid.highlight(it, ev.number)

    def _warn_once(self) -> bool:
        if self._warned:
            return True
        ans = QMessageBox.warning(
            self, "AVISO FOTOSSENSIBILIDADE",
            "Strobo pode desencadear convulsões em pessoas fotossensíveis.\n"
            f"Frequência limitada a {MAX_SAFE_HZ} Hz.\n\nConfirma habilitar?",
            QMessageBox.Ok | QMessageBox.Cancel,
        )
        if ans == QMessageBox.Ok:
            self._warned = True
            return True
        return False

    def _flash(self) -> None:
        self.fx_signals.flash.emit()

    def _blackout(self) -> None:
        self.fx_signals.blackout.emit()

    def _toggle_strobe(self, on: bool) -> None:
        if on and not self._warn_once():
            self.btn_strobe.setChecked(False)
            return
        self._strobe_on = on
        self.btn_strobe.setText(f"Strobo: {'ON' if on else 'OFF'}")
        self.fx_signals.strobe.emit(on)
        if on:
            self.fx_signals.rate.emit(self.rate.value() / 10.0)

    def _rate_changed(self, v: int) -> None:
        hz = v / 10.0
        self.fx_signals.rate.emit(hz)

    def _send_prompt(self) -> None:
        text = self.prompt.text().strip()
        if not text:
            return
        self.ai_backend.execute("prompt", {"prompt": text})
```

- [ ] **Step 2: Commit**

```bash
git add gui/live_panel.py
git commit -m "feat: live panel tab (MIDI log, manual FX/AI triggers, port status)"
```

---

## Task 14: MainWindow + entry `run_gui`

**Files:**
- Create: `gui/main_window.py`
- Create: `gui/app.py`

**Interfaces:**
- Consumes: tudo do `gui/*`, backends, listener.
- Produces:
  - `MainWindow(QMainWindow)` com tabs Live/Editor + combo para trocar de perfil.
  - `run_gui(profile_path: Path) -> None` — chamado por `main.py`.

- [ ] **Step 1: Criar `gui/main_window.py`**

```python
"""Janela principal: combo de perfis + tabs Live / Editor."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget,
)

from core.mapper import Mapper
from core.profiles import load_profile
from gui.binding_editor import BindingEditor
from gui.live_panel import LivePanel
from gui.midi_bridge import MidiBridge

PROFILES_DIR = Path("profiles")


class MainWindow(QMainWindow):
    def __init__(self, bridge: MidiBridge, mapper: Mapper, listener,
                 fx_signals, ai_backend, profile_path: Path) -> None:
        super().__init__()
        self.setWindowTitle("apc-control")
        self.resize(1100, 720)
        self.mapper = mapper
        self.path = profile_path

        central = QWidget(); root = QVBoxLayout(central)

        # combo de perfis
        head = QHBoxLayout()
        head.addWidget(QLabel("Perfil:"))
        self.combo = QComboBox()
        for p in sorted(PROFILES_DIR.glob("*.md")):
            self.combo.addItem(p.name, str(p))
        idx = self.combo.findData(str(profile_path))
        if idx >= 0:
            self.combo.setCurrentIndex(idx)
        self.combo.currentIndexChanged.connect(self._switch_profile)
        head.addWidget(self.combo); head.addStretch()
        root.addLayout(head)

        # tabs
        tabs = QTabWidget()
        self.live = LivePanel(bridge, listener, fx_signals, ai_backend)
        self.editor = BindingEditor(mapper.profile, profile_path, bridge)
        self.editor.profile_changed.connect(self._reload_current)
        tabs.addTab(self.live, "Ao vivo")
        tabs.addTab(self.editor, "Editor")
        root.addWidget(tabs)

        self.setCentralWidget(central)

    def _switch_profile(self, idx: int) -> None:
        path = Path(self.combo.itemData(idx))
        profile = load_profile(path)
        self.mapper.set_profile(profile)
        self.path = path
        self.editor.set_profile(profile, path)

    def _reload_current(self) -> None:
        profile = load_profile(self.path)
        self.mapper.set_profile(profile)
```

- [ ] **Step 2: Criar `gui/app.py`**

```python
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
```

- [ ] **Step 3: Smoke launch**

Run: `python main.py`
Expected: janela "apc-control" abre. Sem APC conectada: ponto 🔴, listener entra em modo SIMULADO, log enche com 5 eventos. Clique em "Flash" → tela inteira pisca branca por 100 ms. Aba Editor: clique no botão 0 da grid, escolha backend=keyboard, ação=key, args=`key=right`, "Adicionar / Atualizar" — entrada nova na tabela. Salvar grava `profiles/powerpoint.md`.

- [ ] **Step 4: Commit**

```bash
git add gui/main_window.py gui/app.py
git commit -m "feat: main window + GUI entry wiring overlays/backends/listener"
```

---

## Task 15: Atualizar README.md e CLAUDE.md

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Atualizar `README.md`**

- Trocar todas as ocorrências "apcdeck" → "apc-control".
- Atualizar diagrama: incluir GUI/overlays.
- Substituir a seção de perfis YAML por exemplo Markdown.
- Adicionar seção "GUI vs --headless".
- Adicionar bloco de aviso fotossensibilidade.

- [ ] **Step 2: Atualizar `CLAUDE.md`**

- Trocar "apcdeck" → "apc-control".
- Adicionar `gui/` ao mapa de arquitetura.
- Adicionar nota sobre `args` sempre `dict[str, str]` no parser MD.
- Adicionar `python main.py` (GUI default) e `--headless` aos comandos.
- Mencionar que `MAX_SAFE_HZ` agora tem fonte única em `outputs/fx_bridge.py`.

- [ ] **Step 3: Verificação final por grep**

Run: `grep -rIn "apcdeck" --exclude-dir=.venv --exclude-dir=.git . || echo "nenhum apcdeck restante"`
Expected: `nenhum apcdeck restante`.

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: rebrand to apc-control, document GUI + Markdown profiles"
```

---

## Verification (end-to-end)

Executar manualmente após Task 15 (idealmente via `superpowers:verification-before-completion`):

1. **Testes do parser**: `pytest tests/test_profiles.py -v` → 7 PASS.
2. **Headless**: `python main.py --headless profiles/powerpoint.md` → banner + simulação de 5 eventos + `[fx/dry]` / `[ai/dry]` saindo conforme bindings. Ctrl+C limpo.
3. **GUI sem APC**: `python main.py` → janela abre, indicador 🔴, log enche com os 5 eventos simulados, botão Flash pisca a tela, slider Strobe + checkbox Strobo on (após aviso) faz tela piscar a ~1–3 Hz.
4. **GUI com APC**: conectar APC mini → indicador 🟢, apertar pads acende botões na grid visual, ações disparam (teste com profile padrão: nota 0 envia tecla →).
5. **Overlay sobre fullscreen**: abrir Keynote/PowerPoint em apresentação, disparar Flash pelo botão da GUI ou pela APC → flash visível sobre o app em fullscreen.
6. **IA streaming**: definir `ANTHROPIC_API_KEY`, digitar prompt no painel ao vivo → overlay aparece, texto stream-aparece sobre qualquer app, auto-dismiss em 12 s; Esc fecha imediato.
7. **IA sem chave**: rodar sem `ANTHROPIC_API_KEY` → overlay aparece com texto `[ai/dry sem API key] ...` (confirma que UX não quebra).
8. **Editor round-trip**: Editor → marcar Learn → apertar pad → form preenche → ajustar action/args → Adicionar → Salvar → abrir `profiles/powerpoint.md` num editor de texto → nova linha presente. Re-abrir o app, perfil carregado já tem o binding novo.
9. **Photo cap**: tentar via Python `from fx.strobe import StrobeOverlay; o = StrobeOverlay(); o.set_rate(20.0); assert o._hz == 3.0` → passa.

---

## Self-Review (recapagem)

**Spec coverage:**
- Renomeio apcdeck → apc-control ✓ (Tasks 5, 15)
- YAML → Markdown ✓ (Tasks 2, 3, 4)
- GUI editor + ao vivo ✓ (Tasks 11, 12, 13, 14)
- Strobo independente do software ✓ (Task 8)
- IA independente do software ✓ (Tasks 9, 10)
- "superpowers" interpretado como suíte de skills carregada ✓ (este plano usa writing-plans; execução usará subagent-driven-development ou executing-plans)

**Placeholder scan:** nenhum "TBD/TODO/implement later/etc." nos passos. Todas as ações com código têm bloco completo.

**Type consistency:**
- `Binding.args: dict[str, str]` em todo o plano (parser, save, editor, backends consumindo via cast).
- `FxSignals` e `AiSignals` com assinaturas idênticas em `signals.py`, conexões no `app.py`, slots em `StrobeOverlay`/`AiOverlay`.
- `MidiBridge.event: Signal(object)` (carrega `MidiEvent`) — conectado em `LivePanel` e `BindingEditor` com slot `@Slot(object)`.
- `MAX_SAFE_HZ` mora em `outputs/fx_bridge.py`; `fx/strobe.py` importa de lá.
