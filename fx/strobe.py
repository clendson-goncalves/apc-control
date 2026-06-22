"""Overlay de strobo/flash/blackout (PySide6)

Janela frameless, translúcida, always-on-top, fullscreen, sem foco.
QTimer alterna pintura branca/transparente a N Hz (cap MAX_SAFE_HZ).

⚠️ FOTOSSENSIBILIDADE: NÃO subir MAX_SAFE_HZ sem aviso à plateia na UI.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QWidget

from gui._macos import raise_above_menu_bar
from outputs.fx_bridge import MAX_SAFE_HZ


class StrobeOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        scr = QApplication.primaryScreen().geometry()
        self.setGeometry(scr)

        self._strobe_on = False
        self._strobe_white = False
        self._blackout = False
        self._flash_on = False
        self._hz = 1.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._end_flash)

        # eleva acima do menu bar quando a janela for materializada
        self.show()
        raise_above_menu_bar(self)
        self.hide()

    # ---- slots --------------------------------------------------------------
    @Slot(bool)
    def set_strobe(self, on: bool) -> None:
        self._strobe_on = on
        if on:
            self._start_strobe()
        else:
            self._timer.stop()
            self._strobe_white = False
        self._refresh()

    @Slot(float)
    def set_rate(self, hz: float) -> None:
        self._hz = max(0.1, min(hz, MAX_SAFE_HZ))
        if self._strobe_on:
            self._start_strobe()

    @Slot()
    def flash(self) -> None:
        self._flash_on = True
        self._refresh()
        self._flash_timer.start(100)   # 100 ms

    @Slot()
    def toggle_blackout(self) -> None:
        self._blackout = not self._blackout
        self._refresh()

    # ---- internos -----------------------------------------------------------
    def _start_strobe(self) -> None:
        # meio-período em ms: para `hz` ciclos por segundo, alterna a 2*hz toggles/s
        interval = max(10, int(1000 / (2 * self._hz)))
        self._timer.start(interval)

    def _tick(self) -> None:
        self._strobe_white = not self._strobe_white
        self.update()

    def _end_flash(self) -> None:
        self._flash_on = False
        self.update()
        self._refresh()

    def _refresh(self) -> None:
        any_active = self._strobe_on or self._blackout or self._flash_on
        if any_active and not self.isVisible():
            self.show()
            raise_above_menu_bar(self)
        elif not any_active and self.isVisible():
            self.hide()
        else:
            self.update()

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        if self._blackout:
            p.fillRect(self.rect(), QColor(0, 0, 0, 255))
            return
        if self._flash_on or (self._strobe_on and self._strobe_white):
            p.fillRect(self.rect(), QColor(255, 255, 255, 255))
            return
        # else: transparente — nada desenhado
