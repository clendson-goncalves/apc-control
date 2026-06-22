"""Janela principal: combo de perfis + tabs Live / Editor."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget,
)

from core.mapper import Mapper
from core.profiles import load_profile
from gui.binding_editor import BindingEditor
from gui.live_panel import LivePanel
from gui.midi_bridge import MidiBridge

PROFILES_DIR = Path("profiles")


class MainWindow(QMainWindow):
    def __init__(self, bridge: MidiBridge, mapper: Mapper, listener,
                 fx_signals, ai_backend, profile_path: Path) -> None:
        super().__init__()
        self.setWindowTitle("apc-control")
        self.resize(1100, 720)
        self.mapper = mapper
        self.path = profile_path

        central = QWidget(); root = QVBoxLayout(central)

        # combo de perfis
        head = QHBoxLayout()
        head.addWidget(QLabel("Perfil:"))
        self.combo = QComboBox()
        for p in sorted(PROFILES_DIR.glob("*.md")):
            self.combo.addItem(p.name, str(p))
        idx = self.combo.findData(str(profile_path))
        if idx >= 0:
            self.combo.setCurrentIndex(idx)
        self.combo.currentIndexChanged.connect(self._switch_profile)
        head.addWidget(self.combo); head.addStretch()
        root.addLayout(head)

        # tabs
        tabs = QTabWidget()
        self.live = LivePanel(bridge, listener, fx_signals, ai_backend)
        self.editor = BindingEditor(mapper.profile, profile_path, bridge)
        self.editor.profile_changed.connect(self._reload_current)
        tabs.addTab(self.live, "Ao vivo")
        tabs.addTab(self.editor, "Editor")
        root.addWidget(tabs)

        self.setCentralWidget(central)

    def _switch_profile(self, idx: int) -> None:
        path = Path(self.combo.itemData(idx))
        profile = load_profile(path)
        self.mapper.set_profile(profile)
        self.path = path
        self.editor.set_profile(profile, path)

    def _reload_current(self) -> None:
        profile = load_profile(self.path)
        self.mapper.set_profile(profile)
