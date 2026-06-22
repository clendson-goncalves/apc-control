# LED idle aceso + muda cor ao clicar — Design

## Objetivo

Na APC mini, todos os pads **com binding de nota** no perfil ficam acesos
(VERDE) como estado de "disponível". Ao acionar um pad, o LED **muda de cor**
para dar feedback e, ao terminar a ação, **volta para a cor idle** (verde) em
vez de apagar.

## Motivação

Hoje o `LedController` acende o LED durante a ação e depois manda `OFF`. Dois
problemas de UX:

1. Pads mapeados ficam apagados quando ociosos — o usuário não tem como saber,
   olhando o hardware, quais botões fazem algo (foi a origem do "cliquei e não
   acendeu": o pad apertado não tinha binding).
2. Após cada ação o pad apaga, perdendo a indicação de que ele continua
   disponível.

## Comportamento

Faders (entradas `cc`, ex. CC 48–56) **não têm LED** e ficam fora deste
recurso — apenas bindings de nota acendem.

Estado idle (parado): **VERDE** (`GREEN = 1`).

| Tipo de ação                          | Ao clicar              | Depois                  |
| ------------------------------------- | ---------------------- | ----------------------- |
| Momentâneo (slide, ppt_goto, flash)   | pisca **VERMELHO** ~150ms | volta **VERDE** (idle) |
| Toggle ON (strobe_toggle/blackout)    | **VERMELHO** fixo      | —                       |
| Toggle OFF                            | —                      | volta **VERDE** (idle)  |
| IA `prompt` (streaming)               | **AMARELO piscando**   | volta **VERDE** ao fim  |

Pad **sem** entrada idle registrada (não-mapeado) restaura para `OFF` — mantém
o comportamento antigo para qualquer pad que não esteja no mapa idle.

## Arquitetura

A mudança central fica no `LedController` (`midi/output.py`): ele passa a
guardar um mapa de cor de descanso por nota e, ao terminar uma ação, restaura
essa cor em vez de mandar `OFF`.

### `midi/output.py` — `LedController`

Novo estado:
- `self._idle: dict[int, int]` — `note → cor de descanso`. Vazio por padrão.

Novo método:
- `set_idle(self, notes: list[int], color: int = GREEN) -> None` — para cada
  nota: registra `self._idle[note] = color` e manda `self._send(note, color)`
  (acende). Usado no startup.

Novo helper interno:
- `_restore(self, note: int) -> None` — `self._send(note, self._idle.get(note, OFF))`.

Métodos alterados:
- `flash(note)`: manda `RED` (era `GREEN`); o timer chama `_restore(note)`
  (era `_send(note, OFF)` via `_flash_off`).
- `set(note, on)`: `on=True` → `RED`; `on=False` → `_restore(note)` (era `OFF`).
- `clear(note)`: passa a `_restore(note)` (era `OFF`). Usado pela IA ao
  terminar o stream e no dismiss.
- `close()`: além de cancelar timers e fechar a porta, apaga todos os pads
  registrados em `self._idle` (manda `OFF` em cada um) para não deixar a
  controladora acesa após sair. Apaga **antes** de fechar a porta.

Métodos inalterados: `blink(note)` (continua `YELLOW_BLINK`), `_send`, `_find_port`.

Cores inalteradas: `OFF=0`, `GREEN=1`, `RED=3`, `YELLOW_BLINK=6`.

### `core/mapper.py`

**Sem mudanças.** `led_behavior()` (cc→None, `*_toggle`→toggle, ai
`prompt`→progress, else flash) e o roteamento de LED continuam idênticos: o
mapper chama `flash`/`set`/(IA chama `blink`/`clear`), e a nova semântica de
"voltar pro idle" vive inteira dentro do `LedController`.

### `main.py` e `gui/app.py` — acender no startup

Após criar o `LedController` e carregar o `profile`, ambos calculam as notas
mapeadas e chamam `set_idle`:

```python
mapped_notes = [b.number for b in profile.bindings if b.input_type == "note"]
led.set_idle(mapped_notes)
```

Em `main.run_headless`: após `led = LedController()` / `mapper = Mapper(...)`.
Em `gui/app.run_gui`: após `led = LedController()` / `mapper = Mapper(...)`.

## O que NÃO muda

- A inferência de comportamento (`led_behavior`) e o fluxo do mapper.
- As constantes de cor e o `MAX_SAFE_HZ`.
- O modo DRY (sem hardware/mido) — `set_idle`/`_restore` passam pelo mesmo
  `_send`, então em DRY apenas imprimem `[led/dry] ...`.
- A API da IA (`AiBackend`) — ela já chama `blink`/`clear`; `clear` agora
  restaura idle automaticamente.

## Testes

Arquivo: `tests/test_led.py` (usa o `sink` injetável já existente).

Ajustar testes existentes que assumem volta-pra-OFF:
- `test_flash_sends_green_then_off` → flash agora manda `RED` e, sem idle
  registrado, restaura `OFF`. Renomear/ajustar para
  `test_flash_sends_red_then_restores_off`.
- `test_set_on_is_red_off_is_off` → sem idle, `on=False` restaura `OFF`
  (continua válido); manter, mas garantir clareza do caso "sem idle".

Adicionar:
- `set_idle` acende cada nota com a cor e registra no mapa
  (`sent` contém `(note, GREEN)` para cada nota; `_idle` populado).
- flash de pad **idle** volta `GREEN`: após `set_idle([5])`, `flash(5)` →
  `sent` termina em `(5, GREEN)` após o timer.
- flash de pad **não-idle** volta `OFF` (caso default).
- toggle `set(note, on=False)` de pad **idle** volta `GREEN`.
- `clear(note)` de pad **idle** volta `GREEN`; de pad não-idle volta `OFF`.
- `close()` apaga todos os pads idle (manda `OFF` em cada nota registrada).

Os testes de `led_behavior`, `FxBackend` e `AiBackend` permanecem; verificar
que `test_ai_*` (que usam `_FakeLed` com `clear`) seguem válidos — o `_FakeLed`
não implementa a semântica de restore, apenas registra a chamada, então
continuam passando.

## Critérios de sucesso

1. Ao iniciar o app com `profiles/powerpoint.md`, os pads de nota
   (0, 1, 8, 16, 17, 24, 25, 26, 56, 57) acendem verde no hardware.
2. Clicar num pad momentâneo pisca vermelho e volta a verde.
3. Toggle ON fica vermelho fixo; OFF volta a verde.
4. IA `prompt` pisca amarelo enquanto responde e volta a verde ao terminar.
5. Ao sair (Ctrl+C / fechar janela), os pads apagam.
6. `pytest tests/test_led.py -v` passa.
