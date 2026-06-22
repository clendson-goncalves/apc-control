"""Portadores de sinais Qt para desacoplar backends (puros Python) da GUI.

Em modo --headless o atributo `.signals` do backend fica em None e os
backends caem no fluxo de print/dry-run.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class FxSignals(QObject):
    strobe = Signal(bool)
    rate = Signal(float)
    flash = Signal()
    blackout = Signal()


class AiSignals(QObject):
    token = Signal(str)
    done = Signal()
    error = Signal(str)
    dismiss = Signal()
