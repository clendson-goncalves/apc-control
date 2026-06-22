"""Backend de IA: chama a API Anthropic e streama tokens para o overlay.

Modelo padrão: claude-haiku-4-5-20251001 (rápido, bom para resposta ao vivo).
Sem ANTHROPIC_API_KEY ou sem SDK instalado, cai em modo dry — emite
tokens fake para a GUI ainda funcionar.

Ações:
  prompt   -> args: { prompt: "texto" }     dispara stream em thread daemon
  dismiss  -> esconde o overlay
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any

from outputs.base import Backend

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _try_import_anthropic():
    try:
        import anthropic  # type: ignore
        return anthropic
    except Exception:
        return None


class AiBackend(Backend):
    name = "ai"

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.signals = None         # GUI injeta AiSignals; None = print
        self.led = None             # LedController injetado; None = sem LED
        self.model = model
        self._anthropic = _try_import_anthropic()
        self._client = None
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if self._anthropic and api_key:
            try:
                self._client = self._anthropic.Anthropic(api_key=api_key)
            except Exception as exc:
                print(f"[ai] cliente Anthropic falhou: {exc}")

    def execute(
        self, do: str, args: dict[str, Any], value: int = 0, note: int | None = None
    ) -> bool | None:
        if do == "prompt":
            prompt = args.get("prompt", "").strip()
            if not prompt:
                print("[ai] prompt vazio, ignorado")
                return None
            threading.Thread(
                target=self._run, args=(prompt,), kwargs={"note": note}, daemon=True
            ).start()
        elif do == "dismiss":
            if note is not None and self.led:
                self.led.clear(note)
            if self.signals:
                self.signals.dismiss.emit()
            else:
                print("[ai/dry] dismiss")
        else:
            print(f"[ai] ação desconhecida: {do}")
        return None

    def _run(self, prompt: str, note: int | None = None) -> None:
        """Acende o LED piscando, streama, e limpa o LED ao terminar."""
        if note is not None and self.led:
            self.led.blink(note)
        try:
            if self._client is None:
                self._stream_dry(prompt)
            else:
                self._stream(prompt)
        finally:
            if note is not None and self.led:
                self.led.clear(note)

    def _stream(self, prompt: str) -> None:
        try:
            with self._client.messages.stream(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for text in stream.text_stream:
                    self._emit_token(text)
            self._emit_done()
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            if self.signals:
                self.signals.error.emit(msg)
            else:
                print(f"[ai] erro: {msg}")

    def _stream_dry(self, prompt: str) -> None:
        fake = f"[ai/dry sem API key] resposta simulada para: {prompt}"
        for chunk in fake.split(" "):
            self._emit_token(chunk + " ")
            time.sleep(0.04)
        self._emit_done()

    def _emit_token(self, text: str) -> None:
        if self.signals:
            self.signals.token.emit(text)
        else:
            print(text, end="", flush=True)

    def _emit_done(self) -> None:
        if self.signals:
            self.signals.done.emit()
        else:
            print()   # quebra de linha
