"""Backend AppleScript (macOS): controle profundo de apps scriptáveis.

Permite agir num app mesmo sem foco e ir para slide específico.
Roda osascript via subprocess. Em sistemas não-macOS, cai em dry-run.

Ações:
  run        -> args: { script: "<applescript cru>" }
  ppt_goto   -> args: { slide: 5 }       pula para slide N no PowerPoint
  ppt_next / ppt_prev                     navega no PowerPoint
  keynote_next / keynote_prev             navega no Keynote

TODO(claude-code): adicionar leitura de estado (slide atual, total de slides)
para feedback nos LEDs.
"""
from __future__ import annotations

import platform
import subprocess
from typing import Any

from outputs.base import Backend

IS_MAC = platform.system() == "Darwin"

# Snippets nomeados. ppt_goto usa formatação com o número do slide.
SCRIPTS = {
    "ppt_next": 'tell application "Microsoft PowerPoint" to go to next slide of slide show view of slide show window 1',
    "ppt_prev": 'tell application "Microsoft PowerPoint" to go to previous slide of slide show view of slide show window 1',
    "ppt_goto": 'tell application "Microsoft PowerPoint" to go to slide number {slide} of slide show view of slide show window 1',
    "keynote_next": 'tell application "Keynote" to show next',
    "keynote_prev": 'tell application "Keynote" to show previous',
}


class AppleScriptBackend(Backend):
    name = "applescript"

    def _osascript(self, script: str) -> None:
        if not IS_MAC:
            print(f"[applescript/dry] {script}")
            return
        try:
            subprocess.run(["osascript", "-e", script], check=True,
                           capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            print(f"[applescript] erro: {exc.stderr.strip()}")

    def execute(
        self, do: str, args: dict[str, Any], value: int = 0, note: int | None = None
    ) -> bool | None:
        if do == "run":
            self._osascript(args.get("script", ""))
            return
        template = SCRIPTS.get(do)
        if template is None:
            print(f"[applescript] ação desconhecida: {do}")
            return
        # coerção: 'slide' chega como string vindo do perfil .md
        fmt_args = dict(args)
        if "slide" in fmt_args:
            try:
                fmt_args["slide"] = int(fmt_args["slide"])
            except (TypeError, ValueError):
                print(f"[applescript] slide inválido: {fmt_args['slide']!r}")
                return
        self._osascript(template.format(**fmt_args))
