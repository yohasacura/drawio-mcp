"""Tests for the style builder and presets."""

from drawio_mcp.styles import (
    ColorTheme,
    EdgeStylePreset,
    StyleBuilder,
    Themes,
    VertexStyle,
)


def test_style_builder_basic() -> None:
    s = StyleBuilder().fill_color("#ff0000").stroke_color("#000000").html().build()
    assert "fillColor=#ff0000" in s
    assert "strokeColor=#000000" in s
    assert "html=1" in s
    assert s.endswith(";")


def test_style_builder_with_base() -> None:
    s = StyleBuilder("ellipse;whiteSpace=wrap;html=1;").fill_color("#dae8fc").build()
    assert s.startswith("ellipse;")
    assert "fillColor=#dae8fc" in s


def test_style_builder_font_style() -> None:
    s = StyleBuilder().font_style(bold=True, italic=True).build()
    assert "fontStyle=3" in s  # 1 + 2


def test_style_builder_edge() -> None:
    s = (
        StyleBuilder()
        .edge_style("orthogonalEdgeStyle")
        .end_arrow("classic")
        .curved(True)
        .build()
    )
    assert "edgeStyle=orthogonalEdgeStyle" in s
    assert "endArrow=classic" in s
    assert "curved=1" in s


def test_theme_apply() -> None:
    sb = StyleBuilder("rounded=1;whiteSpace=wrap;html=1;")
    Themes.BLUE.apply(sb)
    result = sb.build()
    assert "fillColor=#dae8fc" in result
    assert "strokeColor=#6c8ebf" in result


def test_vertex_presets_are_strings() -> None:
    assert isinstance(VertexStyle.RECTANGLE, str)
    assert isinstance(VertexStyle.ELLIPSE, str)
    assert isinstance(VertexStyle.DIAMOND, str)
    assert isinstance(VertexStyle.CYLINDER, str)


def test_edge_presets_are_strings() -> None:
    assert isinstance(EdgeStylePreset.DEFAULT, str)
    assert isinstance(EdgeStylePreset.ORTHOGONAL, str)
    assert isinstance(EdgeStylePreset.UML_INHERITANCE, str)
    assert isinstance(EdgeStylePreset.ER_ONE_TO_MANY, str)


def test_all_themes_have_required_fields() -> None:
    for name in dir(Themes):
        if name.startswith("_"):
            continue
        val = getattr(Themes, name)
        if isinstance(val, ColorTheme):
            assert val.fill
            assert val.stroke
            assert val.font
