"""Réplica visual da APC mini mk1.

Layout fiel ao hardware:
  - 8x8 de pads retangulares cinza-claro (notes 0..63) — note 0 no canto
    inferior esquerdo, 63 no canto superior direito.
  - Coluna SCENE LAUNCH à direita do grid: 7 botões redondos (82..88) com
    rótulos impressos à esquerda (CLIP STOP / SOLO / REC ARM / MUTE /
    SELECT / SOFT KEYS) e um botão retangular STOP ALL CLIPS (89) no fim.
  - Linha entre pads e faders: 8 botões redondos (64..71) — 4 setas
    (▲▼◄►) e 4 controles (VOLUME / PAN / SEND / DEVICE) com rótulos
    abaixo. SHIFT (98) retangular no canto inferior direito.
  - 8 faders (CC48..55) com cap retangular flat + master separado por gap
    (CC56), com rótulo MASTER abaixo.
  - Case preto.

Tooltips trazem o número MIDI de cada controle.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QGridLayout, QLabel, QPushButton, QSizePolicy, QSlider, QWidget,
)

GRID_COLS = 8
GRID_ROWS = 8
FADER_CCS = list(range(48, 57))    # 48..55 + 56 (master)

TRACK_NOTES = list(range(64, 72))  # arrows + fader-ctrl
SCENE_NOTES = list(range(82, 90))  # 82..88 redondos + 89 retangular
SQUARE_NOTE = 89                   # STOP ALL CLIPS — retangular
SHIFT_NOTE = 98                    # SHIFT — retangular

SCENE_LABELS = {
    82: "CLIP STOP",
    83: "SOLO",
    84: "REC ARM",
    85: "MUTE",
    86: "SELECT",
    87: "",
    88: "",
}
TRACK_LABELS = ["▲", "▼", "◄", "►", "VOLUME", "PAN", "SEND", "DEVICE"]

# Sizing
PAD_W, PAD_H = 58, 36
ROUND_SIZE = 22
RECT_W, RECT_H = 46, 26
FADER_HEIGHT = 130

# Endereços — master/SHIFT vivem na mesma coluna vertical das scenes
SCENE_LABEL_COL = GRID_COLS          # col 8
SCENE_BTN_COL = GRID_COLS + 1        # col 9 — também recebe master/SHIFT

TRACK_ROW = GRID_ROWS                # row 8 (track btns + SHIFT)
TRACK_LABEL_ROW = GRID_ROWS + 1      # row 9
FADER_ROW = GRID_ROWS + 2            # row 10 (faders + master)
FADER_LABEL_ROW = GRID_ROWS + 3      # row 11 (CC labels + MASTER)

FADER_QSS = """
QSlider::groove:vertical {
    background: #0c0c0c;
    width: 5px;
    border-radius: 2px;
    border: 1px solid #1c1c1c;
}
QSlider::handle:vertical {
    background: #e0e0e0;
    border: 1px solid #555;
    height: 24px;
    width: 34px;
    margin: 0 -15px;
    border-radius: 3px;
}
"""

SMALL_LABEL = "font-size:7pt; color:#aaa; background: transparent;"
TINY_LABEL = "font-size:6pt; color:#888; background: transparent;"


class APCGrid(QWidget):
    clicked = Signal(str, int)   # ("note"|"cc", number)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("APCGrid")
        self.setStyleSheet("#APCGrid { background-color: #0a0a0a; }")
        # widget mantém o tamanho do device — parent cuida do alinhamento
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

        layout = QGridLayout(self)
        layout.setSpacing(3)
        layout.setContentsMargins(14, 14, 14, 14)

        self._buttons: dict[int, QPushButton] = {}       # pads 0..63
        self._aux_buttons: dict[int, QPushButton] = {}   # round/rect aux
        self._aux_shape: dict[int, str] = {}             # note -> "round"|"rect"
        self._faders: dict[int, QSlider] = {}

        # --- pads (note 0 no canto inferior esquerdo) ---
        for n in range(GRID_COLS * GRID_ROWS):
            row, col = divmod(n, GRID_COLS)
            btn = self._make_pad(n)
            layout.addWidget(btn, GRID_ROWS - 1 - row, col)
            self._buttons[n] = btn

        # --- scene column ---
        for i, note in enumerate(SCENE_NOTES):
            if note == SQUARE_NOTE:
                # STOP ALL CLIPS — retangular ocupa label_col + btn_col
                btn = self._make_rect(note, "STOP\nALL CLIPS")
                layout.addWidget(btn, i, SCENE_LABEL_COL, 1, 2, Qt.AlignCenter)
                self._aux_shape[note] = "rect"
            else:
                text = SCENE_LABELS.get(note, "")
                if text:
                    lbl = QLabel(text)
                    lbl.setStyleSheet(SMALL_LABEL)
                    lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    layout.addWidget(lbl, i, SCENE_LABEL_COL)
                btn = self._make_round(note)
                layout.addWidget(btn, i, SCENE_BTN_COL, Qt.AlignCenter)
                self._aux_shape[note] = "round"
            self._aux_buttons[note] = btn

        # --- track buttons + labels ---
        for i, note in enumerate(TRACK_NOTES):
            btn = self._make_round(note)
            layout.addWidget(btn, TRACK_ROW, i, Qt.AlignCenter)
            self._aux_buttons[note] = btn
            self._aux_shape[note] = "round"
            lbl = QLabel(TRACK_LABELS[i])
            lbl.setStyleSheet(SMALL_LABEL)
            lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(lbl, TRACK_LABEL_ROW, i)

        # --- SHIFT (note 98) — abaixo de STOP ALL CLIPS, span sobre label+btn col ---
        shift_btn = self._make_rect(SHIFT_NOTE, "SHIFT")
        layout.addWidget(shift_btn, TRACK_ROW, SCENE_LABEL_COL, 1, 2, Qt.AlignCenter)
        self._aux_buttons[SHIFT_NOTE] = shift_btn
        self._aux_shape[SHIFT_NOTE] = "rect"

        # --- faders 1..8 ---
        for i, cc in enumerate(FADER_CCS[:GRID_COLS]):
            slider = self._make_fader(cc)
            layout.addWidget(slider, FADER_ROW, i, Qt.AlignHCenter)
            self._faders[cc] = slider

        # --- master fader + label (abaixo de SHIFT, alinhado verticalmente) ---
        master_cc = FADER_CCS[-1]
        master_slider = self._make_fader(master_cc)
        layout.addWidget(
            master_slider, FADER_ROW, SCENE_LABEL_COL, 1, 2, Qt.AlignHCenter
        )
        self._faders[master_cc] = master_slider
        master_lbl = QLabel("MASTER")
        master_lbl.setStyleSheet(SMALL_LABEL)
        master_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(master_lbl, FADER_LABEL_ROW, SCENE_LABEL_COL, 1, 2)

    # ---- factories ----------------------------------------------------------
    def _make_pad(self, n: int) -> QPushButton:
        btn = QPushButton("")
        btn.setFixedSize(PAD_W, PAD_H)
        btn.setStyleSheet(self._style_pad(False))
        btn.setToolTip(f"note {n}")
        btn.clicked.connect(lambda _c=False, num=n: self.clicked.emit("note", num))
        return btn

    def _make_round(self, note: int) -> QPushButton:
        btn = QPushButton("")
        btn.setFixedSize(ROUND_SIZE, ROUND_SIZE)
        btn.setStyleSheet(self._style_round(False))
        btn.setToolTip(f"note {note}")
        btn.clicked.connect(lambda _c=False, num=note: self.clicked.emit("note", num))
        return btn

    def _make_rect(self, note: int, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(RECT_W, RECT_H)
        btn.setStyleSheet(self._style_rect(False))
        btn.setToolTip(f"note {note}")
        btn.clicked.connect(lambda _c=False, num=note: self.clicked.emit("note", num))
        return btn

    def _make_fader(self, cc: int) -> QSlider:
        s = QSlider(Qt.Vertical)
        s.setRange(0, 127)
        s.setFixedHeight(FADER_HEIGHT)
        s.setStyleSheet(FADER_QSS)
        s.setToolTip(f"CC{cc}")
        s.sliderPressed.connect(lambda c=cc: self.clicked.emit("cc", c))
        return s

    # ---- estilos -----------------------------------------------------------
    def _style_pad(self, lit: bool) -> str:
        bg = "#5cc97f" if lit else "#a0a8b0"   # LED on (verde) / off (cinza-claro)
        return (
            f"background:{bg}; border-radius:4px; border:1px solid #1a1a1a;"
        )

    def _style_round(self, lit: bool) -> str:
        bg = "#d24a3a" if lit else "#1f1f1f"
        return (
            f"background:{bg}; border-radius:{ROUND_SIZE // 2}px; "
            "border:1px solid #2c2c2c;"
        )

    def _style_rect(self, lit: bool) -> str:
        bg = "#d24a3a" if lit else "#1f1f1f"
        return (
            f"background:{bg}; color:#cccccc; font-size:7pt; font-weight:bold; "
            "border-radius:3px; border:1px solid #2c2c2c;"
        )

    # ---- highlight ---------------------------------------------------------
    def highlight(self, input_type: str, number: int) -> None:
        if input_type == "note":
            if number in self._buttons:
                btn = self._buttons[number]
                btn.setStyleSheet(self._style_pad(True))
                QTimer.singleShot(
                    200, lambda b=btn: b.setStyleSheet(self._style_pad(False))
                )
            elif number in self._aux_buttons:
                btn = self._aux_buttons[number]
                shape = self._aux_shape.get(number, "round")
                style_fn = self._style_rect if shape == "rect" else self._style_round
                btn.setStyleSheet(style_fn(True))
                QTimer.singleShot(
                    200, lambda b=btn, s=style_fn: b.setStyleSheet(s(False))
                )
        elif input_type == "cc" and number in self._faders:
            pass
