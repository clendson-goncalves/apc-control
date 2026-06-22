"""Ponte EventBus → Signal Qt.

Subscreve no bus (chamado da thread do listener) e reemite via Signal.
A conexão Qt.AutoConnection garante que slots rodem na thread do receptor.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from core.bus import EventBus, MidiEvent


class MidiBridge(QObject):
    event = Signal(object)   # MidiEvent

    def __init__(self, bus: EventBus, parent=None) -> None:
        super().__init__(parent)
        bus.subscribe(self._on_event)

    def _on_event(self, ev: MidiEvent) -> None:
        self.event.emit(ev)
