"""Testes do feedback de LED: inferência de comportamento e LedController."""
import time

from core.mapper import led_behavior
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
