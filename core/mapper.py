"""Mapper: liga eventos da APC às ações do perfil ativo, despachando aos backends."""
from __future__ import annotations

from typing import Any

from core.bus import MidiEvent
from core.profiles import Profile


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
