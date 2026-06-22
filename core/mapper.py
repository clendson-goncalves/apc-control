"""Mapper: liga eventos da APC às ações do perfil ativo, despachando aos backends."""
from __future__ import annotations

from typing import Any

from core.bus import MidiEvent
from core.profiles import Profile


class Mapper:
    def __init__(self, profile: Profile, backends: dict[str, Any]) -> None:
        self.profile = profile
        self.backends = backends

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

        # Passa o valor cru junto (faders precisam dele; botões geralmente ignoram).
        backend.execute(binding.do, binding.args, value=event.value)
