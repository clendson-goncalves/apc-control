"""Backend de IA: dispara um prompt e mostra/usa a resposta.

No protótipo apenas registra a intenção. A integração real (chamada de API)
fica como TODO para o Claude Code conectar.

Ações:
  prompt -> args: { prompt: "explique este slide", show: "overlay|stdout" }

TODO(claude-code):
  - chamar a API escolhida com args["prompt"]
  - opcional: capturar o texto do slide atual (via AppleScriptBackend) e injetar
  - exibir a resposta no overlay (fx/) ou via TTS
"""
from __future__ import annotations

from typing import Any

from outputs.base import Backend


class AiBackend(Backend):
    name = "ai"

    def execute(self, do: str, args: dict[str, Any], value: int = 0) -> None:
        if do == "prompt":
            prompt = args.get("prompt", "")
            print(f"[ai] (stub) prompt -> {prompt!r}")
            # TODO(claude-code): resposta = call_api(prompt); exibir/usar
        else:
            print(f"[ai] ação desconhecida: {do}")
