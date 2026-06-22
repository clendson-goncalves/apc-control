"""Listener MIDI da APC mini.

Usa mido + python-rtmidi. Se as libs ou o dispositivo não estiverem presentes
(ex.: rodando neste sandbox), cai em modo SIMULADO para você ver o fluxo end-to-end.
"""
from __future__ import annotations

import threading
import time

from core.bus import EventBus, MidiEvent

# A APC mini costuma se apresentar com "APC MINI" no nome da porta.
APC_PORT_HINT = "APC MINI"


def _try_import_mido():
    try:
        import mido  # type: ignore
        return mido
    except Exception:
        return None


class MidiListener:
    def __init__(self, bus: EventBus, port_hint: str = APC_PORT_HINT) -> None:
        self.bus = bus
        self.port_hint = port_hint
        self._mido = _try_import_mido()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ---- descoberta de portas -------------------------------------------------
    def list_ports(self) -> list[str]:
        if not self._mido:
            return []
        try:
            return list(self._mido.get_input_names())
        except Exception:
            return []

    def _find_port(self) -> str | None:
        for name in self.list_ports():
            if self.port_hint.lower() in name.lower():
                return name
        return None

    # ---- conversão mido.Message -> MidiEvent ----------------------------------
    @staticmethod
    def _to_event(msg) -> MidiEvent | None:
        if msg.type == "note_on":
            return MidiEvent("note_on", msg.note, msg.velocity, getattr(msg, "channel", 0))
        if msg.type == "note_off":
            return MidiEvent("note_off", msg.note, 0, getattr(msg, "channel", 0))
        if msg.type == "control_change":
            return MidiEvent("control_change", msg.control, msg.value, getattr(msg, "channel", 0))
        return None

    # ---- loop principal -------------------------------------------------------
    def start(self) -> None:
        port = self._find_port() if self._mido else None
        if port is None:
            print("[MIDI] APC não encontrada — entrando em modo SIMULADO.")
            self._thread = threading.Thread(target=self._run_simulated, daemon=True)
        else:
            print(f"[MIDI] conectado a: {port}")
            self._thread = threading.Thread(target=self._run_real, args=(port,), daemon=True)
        self._thread.start()

    def _run_real(self, port: str) -> None:
        with self._mido.open_input(port) as inport:  # type: ignore
            for msg in inport:
                if self._stop.is_set():
                    break
                ev = self._to_event(msg)
                if ev:
                    self.bus.publish(ev)

    def _run_simulated(self) -> None:
        """Gera alguns eventos fictícios para validar o pipeline sem hardware."""
        script = [
            MidiEvent("note_on", 0, 127),     # botão grid 0 -> avançar slide
            MidiEvent("note_on", 1, 127),     # botão grid 1 -> voltar slide
            MidiEvent("control_change", 48, 64),   # fader 1 -> meio curso
            MidiEvent("note_on", 8, 127),     # botão grid 8 -> blackout
            MidiEvent("note_on", 56, 127),    # botão -> ação de IA
        ]
        time.sleep(0.5)
        for ev in script:
            if self._stop.is_set():
                return
            print(f"[MIDI/sim] {ev.kind} number={ev.number} value={ev.value}")
            self.bus.publish(ev)
            time.sleep(1.0)
        print("[MIDI/sim] fim da simulação (loop ocioso).")
        while not self._stop.is_set():
            time.sleep(0.2)

    def stop(self) -> None:
        self._stop.set()
