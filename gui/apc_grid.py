"""Widget 8x8 da APC mini + 9 faders. Cliques emitem (input_type, number).

Usado: (a) no editor para escolher qual entrada bindar; (b) no painel ao vivo
para piscar conforme eventos MIDI entram.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

GRID_COLS = 8
GRID_ROWS = 8
FADER_CCS = list(range(48, 57))   # 8 faders + master (48..56)


class APCGrid(QWidget):
    clicked = Signal(str, int)   # ("note"|"cc", number)

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)

        # grid 8x8
        grid_box = QWidget()
        grid = QGridLayout(grid_box)
        grid.setSpacing(2)
        self._buttons: dict[int, QPushButton] = {}
        for n in range(GRID_COLS * GRID_ROWS):
            row, col = divmod(n, GRID_COLS)
            btn = QPushButton(str(n))
            btn.setFixedSize(42, 42)
            btn.setStyleSheet(self._style_for(False))
            btn.clicked.connect(lambda _checked=False, num=n: self.clicked.emit("note", num))
            grid.addWidget(btn, GRID_ROWS - 1 - row, col)   # linha 0 embaixo
            self._buttons[n] = btn
        outer.addWidget(grid_box)

        # faders
        faders_box = QWidget()
        fbox = QHBoxLayout(faders_box)
        self._faders: dict[int, QSlider] = {}
        for cc in FADER_CCS:
            col = QVBoxLayout()
            slider = QSlider(Qt.Vertical)
            slider.setRange(0, 127)
            slider.setFixedHeight(120)
            slider.sliderPressed.connect(lambda c=cc: self.clicked.emit("cc", c))
            col.addWidget(slider, alignment=Qt.AlignHCenter)
            col.addWidget(QLabel(f"CC{cc}"), alignment=Qt.AlignHCenter)
            fbox.addLayout(col)
            self._faders[cc] = slider
        outer.addWidget(faders_box)

    def _style_for(self, lit: bool) -> str:
        bg = "#3aa757" if lit else "#222"
        return f"background:{bg}; color:white; font-size:10pt; border-radius:6px;"

    def highlight(self, input_type: str, number: int) -> None:
        if input_type == "note" and number in self._buttons:
            btn = self._buttons[number]
            btn.setStyleSheet(self._style_for(True))
            QTimer.singleShot(200, lambda: btn.setStyleSheet(self._style_for(False)))
        elif input_type == "cc" and number in self._faders:
            # nada para faders por ora; só o widget já reflete movimento
            pass
