# apcdeck

Controlar uma **Akai APC mini** no macOS para: passar slides, disparar efeitos de
tela (strobo/flash), e comandar IAs — com um sistema de **perfis** que permite
mapear a APC para qualquer software.

> Protótipo focado em **macOS (Apple Silicon)**. O código já está estruturado para
> ser cross-platform depois (a divergência fica isolada nos backends de saída).

## Arquitetura

```
APC (MIDI in) → MidiListener → EventBus → Mapper (perfil ativo) → Output Backends
                     ↑                                            ├── keyboard (pynput)   universal
                     └────────── LED feedback ───────────────────┤── applescript (osascript)
                                                                  ├── osc   (OBS/VJ)  [TODO]
                                                                  └── shell / ai      [TODO]
        + fx/  → overlay de strobo (efeito próprio, independente do alvo)
```

Conceitos centrais:
- **EventBus**: tudo que a APC gera vira um `MidiEvent` publicado no bus.
- **Profile** (YAML em `profiles/`): mapeia nota/CC → ação. Trocar de software = trocar de perfil.
- **Output backends** (`outputs/`): cada ação abstrata é executada por um backend.
- **FX overlay** (`fx/`): strobo/flash são efeitos internos, funcionam por cima de qualquer app.

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

## Estado atual (o que já funciona neste esqueleto)

- [x] Listener MIDI com `mido` (lista portas, conecta na APC, publica eventos)
- [x] EventBus simples (pub/sub)
- [x] Carregador de perfis YAML + perfil de exemplo (PowerPoint)
- [x] Backend `keyboard` (pynput) — stub funcional
- [x] Backend `applescript` (osascript) — stub funcional
- [x] Modo "dry-run": se não houver APC nem libs, simula eventos para você ver o fluxo
- [ ] LED feedback (estrutura pronta, envio real a implementar)
- [ ] FX overlay de strobo (PySide6) — esqueleto/TODO
- [ ] Backend OSC (OBS/VJ)
- [ ] Ação de IA real
- [ ] Auto-troca de perfil por app em foco (NSWorkspace)

## Handoff para o Claude Code

Próximos passos sugeridos, em ordem:
1. Implementar o **FX overlay** em `fx/strobe.py` com PySide6 (janela frameless,
   translucent, always-on-top; alternar opacidade a N Hz; fader controla frequência).
   ⚠️ Limitar strobo a ~3 Hz por segurança (fotossensibilidade) + aviso na UI.
2. Implementar **LED feedback** em `midi/leds.py` (a APC mini acende LEDs por note_on
   de volta na mesma nota; cores por velocity 0/1/3/5 = off/verde/vermelho/amarelo).
3. Conectar a **ação `ai`** a uma chamada real de API.
4. Adicionar backend **OSC** (`outputs/osc.py`) com `python-osc` para OBS/Resolume.
5. **Auto-perfil**: detectar app em foco via `NSWorkspace.frontmostApplication`
   e carregar o perfil correspondente.

Veja os `# TODO(claude-code):` espalhados pelo código.

## Mapa da APC mini (referência)

- Grid 8x8: notes 0–63 (note_on/note_off).
- Faders: control_change, CC 48–56 (8 faders + master), valores 0–127.
- Botões redondos/laterais: notes 64–98 (varia por firmware — confirmar no device).
