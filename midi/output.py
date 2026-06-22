"""Saída MIDI para os LEDs da APC mini.

Simétrico ao listener: abre a porta de SAÍDA cujo nome contém APC_PORT_HINT
e manda note_on de volta para acender os LEDs. Sem mido/dispositivo, cai em
modo DRY (só imprime), igual ao resto do projeto.

A velocity define cor/efeito na APC mini (VARIA POR FIRMWARE — confirme no
device). Usamos a variante piscante por hardware, então não há thread de
pisca contínua.
"""
from __future__ import annotations

import threading

from midi.listener import APC_PORT_HINT, _try_import_mido

# Mapa de cores (velocity). Varia por firmware da APC mini.
OFF = 0
GREEN = 1
RED = 3
YELLOW_BLINK = 6


class LedController:
    def __init__(
        self, port_hint: str = APC_PORT_HINT, flash_ms: int = 150, sink=None
    ) -> None:
        self._lock = threading.Lock()
        self._timers: list[threading.Timer] = []
        self._idle: dict[int, int] = {}        # note -> cor de descanso
        self._flash_ms = flash_ms
        self._port = None
        self._dry = False

        if sink is not None:
            self._sink = sink                      # injetado nos testes
            return

        mido = _try_import_mido()
        port_name = self._find_port(mido, port_hint)
        if mido and port_name:
            self._port = mido.open_output(port_name)
            print(f"[led] conectado a: {port_name}")
            self._sink = lambda note, vel: self._port.send(
                mido.Message("note_on", note=note, velocity=vel)
            )
        else:
            print("[led] saída da APC não encontrada — modo DRY.")
            self._dry = True
            self._sink = None

    @staticmethod
    def _find_port(mido, port_hint: str) -> str | None:
        if not mido:
            return None
        try:
            for name in mido.get_output_names():
                if port_hint.lower() in name.lower():
                    return name
        except Exception:
            return None
        return None

    def _send(self, note: int, velocity: int) -> None:
        with self._lock:
            if self._sink:
                self._sink(note, velocity)
            elif self._dry:
                print(f"[led/dry] note={note} vel={velocity}")

    def set_idle(self, notes: list[int], color: int = GREEN) -> None:
        """Acende os pads mapeados (estado idle) e registra a cor de descanso."""
        for note in notes:
            self._idle[note] = color
            self._send(note, color)

    def _restore(self, note: int) -> None:
        """Volta o LED para a cor de descanso (idle) ou OFF se não houver."""
        self._send(note, self._idle.get(note, OFF))

    def flash(self, note: int) -> None:
        self._send(note, RED)
        t = threading.Timer(self._flash_ms / 1000, self._flash_off, args=(note,))
        t.daemon = True
        with self._lock:
            self._timers.append(t)
        t.start()

    def _flash_off(self, note: int) -> None:
        """Callback do timer: volta o LED ao idle e remove o próprio timer da lista."""
        self._restore(note)
        # Timer é subclasse de Thread; rodando no próprio thread, current_thread() é ele.
        cur = threading.current_thread()
        with self._lock:
            try:
                self._timers.remove(cur)
            except ValueError:
                pass

    def set(self, note: int, on: bool) -> None:
        if on:
            self._send(note, RED)
        else:
            self._restore(note)

    def blink(self, note: int) -> None:
        self._send(note, YELLOW_BLINK)

    def clear(self, note: int) -> None:
        self._restore(note)

    def close(self) -> None:
        # Snapshot sob o lock; cancela fora dele (evita segurar o lock no cancel
        # e a corrida com flash() mexendo na lista).
        with self._lock:
            timers = list(self._timers)
            self._timers.clear()
            idle_notes = list(self._idle)
        for t in timers:
            t.cancel()
        for note in idle_notes:
            self._send(note, OFF)      # não deixa a controladora acesa após sair
        if self._port is not None:
            try:
                self._port.close()
            except Exception:
                pass
