"""Painel ao vivo: status MIDI, log de eventos, gatilhos manuais de FX.

O aviso de fotossensibilidade aparece UMA vez por sessão antes do primeiro
strobo. Slider de rate é cap MAX_SAFE_HZ (3.0).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QMessageBox, QPushButton,
    QSlider, QVBoxLayout, QWidget,
)

from core.bus import MidiEvent
from gui.apc_grid import APCGrid
from gui.midi_bridge import MidiBridge
from outputs.fx_bridge import MAX_SAFE_HZ

LOG_LIMIT = 200


class LivePanel(QWidget):
    def __init__(self, bridge: MidiBridge, listener, fx_signals) -> None:
        super().__init__()
        self.fx_signals = fx_signals
        self._warned = False
        self._strobe_on = False

        layout = QVBoxLayout(self)

        # --- status MIDI ---
        status = QHBoxLayout()
        ports = listener.list_ports()
        connected = bool(listener._find_port()) if listener._mido else False
        dot = "🟢" if connected else "🔴"
        text = f"{dot} MIDI: {ports[0] if ports else '(nenhuma porta)'} {'(simulando)' if not connected else ''}"
        status.addWidget(QLabel(text))
        status.addStretch()
        layout.addLayout(status)

        # --- grid visual (espelho dos eventos) ---
        self.grid = APCGrid()
        layout.addWidget(self.grid, alignment=Qt.AlignHCenter)

        # --- log ---
        self.log = QListWidget()
        bridge.event.connect(self._on_event)
        layout.addWidget(QLabel("Log de eventos:"))
        layout.addWidget(self.log, stretch=1)

        # --- gatilhos manuais FX ---
        fx_row = QHBoxLayout()
        btn_flash = QPushButton("Flash"); btn_flash.clicked.connect(self._flash)
        self.btn_strobe = QPushButton("Strobo: OFF")
        self.btn_strobe.setCheckable(True)
        self.btn_strobe.toggled.connect(self._toggle_strobe)
        btn_blackout = QPushButton("Blackout"); btn_blackout.clicked.connect(self._blackout)
        self.rate = QSlider(Qt.Horizontal)
        self.rate.setRange(1, int(MAX_SAFE_HZ * 10))   # 0.1..3.0 em décimos
        self.rate.setValue(10)
        self.rate.valueChanged.connect(self._rate_changed)
        fx_row.addWidget(btn_flash)
        fx_row.addWidget(self.btn_strobe)
        fx_row.addWidget(btn_blackout)
        fx_row.addWidget(QLabel("Rate Hz:"))
        fx_row.addWidget(self.rate)
        layout.addLayout(fx_row)

    # ---- handlers ----------------------------------------------------------
    @Slot(object)
    def _on_event(self, ev: MidiEvent) -> None:
        line = f"{ev.kind:<14} number={ev.number:<3} value={ev.value}"
        self.log.addItem(line)
        while self.log.count() > LOG_LIMIT:
            self.log.takeItem(0)
        self.log.scrollToBottom()
        it = "cc" if ev.kind == "control_change" else "note"
        self.grid.highlight(it, ev.number)

    def _warn_once(self) -> bool:
        if self._warned:
            return True
        ans = QMessageBox.warning(
            self, "AVISO FOTOSSENSIBILIDADE",
            "Strobo pode desencadear convulsões em pessoas fotossensíveis.\n"
            f"Frequência limitada a {MAX_SAFE_HZ} Hz.\n\nConfirma habilitar?",
            QMessageBox.Ok | QMessageBox.Cancel,
        )
        if ans == QMessageBox.Ok:
            self._warned = True
            return True
        return False

    def _flash(self) -> None:
        self.fx_signals.flash.emit()

    def _blackout(self) -> None:
        self.fx_signals.blackout.emit()

    def _toggle_strobe(self, on: bool) -> None:
        if on and not self._warn_once():
            self.btn_strobe.setChecked(False)
            return
        self._strobe_on = on
        self.btn_strobe.setText(f"Strobo: {'ON' if on else 'OFF'}")
        self.fx_signals.strobe.emit(on)
        if on:
            self.fx_signals.rate.emit(self.rate.value() / 10.0)

    def _rate_changed(self, v: int) -> None:
        hz = v / 10.0
        self.fx_signals.rate.emit(hz)
