# Feedback de LED na APC mini — Design

**Data:** 2026-06-22
**Status:** aprovado para implementação

## Objetivo

Ao acionar um botão da APC mini, o próprio botão deve dar retorno visual no
hardware conforme o **tipo do comando**:

- **Momentâneo** (slide, `ppt_goto`, flash de tela, etc.) → **acende rápido** (flash verde ~150ms e apaga).
- **Toggle** (`strobe_toggle`, `blackout_toggle`) → **permanece aceso** (vermelho fixo) enquanto ativo; apaga ao desligar.
- **Em andamento** (IA `prompt` enquanto streama a resposta) → **pisca** (amarelo) durante; apaga ao terminar.

A associação tipo→comportamento é **inferida automaticamente** pelo backend e
pelo nome da ação (`do`). Não há configuração nova no perfil Markdown.

## Contexto atual

Hoje o `MidiListener` (`midi/listener.py`) só abre a **porta de entrada**. Não
existe nenhuma saída MIDI. A APC mini só acende LEDs quando recebe um `note_on`
de volta na mesma nota; a velocity define a cor/efeito.

## Arquitetura

### Novo componente: `midi/output.py` → `LedController`

Simétrico ao `listener.py`. Abre a porta de **saída** cujo nome contém
`APC_PORT_HINT` ("APC MINI") via `mido`. Se `mido` ou o dispositivo não
estiverem presentes, entra em **modo dry** (imprime `[led/dry] ...`), igual ao
resto do projeto.

Mapa de cores (velocity), em constantes nomeadas — *varia por firmware da APC*:

```
OFF          = 0
GREEN        = 1
RED          = 3
YELLOW_BLINK = 6   # variante piscante (blink por hardware)
```

API:

- `flash(note: int)` — envia GREEN e agenda OFF após ~150ms via `threading.Timer` one-shot.
- `set(note: int, on: bool)` — RED fixo se `on`, OFF caso contrário.
- `blink(note: int)` — YELLOW_BLINK (a APC pisca sozinha, sem thread contínua).
- `clear(note: int)` — OFF.
- `close()` — fecha a porta e cancela timers pendentes.

Escritas na porta são protegidas por um `threading.Lock` (mapper, thread da IA
e os timers de flash podem escrever concorrentemente).

### Inferência do comportamento — `mapper.py`

Função pura e testável:

```python
def led_behavior(input_type: str, backend: str, do: str) -> str | None:
    if input_type == "cc":
        return None                      # faders não têm LED
    if do.endswith("_toggle"):
        return "toggle"
    if backend == "ai" and do == "prompt":
        return "progress"
    return "flash"
```

### Fluxo em `Mapper.handle`

Depois de resolver o binding e despachar ao backend:

1. Calcula `behavior = led_behavior(input_type, binding.backend, binding.do)`.
2. Chama `result = backend.execute(do, args, value=event.value, note=event.number)`.
3. Se não houver `led` ou `behavior is None` ou input for `cc` → não faz nada.
4. `behavior == "flash"` → `led.flash(note)`.
5. `behavior == "toggle"` → `led.set(note, on=bool(result))`.
6. `behavior == "progress"` → **nada aqui**; o `AiBackend` cuida do ciclo
   (`led.blink(note)` ao iniciar, `led.clear(note)` quando o streaming termina,
   tanto em done quanto em error).

### Mudanças de interface

- `Backend.execute(self, do, args, value=0, note=None) -> bool | None`
  - `note` e o retorno são opcionais; `keyboard` e `applescript` ignoram ambos.
  - `FxBackend` retorna o novo estado (`bool`) nas ações `*_toggle`.
- `Mapper.__init__(self, profile, backends, led=None)` — `led` opcional para que
  headless e testes rodem sem hardware.
- `AiBackend` ganha o atributo `led` (default `None`); usa-o para `blink`/`clear`
  guardando o `note` recebido em `execute`.

### Wiring

- `main.build_backends()` / `run_headless()` e `gui/app.run_gui()` criam um
  `LedController`, injetam no `Mapper` (`led=`) e no `ai_backend.led`.
- `LedController` reutiliza `APC_PORT_HINT` de `midi/listener.py`.
- Encerramento: `LedController.close()` no `finally`/shutdown junto do `listener.stop()`.

## Testes — `tests/test_led.py`

- `led_behavior(...)` devolve o tipo correto para: cc→None, `strobe_toggle`→toggle,
  ai/`prompt`→progress, `key`→flash.
- `LedController` com um *sink* falso (captura mensagens enviadas):
  - `flash` → GREEN e depois OFF (após o timer disparar).
  - `set(on=True)` → RED; `set(on=False)` → OFF.
  - `blink` → YELLOW_BLINK.
  - `clear` → OFF.
  - Modo dry (sem porta) não levanta exceção.

## Fora de escopo (YAGNI)

- Acender LEDs "ociosos" indicando quais botões estão mapeados.
- Espelhar o estado dos LEDs no `ApcGrid` da tela.

Ambos podem ser adicionados depois sem alterar este design.
