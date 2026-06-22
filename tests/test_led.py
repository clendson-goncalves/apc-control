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
