"""Testes do parser/serializer de perfis Markdown."""
from core.profiles import (
    Binding, Profile, parse_markdown, render_markdown, load_profile, save_profile,
)

SAMPLE_MD = """# PowerPoint

Perfil de exemplo.

## Bindings
| Input | N  | Backend  | Action | Args      |
|-------|----|----------|--------|-----------|
| note  | 0  | keyboard | key    | key=right |
| cc    | 48 | fx       | strobe_rate |      |
| note  | 56 | ai       | prompt | prompt=Resuma o slide |
"""


def test_parse_extracts_name_and_description():
    p = parse_markdown(SAMPLE_MD)
    assert p.name == "PowerPoint"
    assert "Perfil de exemplo." in p.description


def test_parse_extracts_bindings():
    p = parse_markdown(SAMPLE_MD)
    assert len(p.bindings) == 3
    assert p.bindings[0] == Binding("note", 0, "keyboard", "key", {"key": "right"})
    assert p.bindings[1] == Binding("cc", 48, "fx", "strobe_rate", {})
    assert p.bindings[2].args == {"prompt": "Resuma o slide"}


def test_args_with_multiple_pairs():
    md = SAMPLE_MD + "| note  | 1  | keyboard | combo  | keys=cmd+shift+f, hold=true |\n"
    p = parse_markdown(md)
    assert p.bindings[-1].args == {"keys": "cmd+shift+f", "hold": "true"}


def test_round_trip_preserves_bindings():
    p1 = parse_markdown(SAMPLE_MD)
    out = render_markdown(p1)
    p2 = parse_markdown(out)
    assert p1.name == p2.name
    assert p1.bindings == p2.bindings


def test_load_and_save(tmp_path):
    path = tmp_path / "x.md"
    path.write_text(SAMPLE_MD, encoding="utf-8")
    p = load_profile(path)
    out = tmp_path / "y.md"
    save_profile(p, out)
    p2 = load_profile(out)
    assert p.bindings == p2.bindings


def test_find_returns_binding_or_none():
    p = parse_markdown(SAMPLE_MD)
    assert p.find("note", 0).backend == "keyboard"
    assert p.find("cc", 48).do == "strobe_rate"
    assert p.find("note", 99) is None


def test_empty_args_renders_empty_column():
    p = Profile("X", "", [Binding("note", 0, "fx", "flash", {})])
    out = render_markdown(p)
    # ultima coluna vazia, mas a tabela continua valida
    assert "| note" in out
    p2 = parse_markdown(out)
    assert p2.bindings[0].args == {}
