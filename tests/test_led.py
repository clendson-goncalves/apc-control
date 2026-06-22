"""Testes do feedback de LED: inferência de comportamento e LedController."""
import time

from core.bus import MidiEvent
from core.mapper import Mapper, led_behavior
from core.profiles import Binding, Profile
from midi.output import LedController, OFF, GREEN, RED, YELLOW_BLINK
from outputs.ai import AiBackend
from outputs.fx_bridge import FxBackend


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


def test_fx_toggle_returns_new_state():
    fx = FxBackend()  # signals=None -> modo dry
    assert fx.execute("strobe_toggle", {}) is True
    assert fx.execute("strobe_toggle", {}) is False
    assert fx.execute("blackout_toggle", {}) is True
    assert fx.execute("flash", {}) is None


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
