"""Event bus e tipos de evento.

Tudo que a APC gera é normalizado em um MidiEvent e publicado aqui.
Os assinantes (mapper, FX, logging) reagem sem acoplamento com o MIDI.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal


EventKind = Literal["note_on", "note_off", "control_change"]


@dataclass(frozen=True)
class MidiEvent:
    """Evento MIDI normalizado vindo da APC."""
    kind: EventKind
    # Para note_on/note_off: 'number' é a nota (0-63 = grid). value = velocity.
    # Para control_change: 'number' é o CC (faders). value = 0-127.
    number: int
    value: int
    channel: int = 0

    @property
    def is_press(self) -> bool:
        return self.kind == "note_on" and self.value > 0

    @property
    def is_release(self) -> bool:
        return self.kind == "note_off" or (self.kind == "note_on" and self.value == 0)


class EventBus:
    """Pub/sub minimalista e síncrono. Suficiente para o protótipo."""

    def __init__(self) -> None:
        self._subscribers: list[Callable[[MidiEvent], None]] = []

    def subscribe(self, handler: Callable[[MidiEvent], None]) -> None:
        self._subscribers.append(handler)

    def publish(self, event: MidiEvent) -> None:
        for handler in self._subscribers:
            try:
                handler(event)
            except Exception as exc:  # noqa: BLE001 - protótipo: não derrubar o loop
                print(f"[EventBus] handler error: {exc}")
