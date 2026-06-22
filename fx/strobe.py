"""Overlay de strobo/flash (PySide6) — ESQUELETO.

A ideia: uma janela frameless, translúcida, always-on-top, em fullscreen,
que o app desenha por cima de tudo. Alternar a opacidade/cor a N Hz cria o
strobo; um pulso curto cria o flash; opacidade 1.0 preta cria blackout.

⚠️ SEGURANÇA: strobo acima de ~3 flashes/segundo pode desencadear convulsões
fotossensíveis. Manter o cap (MAX_SAFE_HZ) e exibir aviso à plateia antes de usar.

Este arquivo está como TODO para o Claude Code implementar. Esboço da API:

    overlay = StrobeOverlay()
    overlay.set_rate(2.0)      # Hz
    overlay.set_strobe(True)   # liga
    overlay.flash()            # pulso único
    overlay.toggle_blackout()

Notas macOS:
  - usar Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
  - setAttribute(Qt.WA_TranslucentBackground)
  - para cobrir fullscreen real/Spaces pode ser necessário ajustar o nível
    da janela via pyobjc (NSWindow level acima do menu bar).
  - o piscar deve usar QTimer no thread da GUI; nunca time.sleep no loop.
"""

MAX_SAFE_HZ = 3.0


class StrobeOverlay:  # pragma: no cover - esqueleto
    def __init__(self) -> None:
        raise NotImplementedError(
            "TODO(claude-code): implementar com PySide6. Ver docstring deste arquivo."
        )
