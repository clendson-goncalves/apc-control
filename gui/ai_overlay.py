"""Overlay de texto da IA: aparece sobre qualquer app, recebe tokens em streaming.

Auto-dismiss 12s após o stream encerrar; reset a cada novo token (mantém visível
durante a geração). Esc fecha; clicar também fecha (não tem
WA_TransparentForMouseEvents).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from gui._macos import raise_above_menu_bar

AUTO_DISMISS_MS = 12_000


class AiOverlay(QWidget):
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

        scr = QApplication.primaryScreen().geometry()
        self.setGeometry(scr)

        self._label = QLabel("", self)
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet(
            "color: white; background: rgba(0, 0, 0, 200);"
            "padding: 32px; border-radius: 16px;"
        )
        font = QFont()
        font.setPointSize(36)
        font.setBold(True)
        self._label.setFont(font)

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(self._label)
        layout.addStretch()
        layout.setContentsMargins(120, 80, 120, 120)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    @Slot(str)
    def append_token(self, t: str) -> None:
        if not self.isVisible():
            self._label.setText("")
            self.show()
            raise_above_menu_bar(self)
        self._label.setText(self._label.text() + t)
        self._timer.stop()   # cancela auto-dismiss enquanto recebe

    @Slot()
    def on_done(self) -> None:
        self._timer.start(AUTO_DISMISS_MS)

    @Slot(str)
    def on_error(self, msg: str) -> None:
        self._label.setText(f"[erro IA] {msg}")
        if not self.isVisible():
            self.show()
            raise_above_menu_bar(self)
        self._timer.start(8000)

    @Slot()
    def dismiss(self) -> None:
        self._timer.stop()
        self.hide()

    def mousePressEvent(self, _ev) -> None:
        self.dismiss()

    def keyPressEvent(self, ev) -> None:
        if ev.key() == Qt.Key_Escape:
            self.dismiss()
