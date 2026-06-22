# PowerPoint

Perfil de exemplo. Navegação por teclado (universal) + slides diretos via
AppleScript + efeitos próprios. Ajuste os 'N' às notas reais da sua APC mini
(use o log do listener para descobri-las).

## Bindings
| Input | N  | Backend     | Action          | Args                                        |
|-------|----|-------------|-----------------|---------------------------------------------|
| note  | 0  | keyboard    | key             | key=right                                   |
| note  | 1  | keyboard    | key             | key=left                                    |
| note  | 8  | keyboard    | key             | key=b                                       |
| note  | 16 | applescript | ppt_goto        | slide=1                                     |
| note  | 17 | applescript | ppt_goto        | slide=10                                    |
| note  | 24 | fx          | strobe_toggle   |                                             |
| note  | 25 | fx          | flash           |                                             |
| note  | 26 | fx          | blackout_toggle |                                             |
| cc    | 48 | keyboard    | key             |                                             |
