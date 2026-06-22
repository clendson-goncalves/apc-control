# LED idle aceso + muda cor ao clicar — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pads de nota mapeados acendem VERDE (idle) na APC mini; ao clicar mudam de cor e voltam ao idle em vez de apagar.

**Architecture:** A nova semântica de "voltar pro idle" vive inteira no `LedController` (`midi/output.py`), que ganha um mapa `note → cor de descanso`. Os entry points (`main.py`, `gui/app.py`) acendem os pads mapeados no startup via um helper compartilhado em `core/mapper.py`. O `Mapper` e a inferência `led_behavior()` não mudam.

**Tech Stack:** Python 3.10+, mido (MIDI out, com fallback DRY), pytest, PySide6 (GUI).

## Global Constraints

- Python 3.10+ (sintaxe `X | None`, `list[...]`). Comentários/docstrings em português (convenção do projeto).
- Cores por velocity (constantes já existentes em `midi/output.py`): `OFF=0`, `GREEN=1`, `RED=3`, `YELLOW_BLINK=6`. Não alterar.
- Idle (pad mapeado disponível) = `GREEN`. Momentâneo ao clicar = `RED` ~150ms → volta idle. Toggle ON = `RED` fixo; OFF → volta idle. IA `prompt` = `YELLOW_BLINK` → volta idle ao terminar.
- Pad sem entrada idle registrada restaura para `OFF` (comportamento antigo).
- Faders (input `cc`) não têm LED — só bindings de nota acendem.
- `MAX_SAFE_HZ = 3.0` em `outputs/fx_bridge.py` é intocável.
- Testes rodam com `.venv/bin/python -m pytest` (o `python3` do sistema não tem pytest).

---

### Task 1: LedController — idle + restaurar cor em vez de apagar

**Files:**
- Modify: `midi/output.py` (classe `LedController`)
- Test: `tests/test_led.py`

**Interfaces:**
- Consumes: nada novo (usa `_send`, `_sink`, constantes `OFF/GREEN/RED/YELLOW_BLINK` já existentes).
- Produces:
  - `LedController.set_idle(self, notes: list[int], color: int = GREEN) -> None` — acende cada nota com `color` e registra em `self._idle[note] = color`.
  - `LedController._idle: dict[int, int]` — mapa `note → cor de descanso` (vazio por padrão).
  - `LedController._restore(self, note: int) -> None` — manda `self._idle.get(note, OFF)`.
  - Semântica alterada: `flash` pisca `RED` e volta ao idle; `set(note, on=False)` volta ao idle; `clear(note)` volta ao idle; `close()` apaga todos os pads idle.

O estado atual de `midi/output.py` (`LedController`): `__init__` cria `self._lock`, `self._timers`, `self._flash_ms`, `self._port`, `self._dry`, `self._sink`. `flash` manda `GREEN` e agenda `_flash_off` que manda `OFF`. `set` manda `RED`/`OFF`. `clear` manda `OFF`. `close` cancela timers e fecha a porta.

- [ ] **Step 1: Escrever os testes que falham (ajustar existentes + novos)**

Em `tests/test_led.py`, **substituir** a função `test_flash_sends_green_then_off` por `test_flash_sends_red_then_restores_off`:

```python
def test_flash_sends_red_then_restores_off():
    sent, sink = _recorder()
    led = LedController(flash_ms=10, sink=sink)
    led.flash(5)
    assert sent[0] == (5, RED)          # pisca vermelho
    time.sleep(0.05)
    assert sent[-1] == (5, OFF)         # sem idle registrado -> volta OFF
    led.close()
```

E **adicionar** estes testes (no mesmo arquivo, após o bloco dos testes de `LedController`):

```python
def test_set_idle_lights_and_registers():
    sent, sink = _recorder()
    led = LedController(sink=sink)
    led.set_idle([0, 8, 16])
    assert sent == [(0, GREEN), (8, GREEN), (16, GREEN)]
    assert led._idle == {0: GREEN, 8: GREEN, 16: GREEN}
    led.close()


def test_flash_idle_pad_returns_to_green():
    sent, sink = _recorder()
    led = LedController(flash_ms=10, sink=sink)
    led.set_idle([5])
    led.flash(5)
    assert (5, RED) in sent             # piscou vermelho
    time.sleep(0.05)
    assert sent[-1] == (5, GREEN)       # voltou ao idle verde
    led.close()


def test_flash_non_idle_pad_returns_to_off():
    sent, sink = _recorder()
    led = LedController(flash_ms=10, sink=sink)
    led.flash(9)
    time.sleep(0.05)
    assert sent[-1] == (9, OFF)
    led.close()


def test_toggle_off_idle_pad_returns_to_green():
    sent, sink = _recorder()
    led = LedController(sink=sink)
    led.set_idle([7])
    sent.clear()
    led.set(7, on=True)
    led.set(7, on=False)
    assert sent == [(7, RED), (7, GREEN)]   # ON vermelho, OFF volta idle
    led.close()


def test_clear_idle_pad_returns_to_green():
    sent, sink = _recorder()
    led = LedController(sink=sink)
    led.set_idle([9])
    sent.clear()
    led.clear(9)
    assert sent == [(9, GREEN)]
    led.close()


def test_close_turns_off_idle_pads():
    sent, sink = _recorder()
    led = LedController(sink=sink)
    led.set_idle([0, 1])
    sent.clear()
    led.close()
    assert (0, OFF) in sent and (1, OFF) in sent
```

Os testes existentes que continuam válidos sem mudança: `test_set_on_is_red_off_is_off` (sem idle, OFF restaura OFF), `test_clear_sends_off` (sem idle, clear → OFF), `test_blink_sends_yellow_blink`, `test_flash_timer_is_pruned_after_firing`, `test_dry_mode_does_not_raise`. Não mexer neles.

- [ ] **Step 2: Rodar os testes e verificar que falham**

Run: `.venv/bin/python -m pytest tests/test_led.py -v`
Expected: FAIL — `AttributeError: 'LedController' object has no attribute 'set_idle'` (e `_idle`), e `test_flash_sends_red_then_restores_off` falha porque `flash` ainda manda `GREEN`.

- [ ] **Step 3: Implementar as mudanças no `LedController`**

Em `midi/output.py`, no `__init__`, adicionar a linha do mapa idle logo após `self._timers`:

```python
        self._lock = threading.Lock()
        self._timers: list[threading.Timer] = []
        self._idle: dict[int, int] = {}        # note -> cor de descanso
        self._flash_ms = flash_ms
```

Substituir o método `flash` (mantém o agendamento de timer; muda a cor para `RED`):

```python
    def flash(self, note: int) -> None:
        self._send(note, RED)
        t = threading.Timer(self._flash_ms / 1000, self._flash_off, args=(note,))
        t.daemon = True
        with self._lock:
            self._timers.append(t)
        t.start()
```

Substituir o método `_flash_off` para restaurar o idle em vez de mandar `OFF`:

```python
    def _flash_off(self, note: int) -> None:
        """Callback do timer: volta o LED ao idle e remove o próprio timer da lista."""
        self._restore(note)
        # Timer é subclasse de Thread; rodando no próprio thread, current_thread() é ele.
        cur = threading.current_thread()
        with self._lock:
            try:
                self._timers.remove(cur)
            except ValueError:
                pass
```

Substituir `set` e `clear`:

```python
    def set(self, note: int, on: bool) -> None:
        if on:
            self._send(note, RED)
        else:
            self._restore(note)

    def blink(self, note: int) -> None:
        self._send(note, YELLOW_BLINK)

    def clear(self, note: int) -> None:
        self._restore(note)
```

Adicionar os métodos novos `set_idle` e `_restore` (por exemplo, logo antes de `flash`):

```python
    def set_idle(self, notes: list[int], color: int = GREEN) -> None:
        """Acende os pads mapeados (estado idle) e registra a cor de descanso."""
        for note in notes:
            self._idle[note] = color
            self._send(note, color)

    def _restore(self, note: int) -> None:
        """Volta o LED para a cor de descanso (idle) ou OFF se não houver."""
        self._send(note, self._idle.get(note, OFF))
```

Substituir `close` para apagar os pads idle antes de fechar a porta:

```python
    def close(self) -> None:
        # Snapshot sob o lock; cancela fora dele (evita segurar o lock no cancel
        # e a corrida com flash() mexendo na lista).
        with self._lock:
            timers = list(self._timers)
            self._timers.clear()
            idle_notes = list(self._idle)
        for t in timers:
            t.cancel()
        for note in idle_notes:
            self._send(note, OFF)      # não deixa a controladora acesa após sair
        if self._port is not None:
            try:
                self._port.close()
            except Exception:
                pass
```

- [ ] **Step 4: Rodar os testes e verificar que passam**

Run: `.venv/bin/python -m pytest tests/test_led.py -v`
Expected: PASS — todos os testes do arquivo (existentes + novos) passam.

- [ ] **Step 5: Commit**

```bash
git add midi/output.py tests/test_led.py
git commit -m "feat: LedController acende idle e restaura cor em vez de apagar"
```

---

### Task 2: Helper `idle_notes` + acender pads no startup

**Files:**
- Modify: `core/mapper.py` (adicionar função `idle_notes`)
- Modify: `main.py` (`run_headless`)
- Modify: `gui/app.py` (`run_gui`)
- Test: `tests/test_led.py`

**Interfaces:**
- Consumes: `LedController.set_idle` (Task 1); `Profile.bindings` / `Binding.input_type` / `Binding.number` (já existentes em `core/profiles.py`).
- Produces: `core.mapper.idle_notes(profile) -> list[int]` — números das notas (pads) com binding, na ordem do perfil; exclui `cc`.

O estado atual: `core/mapper.py` define `led_behavior(...)` e a classe `Mapper`. `main.run_headless` cria `led = LedController()` e `mapper = Mapper(profile, backends, led=led)` (linhas ~47–49). `gui/app.run_gui` cria `led = LedController()` (linha ~42) e `mapper = Mapper(profile, backends, led=led)` (linha ~48). Ambos importam `from core.mapper import Mapper`.

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_led.py`, adicionar (o arquivo já importa `Binding, Profile` de `core.profiles`; ajustar o import de `core.mapper` para incluir `idle_notes`):

```python
def test_idle_notes_returns_only_note_bindings():
    profile = Profile("T", "", [
        Binding("note", 0, "keyboard", "key", {}),
        Binding("cc", 48, "fx", "strobe_rate", {}),
        Binding("note", 8, "fx", "flash", {}),
    ])
    assert idle_notes(profile) == [0, 8]    # ignora cc, mantém ordem
```

O import no topo do arquivo passa de:
`from core.mapper import Mapper, led_behavior`
para:
`from core.mapper import Mapper, idle_notes, led_behavior`

- [ ] **Step 2: Rodar o teste e verificar que falha**

Run: `.venv/bin/python -m pytest tests/test_led.py::test_idle_notes_returns_only_note_bindings -v`
Expected: FAIL — `ImportError: cannot import name 'idle_notes' from 'core.mapper'`.

- [ ] **Step 3: Implementar `idle_notes` em `core/mapper.py`**

Adicionar a função no nível do módulo (junto de `led_behavior`):

```python
def idle_notes(profile) -> list[int]:
    """Números dos pads (notas) com binding — candidatos a acender no idle.

    Faders (input 'cc') não têm LED, então ficam de fora.
    """
    return [b.number for b in profile.bindings if b.input_type == "note"]
```

- [ ] **Step 4: Rodar o teste e verificar que passa**

Run: `.venv/bin/python -m pytest tests/test_led.py::test_idle_notes_returns_only_note_bindings -v`
Expected: PASS.

- [ ] **Step 5: Acender os pads no startup do `main.py`**

Em `main.py`, trocar o import:
`from core.mapper import Mapper`
por:
`from core.mapper import Mapper, idle_notes`

Em `run_headless`, logo após a linha `mapper = Mapper(profile, backends, led=led)`, adicionar:

```python
    led.set_idle(idle_notes(profile))      # acende os pads mapeados (idle)
```

- [ ] **Step 6: Acender os pads no startup do `gui/app.py`**

Em `gui/app.py`, trocar o import:
`from core.mapper import Mapper`
por:
`from core.mapper import Mapper, idle_notes`

Em `run_gui`, logo após a linha `mapper = Mapper(profile, backends, led=led)`, adicionar:

```python
    led.set_idle(idle_notes(profile))      # acende os pads mapeados (idle)
```

- [ ] **Step 7: Rodar a suíte e um smoke de import**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS — toda a suíte (`test_led.py` + `test_profiles.py`).

Run: `.venv/bin/python -c "import main, gui.app; from core.mapper import idle_notes; from core.profiles import load_profile; print(idle_notes(load_profile('profiles/powerpoint.md')))"`
Expected: imprime `[0, 1, 8, 16, 17, 24, 25, 26, 56, 57]` (notas mapeadas do perfil powerpoint), sem erro de import.

- [ ] **Step 8: Commit**

```bash
git add core/mapper.py main.py gui/app.py tests/test_led.py
git commit -m "feat: acender pads mapeados (idle) no startup via idle_notes"
```

---

## Notas de verificação manual (hardware)

Após Task 2, com a APC conectada (`.venv/bin/python main.py --headless profiles/powerpoint.md`):
1. Os pads 0, 1, 8, 16, 17, 24, 25, 26, 56, 57 acendem verde ao iniciar.
2. Apertar um pad momentâneo (ex. nota 0) pisca vermelho e volta a verde.
3. Apertar um toggle de FX (nota 24/26) fica vermelho fixo; apertar de novo volta verde.
4. Ctrl+C apaga todos os pads.
