"""CSS generation and atomic write tests: pure logic, runs on any OS."""

from core.utils.wallpaper_palette import build_css, write_palette_css

COLORS = [(20, 30, 40), (200, 100, 50), (10, 200, 120)]


def _variable_values(css: str, variable: str) -> list[str]:
    prefix = f"    {variable}: "
    return [line.removeprefix(prefix).rstrip(";") for line in css.splitlines() if line.startswith(prefix)]


def test_all_three_colors_present():
    css = build_css(COLORS, auto_apply=False)
    for position in (1, 2, 3):
        assert _variable_values(css, f"--wallpaper-color-{position}") == [
            COLORS[position - 1] and "#{:02x}{:02x}{:02x}".format(*COLORS[position - 1])
        ]


def test_rgb_variants_present():
    css = build_css(COLORS, auto_apply=False)
    assert _variable_values(css, "--wallpaper-color-1-rgb") == ["20, 30, 40"]


def test_accent_and_text_variables_present():
    css = build_css(COLORS, auto_apply=False)
    assert len(_variable_values(css, "--wallpaper-accent")) == 1
    assert _variable_values(css, "--wallpaper-text")[0] in ("#ffffff", "#111111")


def test_auto_apply_adds_bar_block():
    css = build_css(COLORS, auto_apply=True)
    assert ".yasb-bar {" in css
    assert f"background-color: #{COLORS[0][0]:02x}{COLORS[0][1]:02x}{COLORS[0][2]:02x};" in css


def test_no_auto_apply_omits_bar_block():
    css = build_css(COLORS, auto_apply=False)
    assert ".yasb-bar" not in css


def test_build_css_rejects_empty_palette():
    try:
        build_css([], auto_apply=False)
    except ValueError:
        pass
    else:
        raise AssertionError("build_css([]) should raise ValueError")


def test_write_palette_css_roundtrip(tmp_path):
    target = tmp_path / "out.css"
    assert write_palette_css(str(target), "hello\n") is True
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_write_palette_css_replaces_previous_content(tmp_path):
    target = tmp_path / "out.css"
    write_palette_css(str(target), "old content that is quite long\n")
    write_palette_css(str(target), "new\n")
    assert target.read_text(encoding="utf-8") == "new\n"


def test_write_palette_css_leaves_no_temp_file(tmp_path):
    target = tmp_path / "out.css"
    write_palette_css(str(target), "content\n")
    assert not (tmp_path / "out.css.tmp").exists()


def test_write_palette_css_bad_path_returns_false(tmp_path):
    # A directory in the place of the temp file forces the atomic replace to fail.
    (tmp_path / "out.css.tmp").mkdir()
    target = tmp_path / "out.css" / "nested"
    assert write_palette_css(str(target), "content\n") is False
