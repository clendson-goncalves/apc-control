# apc-control

Controlar uma **Akai APC mini** no macOS para: passar slides, disparar efeitos de
tela (strobo/flash), exibir overlays de IA e comandar qualquer software — com um
sistema de **perfis** em Markdown que mapeia a APC para qualquer aplicativo.

> Protótipo focado em **macOS (Apple Silicon)**. O código está estruturado para
> ser cross-platform depois (a divergência fica isolada nos backends de saída).

---

> ⚠️ **Aviso de fotossensibilidade**
> O efeito de strobo é limitado a **3,0 Hz** (`MAX_SAFE_HZ`). A GUI exibe um
> aviso antes de ativar o strobo pela primeira vez. Pessoas com epilepsia
> fotossensível devem ter cuidado ao usar qualquer efeito piscante.

---

## Arquitetura

```
APC (MIDI in)
    │
    ▼
MidiListener ──► EventBus ──► Mapper (perfil ativo) ──► Output Backends
    │                                                    ├── keyboard   (pynput, universal)
    │                                                    ├── applescript (osascript, macOS)
    │                                                    ├── fx ──► StrobeOverlay  ─┐
    │                                                    ├── ai ──► AiOverlay       │ overlays
    │                                                    └── shell                  │ independentes
    │                                                                               │ do software-alvo
    └── LED feedback ◄──────────────────────────────────────────────────────────────┘

GUI (PySide6)
    ├── LivePanel    — log de eventos ao vivo + controles de FX
    ├── BindingEditor — editar/aprender bindings e salvar no perfil
    ├── ApcGrid      — representação visual do grid 8×8 da APC
    └── MidiBridge   — ponte entre o EventBus e os sinais Qt
```

Conceitos centrais:
- **EventBus**: tudo que a APC gera vira um `MidiEvent` publicado no bus.
- **Perfil** (Markdown em `profiles/`): mapeia nota/CC → ação. Trocar de software = trocar de perfil.
- **Output backends** (`outputs/`): cada ação abstrata é executada por um backend registrado.
- **FX overlay** (`fx/strobe.py`): strobo/flash/blackout funcionam por cima de qualquer app.
- **AI overlay** (`gui/ai_overlay.py`): exibe texto gerado pela IA por cima de qualquer app,
  auto-dismiss em 12 s, Esc fecha imediatamente.

## Setup (macOS, M1)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Permissões a conceder em **Ajustes → Privacidade e Segurança**:
- **Acessibilidade** → para o backend `keyboard` (pynput) simular teclas.
- **Automação** → para o backend `applescript` controlar PowerPoint/Keynote.

## GUI vs --headless

```bash
# GUI (padrão) — janela PySide6 com log ao vivo, controles de FX e editor de bindings
python main.py

# Modo headless (CLI) — carrega o perfil e roda sem janela; Ctrl+C encerra
python main.py --headless profiles/powerpoint.md
```

No modo GUI, se não houver APC conectada, o app entra em **simulação**: publica
um conjunto de eventos pré-definidos automaticamente para que o pipeline completo
possa ser exercitado sem hardware. O mesmo vale para o modo headless.

## Perfis (formato Markdown)

Os perfis ficam em `profiles/` como arquivos `.md`. Cada perfil tem um cabeçalho
descritivo e uma tabela `## Bindings` com as colunas:
`Input`, `N` (número de nota ou CC), `Backend`, `Action` e `Args`.

Exemplo (`profiles/powerpoint.md`):

```markdown
# PowerPoint

Perfil de exemplo para navegação de slides.

## Bindings
| Input | N  | Backend     | Action          | Args                                        |
|-------|----|-------------|-----------------|---------------------------------------------|
| note  | 0  | keyboard    | key             | key=right                                   |
| note  | 1  | keyboard    | key             | key=left                                    |
| note  | 24 | fx          | strobe_toggle   |                                             |
| note  | 25 | fx          | flash           |                                             |
| cc    | 48 | fx          | strobe_rate     |                                             |
| note  | 56 | ai          | prompt          | prompt=Explique o slide atual em uma frase. |
```

A coluna `Args` usa o formato `chave=valor` separados por vírgula (ex.: `key=right, slide=1`).
Campos em branco significam sem argumentos. O parser está em `core/profiles.py`.

## Mapa da APC mini (referência)

- Grid 8×8: notes 0–63 (note_on/note_off).
- Faders: control_change, CC 48–56 (8 faders + master), valores 0–127.
- Botões redondos/laterais: notes 64–98 (varia por firmware — confirmar no device).
- LED feedback: enviar `note_on` de volta na mesma nota; velocity 0/1/3/5 = off/verde/vermelho/amarelo.
