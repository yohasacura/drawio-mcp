"""Tests for input validation in the MCP server tools."""

import json

import pytest

from drawio_mcp.server import (
    _diagrams,
    diagram,
    draw,
    inspect,
    layout,
    style,
)
from drawio_mcp.validation import (
    ValidationError,
    validate_action,
    validate_adjacency,
    validate_alignment,
    validate_color,
    validate_columns,
    validate_connection_dict,
    validate_dag_edge_dict,
    validate_direction,
    validate_edge_dict,
    validate_extra_dict,
    validate_font_size,
    validate_grid_size,
    validate_int,
    validate_list,
    validate_node_styles,
    validate_non_empty_string,
    validate_non_negative_number,
    validate_number,
    validate_opacity,
    validate_page_format,
    validate_page_index,
    validate_positive_number,
    validate_spacing,
    validate_update_dict,
    validate_vertex_dict,
    _DIAGRAM_ACTIONS,
    _DRAW_ACTIONS,
)


def setup_function() -> None:
    """Clear diagrams between tests."""
    _diagrams.clear()


# ===================================================================
# Unit tests for primitive validators
# ===================================================================


class TestValidateNonEmptyString:
    def test_valid(self) -> None:
        assert validate_non_empty_string("hello", "f") == "hello"

    def test_strips_whitespace(self) -> None:
        assert validate_non_empty_string("  hi  ", "f") == "hi"

    def test_empty_string(self) -> None:
        with pytest.raises(ValidationError, match="non-empty"):
            validate_non_empty_string("", "field")

    def test_whitespace_only(self) -> None:
        with pytest.raises(ValidationError, match="non-empty"):
            validate_non_empty_string("   ", "field")

    def test_not_a_string(self) -> None:
        with pytest.raises(ValidationError, match="non-empty"):
            validate_non_empty_string(123, "field")

    def test_none(self) -> None:
        with pytest.raises(ValidationError, match="non-empty"):
            validate_non_empty_string(None, "field")


class TestValidateColor:
    def test_valid_hex6(self) -> None:
        assert validate_color("#FF0000", "c") == "#FF0000"

    def test_valid_hex3(self) -> None:
        assert validate_color("#F00", "c") == "#F00"

    def test_valid_hex8(self) -> None:
        assert validate_color("#FF0000AA", "c") == "#FF0000AA"

    def test_none_allowed(self) -> None:
        assert validate_color("none", "c", allow_none=True) == "none"

    def test_empty_allowed(self) -> None:
        assert validate_color("", "c", allow_none=True) == ""

    def test_invalid_color(self) -> None:
        with pytest.raises(ValidationError, match="hex color"):
            validate_color("red", "c")

    def test_invalid_format(self) -> None:
        with pytest.raises(ValidationError, match="hex color"):
            validate_color("#GG0000", "c")

    def test_not_a_string(self) -> None:
        with pytest.raises(ValidationError, match="color string"):
            validate_color(123, "c")


class TestValidateNumber:
    def test_valid_int(self) -> None:
        assert validate_number(42, "n") == 42.0

    def test_valid_float(self) -> None:
        assert validate_number(3.14, "n") == 3.14

    def test_min_val(self) -> None:
        with pytest.raises(ValidationError, match=">="):
            validate_number(-1, "n", min_val=0)

    def test_max_val(self) -> None:
        with pytest.raises(ValidationError, match="<="):
            validate_number(200, "n", max_val=100)

    def test_not_a_number(self) -> None:
        with pytest.raises(ValidationError, match="number"):
            validate_number("abc", "n")


class TestValidateInt:
    def test_valid(self) -> None:
        assert validate_int(10, "i") == 10

    def test_bool_rejected(self) -> None:
        with pytest.raises(ValidationError, match="integer"):
            validate_int(True, "i")

    def test_float_rejected(self) -> None:
        with pytest.raises(ValidationError, match="integer"):
            validate_int(3.5, "i")

    def test_min_val(self) -> None:
        with pytest.raises(ValidationError, match=">="):
            validate_int(0, "i", min_val=1)

    def test_max_val(self) -> None:
        with pytest.raises(ValidationError, match="<="):
            validate_int(101, "i", max_val=100)


class TestValidateList:
    def test_valid(self) -> None:
        assert validate_list([1, 2, 3], "l") == [1, 2, 3]

    def test_min_length(self) -> None:
        with pytest.raises(ValidationError, match="at least 2"):
            validate_list([1], "l", min_length=2)

    def test_not_a_list(self) -> None:
        with pytest.raises(ValidationError, match="list"):
            validate_list("abc", "l")


class TestValidateAction:
    def test_valid(self) -> None:
        assert validate_action("create", "diagram", _DIAGRAM_ACTIONS) == "create"

    def test_case_insensitive(self) -> None:
        assert validate_action("CREATE", "diagram", _DIAGRAM_ACTIONS) == "create"

    def test_unknown_action(self) -> None:
        with pytest.raises(ValidationError, match="Unknown"):
            validate_action("bogus", "diagram", _DIAGRAM_ACTIONS)

    def test_empty_action(self) -> None:
        with pytest.raises(ValidationError, match="requires"):
            validate_action("", "diagram", _DIAGRAM_ACTIONS)


class TestValidateDirection:
    def test_valid(self) -> None:
        assert validate_direction("TB") == "TB"
        assert validate_direction("lr") == "LR"

    def test_invalid(self) -> None:
        with pytest.raises(ValidationError, match="must be one of"):
            validate_direction("DIAGONAL")


class TestValidateAlignment:
    def test_valid(self) -> None:
        assert validate_alignment("center") == "CENTER"

    def test_invalid(self) -> None:
        with pytest.raises(ValidationError, match="must be one of"):
            validate_alignment("diagonal")


class TestValidatePageFormat:
    def test_valid(self) -> None:
        assert validate_page_format("A4_PORTRAIT") == "A4_PORTRAIT"

    def test_invalid(self) -> None:
        with pytest.raises(ValidationError, match="must be one of"):
            validate_page_format("TABLOID")


class TestValidatePageIndex:
    def test_valid(self) -> None:
        assert validate_page_index(0, 3) == 0

    def test_out_of_range(self) -> None:
        with pytest.raises(ValidationError, match="out of range"):
            validate_page_index(5, 3)

    def test_negative(self) -> None:
        with pytest.raises(ValidationError, match="out of range"):
            validate_page_index(-1, 3)


class TestValidateGridSize:
    def test_valid(self) -> None:
        assert validate_grid_size(10) == 10

    def test_too_small(self) -> None:
        with pytest.raises(ValidationError, match=">="):
            validate_grid_size(0)

    def test_too_large(self) -> None:
        with pytest.raises(ValidationError, match="<="):
            validate_grid_size(200)


class TestValidateOpacity:
    def test_valid(self) -> None:
        assert validate_opacity(50) == 50

    def test_too_small(self) -> None:
        with pytest.raises(ValidationError, match=">="):
            validate_opacity(-1)

    def test_too_large(self) -> None:
        with pytest.raises(ValidationError, match="<="):
            validate_opacity(101)


class TestValidateFontSize:
    def test_valid(self) -> None:
        assert validate_font_size(14) == 14

    def test_too_small(self) -> None:
        with pytest.raises(ValidationError, match=">="):
            validate_font_size(0)


class TestValidateColumns:
    def test_valid(self) -> None:
        assert validate_columns(3) == 3

    def test_zero(self) -> None:
        with pytest.raises(ValidationError, match=">="):
            validate_columns(0)


# ===================================================================
# Unit tests for composite validators
# ===================================================================


class TestValidateVertexDict:
    def test_valid(self) -> None:
        validate_vertex_dict({"label": "A", "x": 10, "y": 20}, 0)

    def test_missing_label(self) -> None:
        with pytest.raises(ValidationError, match="label"):
            validate_vertex_dict({"x": 10, "y": 20}, 0)

    def test_missing_x(self) -> None:
        with pytest.raises(ValidationError, match="'x'"):
            validate_vertex_dict({"label": "A", "y": 20}, 0)

    def test_missing_y(self) -> None:
        with pytest.raises(ValidationError, match="'y'"):
            validate_vertex_dict({"label": "A", "x": 10}, 0)

    def test_label_not_string(self) -> None:
        with pytest.raises(ValidationError, match="string"):
            validate_vertex_dict({"label": 123, "x": 10, "y": 20}, 0)

    def test_x_not_number(self) -> None:
        with pytest.raises(ValidationError, match="number"):
            validate_vertex_dict({"label": "A", "x": "bad", "y": 20}, 0)

    def test_width_negative(self) -> None:
        with pytest.raises(ValidationError, match="> 0"):
            validate_vertex_dict({"label": "A", "x": 10, "y": 20, "width": -5}, 0)

    def test_height_zero(self) -> None:
        with pytest.raises(ValidationError, match="> 0"):
            validate_vertex_dict({"label": "A", "x": 10, "y": 20, "height": 0}, 0)

    def test_not_a_dict(self) -> None:
        with pytest.raises(ValidationError, match="dict"):
            validate_vertex_dict("not a dict", 0)


class TestValidateEdgeDict:
    def test_valid(self) -> None:
        validate_edge_dict({"source_id": "1", "target_id": "2"}, 0)

    def test_missing_source(self) -> None:
        with pytest.raises(ValidationError, match="source_id"):
            validate_edge_dict({"target_id": "2"}, 0)

    def test_missing_target(self) -> None:
        with pytest.raises(ValidationError, match="target_id"):
            validate_edge_dict({"source_id": "1"}, 0)

    def test_empty_source(self) -> None:
        with pytest.raises(ValidationError, match="non-empty"):
            validate_edge_dict({"source_id": "", "target_id": "2"}, 0)

    def test_self_loop(self) -> None:
        with pytest.raises(ValidationError, match="different"):
            validate_edge_dict({"source_id": "1", "target_id": "1"}, 0)


class TestValidateDagEdgeDict:
    def test_valid(self) -> None:
        validate_dag_edge_dict({"source": "A", "target": "B"}, 0)

    def test_missing_source(self) -> None:
        with pytest.raises(ValidationError, match="source"):
            validate_dag_edge_dict({"target": "B"}, 0)

    def test_missing_target(self) -> None:
        with pytest.raises(ValidationError, match="target"):
            validate_dag_edge_dict({"source": "A"}, 0)


class TestValidateUpdateDict:
    def test_valid(self) -> None:
        validate_update_dict({"cell_id": "2", "label": "New"}, 0)

    def test_missing_cell_id(self) -> None:
        with pytest.raises(ValidationError, match="cell_id"):
            validate_update_dict({"label": "New"}, 0)

    def test_width_negative(self) -> None:
        with pytest.raises(ValidationError, match="> 0"):
            validate_update_dict({"cell_id": "2", "width": -10}, 0)


class TestValidateConnectionDict:
    def test_valid_labels(self) -> None:
        validate_connection_dict({"source": "A", "target": "B"}, 0)

    def test_valid_ids(self) -> None:
        validate_connection_dict({"source_id": "1", "target_id": "2"}, 0)

    def test_missing_both(self) -> None:
        with pytest.raises(ValidationError, match="source.*target"):
            validate_connection_dict({"label": "edge"}, 0)


class TestValidateFlowchartStep:
    def test_valid(self) -> None:
        from drawio_mcp.validation import validate_flowchart_step
        validate_flowchart_step({"label": "Start", "type": "terminator"}, 0)

    def test_missing_label(self) -> None:
        from drawio_mcp.validation import validate_flowchart_step
        with pytest.raises(ValidationError, match="label"):
            validate_flowchart_step({"type": "process"}, 0)

    def test_invalid_type(self) -> None:
        from drawio_mcp.validation import validate_flowchart_step
        with pytest.raises(ValidationError, match="unknown type"):
            validate_flowchart_step({"label": "X", "type": "bogus"}, 0)


class TestValidateLegendEntry:
    def test_valid(self) -> None:
        from drawio_mcp.validation import validate_legend_entry
        validate_legend_entry({"label": "A", "fill_color": "#FF0000"}, 0)

    def test_missing_label(self) -> None:
        from drawio_mcp.validation import validate_legend_entry
        with pytest.raises(ValidationError, match="label"):
            validate_legend_entry({"fill_color": "#FF0000"}, 0)

    def test_invalid_fill_color(self) -> None:
        from drawio_mcp.validation import validate_legend_entry
        with pytest.raises(ValidationError, match="hex color"):
            validate_legend_entry({"label": "A", "fill_color": "red"}, 0)


class TestValidateNodeStyles:
    def test_valid(self) -> None:
        validate_node_styles({"DB": "DATABASE", "API": "SERVICE"})

    def test_none(self) -> None:
        assert validate_node_styles(None) == {}

    def test_not_a_dict(self) -> None:
        with pytest.raises(ValidationError, match="dict"):
            validate_node_styles("not a dict")

    def test_non_string_value(self) -> None:
        with pytest.raises(ValidationError, match="string"):
            validate_node_styles({"DB": 123})


class TestValidateAdjacency:
    def test_valid(self) -> None:
        validate_adjacency({"A": ["B", "C"]})

    def test_empty(self) -> None:
        with pytest.raises(ValidationError, match="non-empty"):
            validate_adjacency({})

    def test_none(self) -> None:
        with pytest.raises(ValidationError, match="non-empty"):
            validate_adjacency(None)

    def test_not_a_dict(self) -> None:
        with pytest.raises(ValidationError, match="dict"):
            validate_adjacency("not a dict")

    def test_value_not_list(self) -> None:
        with pytest.raises(ValidationError, match="list"):
            validate_adjacency({"A": "B"})


class TestValidateExtraDict:
    def test_valid(self) -> None:
        validate_extra_dict({"key": "value"})

    def test_none(self) -> None:
        assert validate_extra_dict(None) == {}

    def test_not_a_dict(self) -> None:
        with pytest.raises(ValidationError, match="dict"):
            validate_extra_dict("not a dict")


# ===================================================================
# Integration tests: diagram() tool validation
# ===================================================================


class TestDiagramValidation:
    def test_invalid_action(self) -> None:
        result = diagram(action="bogus")
        assert "Error" in result
        assert "bogus" in result

    def test_empty_action(self) -> None:
        result = diagram(action="")
        assert "Error" in result

    def test_create_empty_name(self) -> None:
        result = diagram(action="create", name="")
        assert "Error" in result
        assert "name" in result.lower()

    def test_create_invalid_page_format(self) -> None:
        result = diagram(action="create", name="test", page_format="TABLOID")
        assert "Error" in result
        assert "page_format" in result

    def test_create_invalid_grid_size(self) -> None:
        result = diagram(action="create", name="test", grid_size=0)
        assert "Error" in result
        assert "grid_size" in result

    def test_create_invalid_background(self) -> None:
        result = diagram(action="create", name="test", background="red")
        assert "Error" in result
        assert "background" in result

    def test_save_empty_name(self) -> None:
        result = diagram(action="save", name="", file_path="/tmp/x.drawio")
        assert "Error" in result

    def test_save_empty_file_path(self) -> None:
        result = diagram(action="save", name="test", file_path="")
        assert "Error" in result

    def test_load_empty_name(self) -> None:
        result = diagram(action="load", name="", file_path="/tmp/x.drawio")
        assert "Error" in result

    def test_load_empty_file_path(self) -> None:
        result = diagram(action="load", name="test", file_path="")
        assert "Error" in result

    def test_import_xml_empty_name(self) -> None:
        result = diagram(action="import_xml", name="", xml_content="<xml/>")
        assert "Error" in result

    def test_import_xml_empty_content(self) -> None:
        result = diagram(action="import_xml", name="test", xml_content="")
        assert "Error" in result

    def test_get_xml_empty_name(self) -> None:
        result = diagram(action="get_xml", name="")
        assert "Error" in result

    def test_add_page_empty_name(self) -> None:
        result = diagram(action="add_page", name="")
        assert "Error" in result


# ===================================================================
# Integration tests: draw() tool validation
# ===================================================================


class TestDrawValidation:
    def test_invalid_action(self) -> None:
        result = draw(action="bogus", diagram_name="x")
        assert "Error" in result

    def test_empty_diagram_name(self) -> None:
        result = draw(action="add_vertices", diagram_name="")
        assert "Error" in result

    def test_nonexistent_diagram(self) -> None:
        result = draw(action="add_vertices", diagram_name="nope", vertices=[
            {"label": "A", "x": 0, "y": 0}
        ])
        assert "Error" in result
        assert "not found" in result

    def test_add_vertices_empty_list(self) -> None:
        diagram(action="create", name="dv1")
        result = draw(action="add_vertices", diagram_name="dv1", vertices=[])
        assert "Error" in result
        assert "at least 1" in result

    def test_add_vertices_missing_label(self) -> None:
        diagram(action="create", name="dv2")
        result = draw(action="add_vertices", diagram_name="dv2", vertices=[
            {"x": 10, "y": 20}
        ])
        assert "Error" in result
        assert "label" in result

    def test_add_vertices_missing_x(self) -> None:
        diagram(action="create", name="dv3")
        result = draw(action="add_vertices", diagram_name="dv3", vertices=[
            {"label": "A", "y": 20}
        ])
        assert "Error" in result
        assert "'x'" in result

    def test_add_vertices_bad_width(self) -> None:
        diagram(action="create", name="dv4")
        result = draw(action="add_vertices", diagram_name="dv4", vertices=[
            {"label": "A", "x": 0, "y": 0, "width": -10}
        ])
        assert "Error" in result
        assert "width" in result

    def test_add_edges_empty_list(self) -> None:
        diagram(action="create", name="de1")
        result = draw(action="add_edges", diagram_name="de1", edges=[])
        assert "Error" in result
        assert "at least 1" in result

    def test_add_edges_missing_source(self) -> None:
        diagram(action="create", name="de2")
        result = draw(action="add_edges", diagram_name="de2", edges=[
            {"target_id": "2"}
        ])
        assert "Error" in result
        assert "source_id" in result

    def test_add_edges_self_loop(self) -> None:
        diagram(action="create", name="de3")
        result = draw(action="add_edges", diagram_name="de3", edges=[
            {"source_id": "1", "target_id": "1"}
        ])
        assert "Error" in result
        assert "different" in result

    def test_add_group_empty_label(self) -> None:
        diagram(action="create", name="dg1")
        result = draw(action="add_group", diagram_name="dg1", group_label="")
        assert "Error" in result
        assert "group_label" in result

    def test_add_group_negative_width(self) -> None:
        diagram(action="create", name="dg2")
        result = draw(action="add_group", diagram_name="dg2",
                      group_label="G", group_width=-100)
        assert "Error" in result
        assert "group_width" in result

    def test_update_cells_empty_list(self) -> None:
        diagram(action="create", name="du1")
        result = draw(action="update_cells", diagram_name="du1", updates=[])
        assert "Error" in result
        assert "at least 1" in result

    def test_update_cells_missing_cell_id(self) -> None:
        diagram(action="create", name="du2")
        result = draw(action="update_cells", diagram_name="du2", updates=[
            {"label": "New"}
        ])
        assert "Error" in result
        assert "cell_id" in result

    def test_update_cells_negative_width(self) -> None:
        diagram(action="create", name="du3")
        result = draw(action="update_cells", diagram_name="du3", updates=[
            {"cell_id": "2", "width": -5}
        ])
        assert "Error" in result
        assert "width" in result

    def test_delete_cells_empty_list(self) -> None:
        diagram(action="create", name="dd1")
        result = draw(action="delete_cells", diagram_name="dd1", cell_ids=[])
        assert "Error" in result
        assert "at least 1" in result

    def test_add_title_empty(self) -> None:
        diagram(action="create", name="dt1")
        result = draw(action="add_title", diagram_name="dt1", title="")
        assert "Error" in result
        assert "title" in result

    def test_add_legend_empty_entries(self) -> None:
        diagram(action="create", name="dl1")
        result = draw(action="add_legend", diagram_name="dl1", legend_entries=[])
        assert "Error" in result
        assert "at least 1" in result

    def test_add_legend_missing_label(self) -> None:
        diagram(action="create", name="dl2")
        result = draw(action="add_legend", diagram_name="dl2", legend_entries=[
            {"fill_color": "#FF0000"}
        ])
        assert "Error" in result
        assert "label" in result

    def test_add_legend_invalid_color(self) -> None:
        diagram(action="create", name="dl3")
        result = draw(action="add_legend", diagram_name="dl3", legend_entries=[
            {"label": "A", "fill_color": "notacolor"}
        ])
        assert "Error" in result
        assert "hex color" in result

    def test_build_dag_empty_edges(self) -> None:
        diagram(action="create", name="bd1")
        result = draw(action="build_dag", diagram_name="bd1", edges=[])
        assert "Error" in result
        assert "at least 1" in result

    def test_build_dag_missing_source(self) -> None:
        diagram(action="create", name="bd2")
        result = draw(action="build_dag", diagram_name="bd2", edges=[
            {"target": "B"}
        ])
        assert "Error" in result
        assert "source" in result

    def test_build_dag_invalid_direction(self) -> None:
        diagram(action="create", name="bd3")
        result = draw(action="build_dag", diagram_name="bd3", edges=[
            {"source": "A", "target": "B"}
        ], direction="DIAGONAL")
        assert "Error" in result
        assert "direction" in result

    def test_build_dag_invalid_node_styles(self) -> None:
        diagram(action="create", name="bd4")
        result = draw(action="build_dag", diagram_name="bd4", edges=[
            {"source": "A", "target": "B"}
        ], node_styles="not a dict")
        assert "Error" in result

    def test_build_full_empty_vertices(self) -> None:
        diagram(action="create", name="bf1")
        result = draw(action="build_full", diagram_name="bf1", vertices=[])
        assert "Error" in result
        assert "at least 1" in result

    def test_build_full_invalid_edge(self) -> None:
        diagram(action="create", name="bf2")
        result = draw(action="build_full", diagram_name="bf2",
                      vertices=[{"label": "A", "x": 0, "y": 0}],
                      edges=[{"source_id": "1"}])
        assert "Error" in result
        assert "target_id" in result

    def test_invalid_page_index(self) -> None:
        diagram(action="create", name="dpi1")
        result = draw(action="add_vertices", diagram_name="dpi1",
                      vertices=[{"label": "A", "x": 0, "y": 0}],
                      page_index=99)
        assert "Error" in result
        assert "page_index" in result.lower() or "out of range" in result


# ===================================================================
# Integration tests: style() tool validation
# ===================================================================


class TestStyleValidation:
    def test_invalid_action(self) -> None:
        result = style(action="bogus")
        assert "Error" in result

    def test_build_invalid_fill_color(self) -> None:
        result = style(action="build", fill_color="red")
        assert "Error" in result
        assert "fill_color" in result

    def test_build_invalid_font_size(self) -> None:
        result = style(action="build", font_size=-5)
        assert "Error" in result
        assert "font_size" in result

    def test_build_invalid_opacity(self) -> None:
        result = style(action="build", opacity=150)
        assert "Error" in result
        assert "opacity" in result

    def test_apply_theme_empty_diagram_name(self) -> None:
        result = style(action="apply_theme", diagram_name="", theme="BLUE")
        assert "Error" in result

    def test_apply_theme_empty_theme(self) -> None:
        diagram(action="create", name="st1")
        result = style(action="apply_theme", diagram_name="st1", theme="")
        assert "Error" in result

    def test_apply_theme_invalid_page_index(self) -> None:
        diagram(action="create", name="st2")
        result = style(action="apply_theme", diagram_name="st2",
                       theme="BLUE", page_index=99)
        assert "Error" in result


# ===================================================================
# Integration tests: layout() tool validation
# ===================================================================


class TestLayoutValidation:
    def test_invalid_action(self) -> None:
        diagram(action="create", name="lt1")
        result = layout(action="bogus", diagram_name="lt1")
        assert "Error" in result

    def test_empty_diagram_name(self) -> None:
        result = layout(action="polish", diagram_name="")
        assert "Error" in result

    def test_sugiyama_empty_connections(self) -> None:
        diagram(action="create", name="ls1")
        result = layout(action="sugiyama", diagram_name="ls1", connections=[])
        assert "Error" in result
        assert "at least 1" in result

    def test_sugiyama_invalid_direction(self) -> None:
        diagram(action="create", name="ls2")
        result = layout(action="sugiyama", diagram_name="ls2",
                        connections=[{"source": "A", "target": "B"}],
                        direction="DIAGONAL")
        assert "Error" in result
        assert "direction" in result

    def test_tree_missing_adjacency(self) -> None:
        diagram(action="create", name="ltr1")
        result = layout(action="tree", diagram_name="ltr1", root="Root")
        assert "Error" in result
        assert "adjacency" in result

    def test_tree_empty_root(self) -> None:
        diagram(action="create", name="ltr2")
        result = layout(action="tree", diagram_name="ltr2",
                        adjacency={"A": ["B"]}, root="")
        assert "Error" in result
        assert "root" in result

    def test_horizontal_empty_labels(self) -> None:
        diagram(action="create", name="lh1")
        result = layout(action="horizontal", diagram_name="lh1", labels=[])
        assert "Error" in result
        assert "at least 1" in result

    def test_vertical_empty_labels(self) -> None:
        diagram(action="create", name="lv1")
        result = layout(action="vertical", diagram_name="lv1", labels=[])
        assert "Error" in result
        assert "at least 1" in result

    def test_grid_empty_labels(self) -> None:
        diagram(action="create", name="lg1")
        result = layout(action="grid", diagram_name="lg1", labels=[])
        assert "Error" in result
        assert "at least 1" in result

    def test_grid_invalid_columns(self) -> None:
        diagram(action="create", name="lg2")
        result = layout(action="grid", diagram_name="lg2",
                        labels=["A", "B"], columns=0)
        assert "Error" in result
        assert "columns" in result

    def test_flowchart_empty_steps(self) -> None:
        diagram(action="create", name="lf1")
        result = layout(action="flowchart", diagram_name="lf1", steps=[])
        assert "Error" in result
        assert "at least 1" in result

    def test_flowchart_invalid_step_type(self) -> None:
        diagram(action="create", name="lf2")
        result = layout(action="flowchart", diagram_name="lf2", steps=[
            {"label": "Start", "type": "bogus"}
        ])
        assert "Error" in result
        assert "bogus" in result

    def test_flowchart_missing_label(self) -> None:
        diagram(action="create", name="lf3")
        result = layout(action="flowchart", diagram_name="lf3", steps=[
            {"type": "process"}
        ])
        assert "Error" in result
        assert "label" in result

    def test_smart_connect_empty_connections(self) -> None:
        diagram(action="create", name="lsc1")
        result = layout(action="smart_connect", diagram_name="lsc1",
                        connections=[])
        assert "Error" in result
        assert "at least 1" in result

    def test_align_too_few_cells(self) -> None:
        diagram(action="create", name="la1")
        result = layout(action="align", diagram_name="la1",
                        cell_ids=["1"])
        assert "Error" in result
        assert "at least 2" in result

    def test_align_invalid_alignment(self) -> None:
        diagram(action="create", name="la2")
        result = layout(action="align", diagram_name="la2",
                        cell_ids=["1", "2"], alignment="diagonal")
        assert "Error" in result
        assert "alignment" in result

    def test_distribute_too_few_cells(self) -> None:
        diagram(action="create", name="ld1")
        result = layout(action="distribute", diagram_name="ld1",
                        cell_ids=["1"])
        assert "Error" in result
        assert "at least 2" in result

    def test_polish_invalid_direction(self) -> None:
        diagram(action="create", name="lp1")
        result = layout(action="polish", diagram_name="lp1", direction="DIAGONAL")
        assert "Error" in result
        assert "direction" in result

    def test_relayout_invalid_direction(self) -> None:
        diagram(action="create", name="lr1")
        result = layout(action="relayout", diagram_name="lr1", direction="DIAGONAL")
        assert "Error" in result

    def test_resize_container_empty_id(self) -> None:
        diagram(action="create", name="lrc1")
        result = layout(action="resize_container", diagram_name="lrc1",
                        container_id="")
        assert "Error" in result
        assert "container_id" in result


# ===================================================================
# Integration tests: inspect() tool validation
# ===================================================================


class TestInspectValidation:
    def test_invalid_action(self) -> None:
        result = inspect(action="bogus")
        assert "Error" in result

    def test_cells_empty_diagram_name(self) -> None:
        result = inspect(action="cells", diagram_name="")
        assert "Error" in result

    def test_cells_nonexistent_diagram(self) -> None:
        result = inspect(action="cells", diagram_name="nope")
        assert "Error" in result
        assert "not found" in result

    def test_invalid_page_index(self) -> None:
        diagram(action="create", name="ip1")
        result = inspect(action="cells", diagram_name="ip1", page_index=5)
        assert "Error" in result

    def test_ports_no_diagram_needed(self) -> None:
        result = inspect(action="ports")
        assert "TOP" in result  # ports doesn't need a diagram


# ===================================================================
# Verify existing tests still pass — the validation should not
# break any currently-working flows.
# ===================================================================


class TestExistingFlowsStillWork:
    """Smoke tests ensuring validated paths work with correct inputs."""

    def test_full_workflow(self) -> None:
        result = diagram(action="create", name="smoke1")
        assert "created" in result

        ids = json.loads(draw(action="add_vertices", diagram_name="smoke1", vertices=[
            {"label": "A", "x": 50, "y": 50},
            {"label": "B", "x": 200, "y": 50},
        ]))
        assert len(ids) == 2

        edge_ids = json.loads(draw(action="add_edges", diagram_name="smoke1", edges=[
            {"source_id": ids[0], "target_id": ids[1], "label": "edge"},
        ]))
        assert len(edge_ids) == 1

        s = style(action="build", base="rounded=1;", fill_color="#dae8fc",
                   font_size=14, opacity=80)
        assert "fillColor=#dae8fc" in s

        result = style(action="apply_theme", diagram_name="smoke1", theme="BLUE")
        assert "cell(s)" in result

        cells = json.loads(inspect(action="cells", diagram_name="smoke1"))
        assert len(cells) > 2

        info = json.loads(inspect(action="info", diagram_name="smoke1"))
        assert info["name"] == "smoke1"

    def test_build_dag_workflow(self) -> None:
        diagram(action="create", name="smoke2")
        result = json.loads(draw(action="build_dag", diagram_name="smoke2", edges=[
            {"source": "Client", "target": "API"},
            {"source": "API", "target": "DB"},
        ], theme="BLUE", title="Test", direction="TB"))
        assert "__summary" in result

    def test_layout_flowchart(self) -> None:
        diagram(action="create", name="smoke3")
        result = json.loads(layout(action="flowchart", diagram_name="smoke3", steps=[
            {"label": "Start", "type": "terminator"},
            {"label": "End", "type": "terminator"},
        ]))
        assert len(result["vertex_ids"]) == 2

    def test_layout_tree(self) -> None:
        diagram(action="create", name="smoke4")
        result = json.loads(layout(action="tree", diagram_name="smoke4",
                                   adjacency={"R": ["A", "B"]}, root="R"))
        assert len(result) == 3
