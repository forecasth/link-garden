from pathlib import Path

from link_garden.web.theme import compile_theme


def test_theme_compiler_outputs_css_variables_and_components(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    theme_file = repo_root / "ui" / "theme.yaml"
    output_css = tmp_path / "theme.css"

    compile_theme(theme_file, output_css)
    css = output_css.read_text(encoding="utf-8")

    assert ":root {" in css
    assert "--color-bg:" in css
    assert "--color-accent:" in css
    assert ".card {" in css
    assert ".btn {" in css
    assert ".input {" in css
    assert "var(--color-border)" in css
