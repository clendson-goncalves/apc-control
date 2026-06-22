"""Eleva uma QWindow acima do menu bar e a torna visível em todos os Spaces.

Necessário para overlays cobrirem PowerPoint/Keynote em fullscreen.
Sem pyobjc instalado ou fora do macOS, vira no-op.
"""
from __future__ import annotations

import platform


def raise_above_menu_bar(widget) -> None:
    if platform.system() != "Darwin":
        return
    try:
        import objc  # type: ignore
        from AppKit import (  # type: ignore
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorStationary,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
        )
        # NSScreenSaverWindowLevel = 1000 — acima do menu bar (24) e dock
        NSScreenSaverWindowLevel = 1000
    except Exception as exc:
        print(f"[macos] pyobjc indisponível: {exc}")
        return

    try:
        view_ptr = int(widget.winId())
        view = objc.objc_object(c_void_p=view_ptr)
        win = view.window()
        if win is None:
            return
        win.setLevel_(NSScreenSaverWindowLevel)
        win.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
    except Exception as exc:
        print(f"[macos] falha ao elevar janela: {exc}")
