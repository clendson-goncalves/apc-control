"""Aba editor de bindings.

Tabela à esquerda, APC visual + formulário à direita. Botão Learn captura
o próximo evento MIDI do bridge.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.bus import MidiEvent
from core.profiles import Binding, Profile, save_profile
from gui.apc_grid import APCGrid
from gui.midi_bridge import MidiBridge

BACKENDS = ["keyboard", "applescript", "fx", "ai"]
ACTIONS = {
    "keyboard": ["key", "combo", "text"],
    "applescript": ["ppt_next", "ppt_prev", "ppt_goto", "keynote_next", "keynote_prev", "run"],
    "fx": ["strobe_toggle", "strobe_rate", "flash", "blackout_toggle"],
    "ai": ["prompt", "dismiss"],
}


class BindingEditor(QWidget):
    profile_changed = Signal()

    def __init__(self, profile: Profile, profile_path: Path, bridge: MidiBridge) -> None:
        super().__init__()
        self.profile = profile
        self.path = profile_path
        self._learning = False
        bridge.event.connect(self._on_midi)

        splitter = QSplitter(Qt.Horizontal)

        # --- esquerda: tabela ---
        left = QWidget(); left_l = QVBoxLayout(left)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Input", "N", "Backend", "Action", "Args"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._on_select)
        left_l.addWidget(self.table)
        btn_del = QPushButton("Remover selecionado")
        btn_del.clicked.connect(self._delete_selected)
        left_l.addWidget(btn_del)
        splitter.addWidget(left)

        # --- direita: APC + form ---
        right = QWidget(); right_l = QVBoxLayout(right)
        self.grid = APCGrid()
        self.grid.clicked.connect(self._on_grid_click)
        right_l.addWidget(self.grid)

        form = QHBoxLayout()
        self.input_type = QComboBox(); self.input_type.addItems(["note", "cc"])
        self.number = QSpinBox(); self.number.setRange(0, 127)
        self.backend = QComboBox(); self.backend.addItems(BACKENDS)
        self.backend.currentTextChanged.connect(self._on_backend_change)
        self.action = QComboBox(); self.action.addItems(ACTIONS["keyboard"])
        self.args = QLineEdit(); self.args.setPlaceholderText("k=v, k2=v2")
        form.addWidget(QLabel("tipo:")); form.addWidget(self.input_type)
        form.addWidget(QLabel("n:")); form.addWidget(self.number)
        form.addWidget(QLabel("backend:")); form.addWidget(self.backend)
        form.addWidget(QLabel("ação:")); form.addWidget(self.action)
        right_l.addLayout(form)
        right_l.addWidget(QLabel("args:"))
        right_l.addWidget(self.args)

        btn_row = QHBoxLayout()
        self.learn = QCheckBox("Learn (capturar próximo MIDI)")
        btn_add = QPushButton("Adicionar / Atualizar")
        btn_add.clicked.connect(self._add_or_update)
        btn_save = QPushButton("Salvar perfil (.md)")
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(self.learn); btn_row.addStretch()
        btn_row.addWidget(btn_add); btn_row.addWidget(btn_save)
        right_l.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1); splitter.setStretchFactor(1, 2)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        self._refill_table()

    # ---- pública ------------------------------------------------------------
    def set_profile(self, profile: Profile, path: Path) -> None:
        self.profile = profile
        self.path = path
        self._refill_table()

    # ---- internos -----------------------------------------------------------
    def _refill_table(self) -> None:
        self.table.setRowCount(len(self.profile.bindings))
        for i, b in enumerate(self.profile.bindings):
            args_str = ", ".join(f"{k}={v}" for k, v in b.args.items())
            for col, val in enumerate([b.input_type, str(b.number), b.backend, b.do, args_str]):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, col, item)

    def _on_select(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        b = self.profile.bindings[rows[0].row()]
        self.input_type.setCurrentText(b.input_type)
        self.number.setValue(b.number)
        self.backend.setCurrentText(b.backend)
        self._refresh_actions(b.backend, b.do)
        self.args.setText(", ".join(f"{k}={v}" for k, v in b.args.items()))

    def _on_backend_change(self, name: str) -> None:
        self._refresh_actions(name, None)

    def _refresh_actions(self, backend: str, current: str | None) -> None:
        self.action.clear()
        self.action.addItems(ACTIONS.get(backend, []))
        if current:
            self.action.setCurrentText(current)

    def _on_grid_click(self, input_type: str, number: int) -> None:
        self.input_type.setCurrentText(input_type)
        self.number.setValue(number)

    @Slot(object)
    def _on_midi(self, ev: MidiEvent) -> None:
        if not self.learn.isChecked():
            return
        it = "cc" if ev.kind == "control_change" else "note"
        self.input_type.setCurrentText(it)
        self.number.setValue(ev.number)
        self.learn.setChecked(False)

    def _parse_args(self, s: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for pair in s.split(","):
            pair = pair.strip()
            if "=" not in pair:
                continue
            k, v = pair.split("=", 1)
            out[k.strip()] = v.strip()
        return out

    def _add_or_update(self) -> None:
        it = self.input_type.currentText()
        n = self.number.value()
        new = Binding(it, n, self.backend.currentText(),
                      self.action.currentText(), self._parse_args(self.args.text()))
        # se já existe binding com (it, n), substitui
        for i, b in enumerate(self.profile.bindings):
            if b.input_type == it and b.number == n:
                self.profile.bindings[i] = new
                self._refill_table()
                return
        self.profile.bindings.append(new)
        self._refill_table()

    def _delete_selected(self) -> None:
        rows = sorted({r.row() for r in self.table.selectionModel().selectedRows()},
                      reverse=True)
        for r in rows:
            del self.profile.bindings[r]
        self._refill_table()

    def _save(self) -> None:
        try:
            save_profile(self.profile, self.path)
            self.profile_changed.emit()
            QMessageBox.information(self, "Salvo", f"Perfil salvo em {self.path}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
