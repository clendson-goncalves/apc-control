"""Testes do feedback de LED: inferência de comportamento e LedController."""
import time

from core.bus import MidiEvent
from core.mapper import Mapper, idle_notes, led_behavior
from core.profiles import Binding, Profile
from midi.output import LedController, OFF, GREEN, RED, YELLOW_BLINK
from outputs.fx_bridge import FxBackend


def test_idle_notes_returns_only_note_bindings():
    profile = Profile("T", "", [
        Binding("note", 0, "keyboard", "key", {}),
        Binding("cc", 48, "fx", "strobe_rate", {}),
        Binding("note", 8, "fx", "flash", {}),
    ])
    assert idle_notes(profile) == [0, 8]    # ignora cc, mantém ordem


def test_led_behavior_cc_has_no_led():
    assert led_behavior("cc", "strobe_rate") is None


def test_led_behavior_toggle():
    assert led_behavior("note", "strobe_toggle") == "toggle"
    assert led_behavior("note", "blackout_toggle") == "toggle"


def test_led_behavior_default_is_flash():
    assert led_behavior("note", "key") == "flash"
    assert led_behavior("note", "ppt_goto") == "flash"


def _recorder():
    sent: list[tuple[int, int]] = []
    return sent, (lambda note, vel: sent.append((note, vel)))


def test_flash_sends_red_then_restores_off():
    sent, sink = _recorder()
    led = LedController(flash_ms=10, sink=sink)
    led.flash(5)
    assert sent[0] == (5, RED)          # pisca vermelho
    time.sleep(0.05)
    assert sent[-1] == (5, OFF)         # sem idle registrado -> volta OFF
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


def test_flash_timer_is_pruned_after_firing():
    sent, sink = _recorder()
    led = LedController(flash_ms=10, sink=sink)
    led.flash(5)
    time.sleep(0.05)
    assert led._timers == []   # timer se remove após disparar (sem vazamento)
    led.close()


def test_dry_mode_does_not_raise():
    # sem sink e sem mido/dispositivo -> modo dry, só imprime
    led = LedController(sink=None)
    led.flash(0)
    led.set(0, on=True)
    led.blink(0)
    led.clear(0)
    led.close()


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


def test_fx_toggle_returns_new_state():
    fx = FxBackend()  # signals=None -> modo dry
    assert fx.execute("strobe_toggle", {}) is True
    assert fx.execute("strobe_toggle", {}) is False
    assert fx.execute("blackout_toggle", {}) is True
    assert fx.execute("flash", {}) is None


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


def test_mapper_sets_led_off_from_falsey_toggle():
    led = _SpyLed()
    be = _StubBackend(ret=False)
    m = _mapper_with(Binding("note", 26, "fx", "blackout_toggle", {}), be, led)
    m.handle(MidiEvent("note_on", 26, 127))
    assert led.sets == [(26, False)]


def test_mapper_without_led_does_not_crash():
    be = _StubBackend()
    m = _mapper_with(Binding("note", 0, "keyboard", "key", {}), be, led=None)
    m.handle(MidiEvent("note_on", 0, 127))   # não deve levantar
