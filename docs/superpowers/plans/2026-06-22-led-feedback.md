# APC mini LED Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ao acionar um botão da APC mini, o LED do botão dá retorno visual conforme o tipo do comando: flash (momentâneo), aceso fixo (toggle) ou piscando (em andamento).

**Architecture:** Um novo `LedController` (`midi/output.py`) abre a porta de **saída** MIDI da APC e envia `note_on` de volta para acender LEDs. O `Mapper` infere o comportamento pelo tipo da ação (`led_behavior`) e comanda o LED: flash e toggle direto; o ciclo "em andamento" da IA fica a cargo do `AiBackend` (blink ao iniciar, clear ao terminar). Sem hardware/`mido`, tudo cai em modo dry.

**Tech Stack:** Python 3.10+, `mido` + `python-rtmidi` (opcionais, já usados pelo listener), `threading` (timers), `pytest`.

## Global Constraints

- Python 3.10+; usar sintaxe `X | None`, `list[...]`.
- Comentários e docstrings em **português** (convenção do projeto).
- TODOs futuros usam a tag `# TODO(claude-code):`.
- Backends sem libs nativas / sem hardware **não podem quebrar**: caem em modo dry imprimindo `[nome/dry] ...`.
- `APC_PORT_HINT = "APC MINI"` já existe em `midi/listener.py` — reutilizar, não duplicar.
- Mapa de cores da APC (velocity) varia por firmware; manter em constantes nomeadas com comentário.

---

### Task 1: Estender a interface `Backend.execute` (assinatura, sem mudar comportamento)

Adiciona `note: int | None = None` e o tipo de retorno `bool | None` em todos os backends, para que tarefas seguintes possam passar a nota e retornar estado de toggle. Nenhuma mudança de comportamento aqui.

**Files:**
- Modify: `outputs/base.py:14`
- Modify: `outputs/keyboard.py:40`
- Modify: `outputs/applescript.py:48`
- Modify: `outputs/fx_bridge.py:32`
- Modify: `outputs/ai.py:46`
- Test: `tests/test_profiles.py` (suíte existente, só precisa continuar passando)

**Interfaces:**
- Produces: `Backend.execute(self, do: str, args: dict[str, Any], value: int = 0, note: int | None = None) -> bool | None` — assinatura comum que o `Mapper` (Task 6) vai chamar com `note=`.

- [ ] **Step 1: Atualizar a base**

Em `outputs/base.py`, trocar a assinatura de `execute`:

```python
class Backend:
    name: str = "base"

    def execute(
        self, do: str, args: dict[str, Any], value: int = 0, note: int | None = None
    ) -> bool | None:
        raise NotImplementedError
```

- [ ] **Step 2: Atualizar os quatro backends concretos**

Em cada arquivo, só a linha do `def execute(...)` muda (corpo intacto):

`outputs/keyboard.py`:
```python
    def execute(
        self, do: str, args: dict[str, Any], value: int = 0, note: int | None = None
    ) -> bool | None:
```

`outputs/applescript.py`:
```python
    def execute(
        self, do: str, args: dict[str, Any], value: int = 0, note: int | None = None
    ) -> bool | None:
```

`outputs/fx_bridge.py`:
```python
    def execute(
        self, do: str, args: dict[str, Any], value: int = 0, note: int | None = None
    ) -> bool | None:
```

`outputs/ai.py`:
```python
    def execute(
        self, do: str, args: dict[str, Any], value: int = 0, note: int | None = None
    ) -> bool | None:
```

- [ ] **Step 3: Rodar a suíte e o import para garantir que nada quebrou**

Run: `pytest tests/test_profiles.py -v && python -c "import outputs.base, outputs.keyboard, outputs.applescript, outputs.fx_bridge, outputs.ai"`
Expected: 7 passed; import sem erro.

- [ ] **Step 4: Commit**

```bash
git add outputs/base.py outputs/keyboard.py outputs/applescript.py outputs/fx_bridge.py outputs/ai.py
git commit -m "refactor: add note/return to Backend.execute signature"
```

---

### Task 2: Função pura `led_behavior` no mapper

Decide o comportamento do LED a partir do tipo de input, backend e ação. Pura e testável sem MIDI.

**Files:**
- Modify: `core/mapper.py` (adicionar a função no topo, após os imports)
- Test: `tests/test_led.py` (criar)

**Interfaces:**
- Produces: `led_behavior(input_type: str, backend: str, do: str) -> str | None` — retorna `"flash"`, `"toggle"`, `"progress"` ou `None`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_led.py`:

```python
"""Testes do feedback de LED: inferência de comportamento e LedController."""
from core.mapper import led_behavior


def test_led_behavior_cc_has_no_led():
    assert led_behavior("cc", "fx", "strobe_rate") is None


def test_led_behavior_toggle():
    assert led_behavior("note", "fx", "strobe_toggle") == "toggle"
    assert led_behavior("note", "fx", "blackout_toggle") == "toggle"


def test_led_behavior_ai_prompt_is_progress():
    assert led_behavior("note", "ai", "prompt") == "progress"


def test_led_behavior_default_is_flash():
    assert led_behavior("note", "keyboard", "key") == "flash"
    assert led_behavior("note", "ai", "dismiss") == "flash"
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `pytest tests/test_led.py -v`
Expected: FAIL com `ImportError: cannot import name 'led_behavior'`.

- [ ] **Step 3: Implementar a função**

Em `core/mapper.py`, logo após os imports e antes de `class Mapper`:

```python
def led_behavior(input_type: str, backend: str, do: str) -> str | None:
    """Infere o comportamento do LED pelo tipo da ação (sem config no perfil).

    cc (faders) não têm LED. Ações '*_toggle' permanecem acesas; o 'prompt'
    da IA pisca enquanto streama; o resto dá um flash momentâneo.
    """
    if input_type == "cc":
        return None
    if do.endswith("_toggle"):
        return "toggle"
    if backend == "ai" and do == "prompt":
        return "progress"
    return "flash"
```

- [ ] **Step 4: Rodar para ver passar**

Run: `pytest tests/test_led.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add core/mapper.py tests/test_led.py
git commit -m "feat: led_behavior inference for LED feedback"
```

---

### Task 3: `LedController` com porta de saída MIDI e modo dry

Componente que envia `note_on` de volta à APC. Testável injetando um `sink` falso.

**Files:**
- Create: `midi/output.py`
- Test: `tests/test_led.py` (adicionar)

**Interfaces:**
- Consumes: `APC_PORT_HINT` de `midi/listener.py`.
- Produces:
  - `LedController(port_hint: str = APC_PORT_HINT, flash_ms: int = 150, sink=None)` — `sink` é um callable `(note: int, velocity: int) -> None` para testes; se `None`, abre a porta real.
  - `.flash(note: int)`, `.set(note: int, on: bool)`, `.blink(note: int)`, `.clear(note: int)`, `.close()`.
  - Constantes `OFF=0`, `GREEN=1`, `RED=3`, `YELLOW_BLINK=6`.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar em `tests/test_led.py`:

```python
import time
from midi.output import LedController, OFF, GREEN, RED, YELLOW_BLINK


def _recorder():
    sent: list[tuple[int, int]] = []
    return sent, (lambda note, vel: sent.append((note, vel)))


def test_flash_sends_green_then_off():
    sent, sink = _recorder()
    led = LedController(flash_ms=10, sink=sink)
    led.flash(5)
    assert sent[0] == (5, GREEN)
    time.sleep(0.05)
    assert sent[-1] == (5, OFF)
    led.close()


def test_set_on_is_red_off_is_off():
    sent, sink = _recorder()
    led = LedController(sink=sink)
    led.set(7, on=True)
    led.set(7, on=False)
    assert sent == [(7, RED), (7, OFF)]
    led.close()


def test_blink_sends_yellow_blink():
    sent, sink = _recorder()
    led = LedController(sink=sink)
    led.blink(9)
    assert sent == [(9, YELLOW_BLINK)]
    led.close()


def test_clear_sends_off():
    sent, sink = _recorder()
    led = LedController(sink=sink)
    led.clear(9)
    assert sent == [(9, OFF)]
    led.close()


def test_dry_mode_does_not_raise():
    # sem sink e sem mido/dispositivo -> modo dry, só imprime
    led = LedController(sink=None)
    led.flash(0)
    led.set(0, on=True)
    led.blink(0)
    led.clear(0)
    led.close()
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `pytest tests/test_led.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'midi.output'`.

- [ ] **Step 3: Implementar `midi/output.py`**

```python
"""Saída MIDI para os LEDs da APC mini.

Simétrico ao listener: abre a porta de SAÍDA cujo nome contém APC_PORT_HINT
e manda note_on de volta para acender os LEDs. Sem mido/dispositivo, cai em
modo DRY (só imprime), igual ao resto do projeto.

A velocity define cor/efeito na APC mini (VARIA POR FIRMWARE — confirme no
device). Usamos a variante piscante por hardware, então não há thread de
pisca contínua.
"""
from __future__ import annotations

import threading

from midi.listener import APC_PORT_HINT, _try_import_mido

# Mapa de cores (velocity). Varia por firmware da APC mini.
OFF = 0
GREEN = 1
RED = 3
YELLOW_BLINK = 6


class LedController:
    def __init__(
        self, port_hint: str = APC_PORT_HINT, flash_ms: int = 150, sink=None
    ) -> None:
        self._lock = threading.Lock()
        self._timers: list[threading.Timer] = []
        self._flash_ms = flash_ms
        self._port = None
        self._dry = False

        if sink is not None:
            self._sink = sink                      # injetado nos testes
            return

        mido = _try_import_mido()
        port_name = self._find_port(mido, port_hint)
        if mido and port_name:
            self._port = mido.open_output(port_name)
            print(f"[led] conectado a: {port_name}")
            self._sink = lambda note, vel: self._port.send(
                mido.Message("note_on", note=note, velocity=vel)
            )
        else:
            print("[led] saída da APC não encontrada — modo DRY.")
            self._dry = True
            self._sink = None

    @staticmethod
    def _find_port(mido, port_hint: str) -> str | None:
        if not mido:
            return None
        try:
            for name in mido.get_output_names():
                if port_hint.lower() in name.lower():
                    return name
        except Exception:
            return None
        return None

    def _send(self, note: int, velocity: int) -> None:
        with self._lock:
            if self._sink:
                self._sink(note, velocity)
            elif self._dry:
                print(f"[led/dry] note={note} vel={velocity}")

    def flash(self, note: int) -> None:
        self._send(note, GREEN)
        t = threading.Timer(self._flash_ms / 1000, self._send, args=(note, OFF))
        t.daemon = True
        self._timers.append(t)
        t.start()

    def set(self, note: int, on: bool) -> None:
        self._send(note, RED if on else OFF)

    def blink(self, note: int) -> None:
        self._send(note, YELLOW_BLINK)

    def clear(self, note: int) -> None:
        self._send(note, OFF)

    def close(self) -> None:
        for t in self._timers:
            t.cancel()
        self._timers.clear()
        if self._port is not None:
            try:
                self._port.close()
            except Exception:
                pass
```

- [ ] **Step 4: Rodar para ver passar**

Run: `pytest tests/test_led.py -v`
Expected: todos os testes (Task 2 + Task 3) passam.

- [ ] **Step 5: Commit**

```bash
git add midi/output.py tests/test_led.py
git commit -m "feat: LedController for APC mini LED output"
```

---

### Task 4: `FxBackend` retorna o estado nos toggles

Para o `Mapper` saber se um toggle ficou ligado ou desligado, `execute` passa a retornar o novo estado nas ações `*_toggle`.

**Files:**
- Modify: `outputs/fx_bridge.py:32-57`
- Test: `tests/test_led.py` (adicionar)

**Interfaces:**
- Produces: `FxBackend.execute(...)` retorna `bool` (novo estado) para `strobe_toggle`/`blackout_toggle`; `None` para as demais ações.

- [ ] **Step 1: Escrever o teste que falha**

Adicionar em `tests/test_led.py`:

```python
from outputs.fx_bridge import FxBackend


def test_fx_toggle_returns_new_state():
    fx = FxBackend()  # signals=None -> modo dry
    assert fx.execute("strobe_toggle", {}) is True
    assert fx.execute("strobe_toggle", {}) is False
    assert fx.execute("blackout_toggle", {}) is True
    assert fx.execute("flash", {}) is None
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `pytest tests/test_led.py::test_fx_toggle_returns_new_state -v`
Expected: FAIL — `execute` retorna `None` em vez de `True`.

- [ ] **Step 3: Implementar o retorno**

Substituir o corpo de `FxBackend.execute` (em `outputs/fx_bridge.py`) por (note os `return`):

```python
    def execute(
        self, do: str, args: dict[str, Any], value: int = 0, note: int | None = None
    ) -> bool | None:
        if do == "strobe_toggle":
            self._strobe_on = not self._strobe_on
            if self.signals:
                self.signals.strobe.emit(self._strobe_on)
            else:
                print(f"[fx/dry] strobo {'ON' if self._strobe_on else 'OFF'}")
            return self._strobe_on
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
            return self._blackout_on
        else:
            print(f"[fx] ação desconhecida: {do}")
        return None
```

- [ ] **Step 4: Rodar para ver passar**

Run: `pytest tests/test_led.py -v`
Expected: todos passam.

- [ ] **Step 5: Commit**

```bash
git add outputs/fx_bridge.py tests/test_led.py
git commit -m "feat: FxBackend returns toggle state for LED feedback"
```

---

### Task 5: `AiBackend` controla o LED "em andamento"

A IA acende o LED piscando ao iniciar o `prompt` e o apaga quando o streaming termina (done ou error). O `dismiss` também apaga.

**Files:**
- Modify: `outputs/ai.py:34-98`
- Test: `tests/test_led.py` (adicionar)

**Interfaces:**
- Consumes: `LedController.blink(note)` / `LedController.clear(note)` (Task 3).
- Produces: `AiBackend.led` (atributo, default `None`); `execute("prompt", ..., note=N)` pisca o LED `N` e o limpa ao fim do stream.

- [ ] **Step 1: Escrever o teste que falha**

Adicionar em `tests/test_led.py`:

```python
from outputs.ai import AiBackend


class _FakeLed:
    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def blink(self, note):
        self.calls.append(("blink", note))

    def clear(self, note):
        self.calls.append(("clear", note))


def test_ai_prompt_blinks_then_clears_on_done():
    ai = AiBackend()          # sem API key -> _stream_dry, mas síncrono no teste
    led = _FakeLed()
    ai.led = led
    # roda o stream de forma síncrona (sem thread) para o teste ser determinístico
    ai._run("Oi", note=42)
    assert led.calls[0] == ("blink", 42)
    assert led.calls[-1] == ("clear", 42)


def test_ai_dismiss_clears_led():
    ai = AiBackend()
    led = _FakeLed()
    ai.led = led
    ai.execute("dismiss", {}, note=42)
    assert ("clear", 42) in led.calls
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `pytest tests/test_led.py::test_ai_prompt_blinks_then_clears_on_done -v`
Expected: FAIL — `AiBackend` não tem `led`/`_run`.

- [ ] **Step 3: Implementar o controle de LED na IA**

Em `outputs/ai.py`:

1. No `__init__`, adicionar o atributo `led` (após `self.signals = None`):

```python
        self.signals = None         # GUI injeta AiSignals; None = print
        self.led = None             # LedController injetado; None = sem LED
```

2. Trocar `execute` e o `_stream`/`_stream_dry` para receberem `note` e usarem `_run`. Substituir o método `execute` por:

```python
    def execute(
        self, do: str, args: dict[str, Any], value: int = 0, note: int | None = None
    ) -> bool | None:
        if do == "prompt":
            prompt = args.get("prompt", "").strip()
            if not prompt:
                print("[ai] prompt vazio, ignorado")
                return None
            threading.Thread(
                target=self._run, args=(prompt,), kwargs={"note": note}, daemon=True
            ).start()
        elif do == "dismiss":
            if note is not None and self.led:
                self.led.clear(note)
            if self.signals:
                self.signals.dismiss.emit()
            else:
                print("[ai/dry] dismiss")
        else:
            print(f"[ai] ação desconhecida: {do}")
        return None
```

3. Adicionar `_run` (orquestra LED + stream, de forma síncrona — a thread fica em `execute`) e ajustar o stream para limpar o LED ao terminar. Substituir os métodos `_stream` e `_stream_dry` por:

```python
    def _run(self, prompt: str, note: int | None = None) -> None:
        """Acende o LED piscando, streama, e limpa o LED ao terminar."""
        if note is not None and self.led:
            self.led.blink(note)
        try:
            if self._client is None:
                self._stream_dry(prompt)
            else:
                self._stream(prompt)
        finally:
            if note is not None and self.led:
                self.led.clear(note)

    def _stream(self, prompt: str) -> None:
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
```

(O `try/finally` em `_run` garante o `clear` mesmo se o stream der erro; `_stream` já trata sua própria exceção, então o `finally` cobre o caminho dry e qualquer falha inesperada.)

- [ ] **Step 4: Rodar para ver passar**

Run: `pytest tests/test_led.py -v`
Expected: todos passam.

- [ ] **Step 5: Commit**

```bash
git add outputs/ai.py tests/test_led.py
git commit -m "feat: AiBackend drives blinking LED during streaming"
```

---

### Task 6: Ligar o `Mapper` ao `LedController`

O `Mapper` recebe um `led` opcional, infere o comportamento e comanda flash/toggle (o "progress" fica com a IA).

**Files:**
- Modify: `core/mapper.py:10-41`
- Test: `tests/test_led.py` (adicionar)

**Interfaces:**
- Consumes: `led_behavior` (Task 2); `LedController.flash/set` (Task 3); retorno bool de `FxBackend` (Task 4).
- Produces: `Mapper(profile, backends, led=None)`; em `handle`, chama `backend.execute(..., note=event.number)` e aciona o LED.

- [ ] **Step 1: Escrever o teste que falha**

Adicionar em `tests/test_led.py`:

```python
from core.bus import MidiEvent
from core.mapper import Mapper
from core.profiles import Binding, Profile


class _SpyLed:
    def __init__(self):
        self.flashed = []
        self.sets = []

    def flash(self, note):
        self.flashed.append(note)

    def set(self, note, on):
        self.sets.append((note, on))


class _StubBackend:
    """Retorna o que for configurado; registra a nota recebida."""
    def __init__(self, ret=None):
        self.ret = ret
        self.last_note = None

    def execute(self, do, args, value=0, note=None):
        self.last_note = note
        return self.ret


def _mapper_with(binding, backend, led):
    profile = Profile("T", "", [binding])
    return Mapper(profile, {binding.backend: backend}, led=led)


def test_mapper_flashes_on_momentary_note():
    led = _SpyLed()
    be = _StubBackend()
    m = _mapper_with(Binding("note", 0, "keyboard", "key", {}), be, led)
    m.handle(MidiEvent("note_on", 0, 127))
    assert led.flashed == [0]
    assert be.last_note == 0


def test_mapper_sets_led_from_toggle_result():
    led = _SpyLed()
    be = _StubBackend(ret=True)
    m = _mapper_with(Binding("note", 24, "fx", "strobe_toggle", {}), be, led)
    m.handle(MidiEvent("note_on", 24, 127))
    assert led.sets == [(24, True)]
    assert led.flashed == []


def test_mapper_progress_leaves_led_to_backend():
    led = _SpyLed()
    be = _StubBackend()
    m = _mapper_with(Binding("note", 56, "ai", "prompt", {}), be, led)
    m.handle(MidiEvent("note_on", 56, 127))
    assert led.flashed == [] and led.sets == []   # IA cuida do blink/clear
    assert be.last_note == 56


def test_mapper_without_led_does_not_crash():
    be = _StubBackend()
    m = _mapper_with(Binding("note", 0, "keyboard", "key", {}), be, led=None)
    m.handle(MidiEvent("note_on", 0, 127))   # não deve levantar
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `pytest tests/test_led.py -v`
Expected: FAIL — `Mapper.__init__` não aceita `led`.

- [ ] **Step 3: Implementar a ligação no mapper**

Em `core/mapper.py`, atualizar `__init__` e `handle`:

```python
class Mapper:
    def __init__(self, profile: Profile, backends: dict[str, Any], led=None) -> None:
        self.profile = profile
        self.backends = backends
        self.led = led          # LedController | None

    def set_profile(self, profile: Profile) -> None:
        self.profile = profile
        print(f"[Mapper] perfil ativo: {profile.name}")

    def handle(self, event: MidiEvent) -> None:
        # Faders disparam continuamente; botões só no press (evita disparo no release).
        if event.kind == "control_change":
            input_type, trigger = "cc", True
        elif event.is_press:
            input_type, trigger = "note", True
        else:
            input_type, trigger = "note", False

        if not trigger:
            return

        binding = self.profile.find(input_type, event.number)
        if binding is None:
            return

        backend = self.backends.get(binding.backend)
        if backend is None:
            print(f"[Mapper] backend '{binding.backend}' indisponível")
            return

        # Passa o valor cru e a nota (para o feedback de LED).
        result = backend.execute(
            binding.do, binding.args, value=event.value, note=event.number
        )

        # Feedback de LED conforme o tipo da ação.
        if self.led is None:
            return
        behavior = led_behavior(input_type, binding.backend, binding.do)
        if behavior == "flash":
            self.led.flash(event.number)
        elif behavior == "toggle":
            self.led.set(event.number, on=bool(result))
        # "progress" e None: nada aqui (a IA cuida do blink/clear).
```

- [ ] **Step 4: Rodar para ver passar**

Run: `pytest tests/test_led.py tests/test_profiles.py -v`
Expected: todos passam.

- [ ] **Step 5: Commit**

```bash
git add core/mapper.py tests/test_led.py
git commit -m "feat: Mapper drives LED feedback per action type"
```

---

### Task 7: Wiring nos entry points (headless e GUI)

Cria o `LedController`, injeta no `Mapper` e no `AiBackend`, e fecha no shutdown.

**Files:**
- Modify: `main.py:28-34` e `main.py:37-59`
- Modify: `gui/app.py:24-71`
- Test: smoke manual (sem hardware -> modo dry, sem exceções)

**Interfaces:**
- Consumes: `LedController` (Task 3), `Mapper(..., led=)` (Task 6), `AiBackend.led` (Task 5).

- [ ] **Step 1: Wiring no `main.py` (headless)**

`build_backends` retorna também o `ai_backend` para podermos injetar o led nele. Substituir `build_backends` e `run_headless`:

```python
from midi.output import LedController   # add no topo, junto dos outros imports


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
    led = LedController()
    backends["ai"].led = led
    mapper = Mapper(profile, backends, led=led)
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
        led.close()
```

- [ ] **Step 2: Wiring no `gui/app.py`**

Adicionar o import e criar/injetar/fechar o `LedController`:

```python
from midi.output import LedController   # add no topo
```

Logo após a criação dos backends (depois do bloco `backends = {...}`), adicionar:

```python
    led = LedController()
    ai_backend.led = led
```

Trocar a criação do mapper para passar o led:

```python
    mapper = Mapper(profile, backends, led=led)
```

E no `finally`, fechar o led junto do listener:

```python
    try:
        sys.exit(app.exec())
    finally:
        listener.stop()
        led.close()
```

- [ ] **Step 3: Smoke test headless (modo dry, sem hardware)**

Run: `python main.py --headless profiles/powerpoint.md` e aguardar a simulação rodar (~6s), depois Ctrl+C.
Expected: aparecem linhas `[led/dry] note=... vel=...` (ou `[led] conectado a:` se a APC estiver plugada); sem traceback; encerra limpo.

- [ ] **Step 4: Rodar a suíte completa**

Run: `pytest tests/ -v`
Expected: todos os testes passam (`test_profiles.py` + `test_led.py`).

- [ ] **Step 5: Commit**

```bash
git add main.py gui/app.py
git commit -m "feat: wire LedController into headless and GUI entry points"
```

---

## Notas finais

- **Doc:** ao concluir, vale acrescentar uma linha no `CLAUDE.md` (seção Architecture / referência MIDI) descrevendo `midi/output.py` e o mapa de velocity, mas isso pode ir num commit de docs separado e não bloqueia a feature.
- **Fora de escopo (YAGNI):** LEDs "ociosos" para botões mapeados e espelhamento no `ApcGrid` — adicionáveis depois sem mexer neste design.
