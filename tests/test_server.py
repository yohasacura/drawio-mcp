"""Tests for the MCP server tools (5-tool architecture)."""

import json
import os
import tempfile

from drawio_mcp.server import (
    _diagrams,
    diagram,
    draw,
    inspect,
    layout,
    style,
)


def setup_function() -> None:
    """Clear diagrams between tests."""
    _diagrams.clear()


def test_create_and_save() -> None:
    result = diagram(action="create", name="test1")
    assert "created" in result

    v_ids = json.loads(draw(action="add_vertices", diagram_name="test1", vertices=[
        {"label": "Hello", "x": 100, "y": 200},
    ]))
    v1 = v_ids[0]
    v_ids2 = json.loads(draw(action="add_vertices", diagram_name="test1", vertices=[
        {"label": "World", "x": 300, "y": 200},
    ]))
    v2 = v_ids2[0]
    draw(action="add_edges", diagram_name="test1", edges=[
        {"source_id": v1, "target_id": v2, "label": "arrow"},
    ])

    xml = diagram(action="get_xml", name="test1")
    assert "<mxfile" in xml
    assert 'value="Hello"' in xml
    assert 'edge="1"' in xml

    with tempfile.NamedTemporaryFile(suffix=".drawio", delete=False) as f:
        path = f.name
    try:
        result = diagram(action="save", name="test1", file_path=path)
        assert "saved" in result.lower()
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        assert "<mxfile" in content
    finally:
        os.unlink(path)


def test_bulk_operations() -> None:
    diagram(action="create", name="bulk")
    ids = json.loads(draw(action="add_vertices", diagram_name="bulk", vertices=[
        {"label": "A", "x": 0, "y": 0},
        {"label": "B", "x": 200, "y": 0},
        {"label": "C", "x": 400, "y": 0},
    ]))
    assert len(ids) == 3

    edge_ids = json.loads(draw(action="add_edges", diagram_name="bulk", edges=[
        {"source_id": ids[0], "target_id": ids[1]},
        {"source_id": ids[1], "target_id": ids[2]},
    ]))
    assert len(edge_ids) == 2


def test_group_and_children() -> None:
    diagram(action="create", name="groups")
    gid = draw(action="add_group", diagram_name="groups", group_label="My Group",
               group_x=50, group_y=50, group_width=300, group_height=200)
    # Use ABSOLUTE coords (80, 100) — server should convert to (30, 50) relative
    cid = json.loads(draw(action="add_vertices", diagram_name="groups", vertices=[
        {"label": "Inside", "x": 80, "y": 100, "parent_id": gid},
    ]))[0]
    cells = json.loads(inspect(action="cells", diagram_name="groups"))
    child = next(c for c in cells if c["id"] == cid)
    assert child["parent"] == gid
    # Check that the stored position is relative (80-50=30, 100-50=50)
    assert child["position"]["x"] == 30
    assert child["position"]["y"] == 50


def test_update_style_and_label() -> None:
    diagram(action="create", name="upd")
    cid = json.loads(draw(action="add_vertices", diagram_name="upd", vertices=[
        {"label": "Original", "x": 0, "y": 0},
    ]))[0]
    draw(action="update_cells", diagram_name="upd", updates=[
        {"cell_id": cid, "style": "ellipse;whiteSpace=wrap;html=1;", "label": "Updated"},
    ])
    cells = json.loads(inspect(action="cells", diagram_name="upd"))
    cell = next(c for c in cells if c["id"] == cid)
    assert cell["label"] == "Updated"
    assert "ellipse" in cell["style"]


def test_move_and_resize() -> None:
    diagram(action="create", name="mvr")
    cid = json.loads(draw(action="add_vertices", diagram_name="mvr", vertices=[
        {"label": "Box", "x": 0, "y": 0},
    ]))[0]
    draw(action="update_cells", diagram_name="mvr", updates=[
        {"cell_id": cid, "x": 500, "y": 500, "width": 200, "height": 100},
    ])
    cells = json.loads(inspect(action="cells", diagram_name="mvr"))
    cell = next(c for c in cells if c["id"] == cid)
    assert cell["position"]["x"] == 500
    assert cell["position"]["width"] == 200


def test_delete_cascades() -> None:
    diagram(action="create", name="del")
    v1 = json.loads(draw(action="add_vertices", diagram_name="del", vertices=[
        {"label": "A", "x": 0, "y": 0},
    ]))[0]
    v2 = json.loads(draw(action="add_vertices", diagram_name="del", vertices=[
        {"label": "B", "x": 200, "y": 0},
    ]))[0]
    draw(action="add_edges", diagram_name="del", edges=[
        {"source_id": v1, "target_id": v2},
    ])
    result = draw(action="delete_cells", diagram_name="del", cell_ids=[v1])
    assert "2" in result  # vertex + edge removed


def test_auto_layout_horizontal() -> None:
    diagram(action="create", name="hlayout")
    result = json.loads(layout(action="horizontal", diagram_name="hlayout",
                               labels=["A", "B", "C"]))
    assert len(result["vertex_ids"]) == 3
    assert len(result["edge_ids"]) == 2


def test_auto_layout_vertical() -> None:
    diagram(action="create", name="vlayout")
    result = json.loads(layout(action="vertical", diagram_name="vlayout",
                               labels=["X", "Y", "Z"]))
    assert len(result["vertex_ids"]) == 3


def test_auto_layout_tree() -> None:
    diagram(action="create", name="tree")
    mapping = json.loads(layout(action="tree", diagram_name="tree",
                                adjacency={"Root": ["A", "B"], "A": ["C"]},
                                root="Root"))
    assert len(mapping) == 4


def test_create_flowchart() -> None:
    diagram(action="create", name="flow")
    result = json.loads(layout(action="flowchart", diagram_name="flow", steps=[
        {"label": "Start", "type": "terminator"},
        {"label": "Process?", "type": "decision"},
        {"label": "Do Work", "type": "process"},
        {"label": "End", "type": "terminator"},
    ]))
    assert len(result["vertex_ids"]) == 4
    assert len(result["edge_ids"]) == 3


def test_build_style() -> None:
    s = style(
        action="build",
        base="rounded=1;whiteSpace=wrap;html=1;",
        theme="BLUE",
        bold=True,
        font_size=14,
    )
    assert "fillColor=#dae8fc" in s
    assert "fontStyle=1" in s
    assert "fontSize=14" in s


def test_list_styles() -> None:
    assert "RECTANGLE" in style(action="list_vertex_presets")
    assert "ORTHOGONAL" in style(action="list_edge_presets")
    assert "BLUE" in style(action="list_themes")


def test_list_diagrams() -> None:
    diagram(action="create", name="d1")
    diagram(action="create", name="d2")
    result = json.loads(diagram(action="list"))
    names = [d["name"] for d in result]
    assert "d1" in names
    assert "d2" in names


def test_import_xml() -> None:
    xml = """<mxfile>
      <diagram name="Imported" id="imp1">
        <mxGraphModel>
          <root>
            <mxCell id="0" />
            <mxCell id="1" parent="0" />
            <mxCell id="2" value="Test" style="rounded=1;" parent="1" vertex="1">
              <mxGeometry x="10" y="20" width="100" height="50" as="geometry" />
            </mxCell>
          </root>
        </mxGraphModel>
      </diagram>
    </mxfile>"""
    result = diagram(action="import_xml", name="imported", xml_content=xml)
    assert "3 cells" in result
    cells = json.loads(inspect(action="cells", diagram_name="imported"))
    assert any(c.get("label") == "Test" for c in cells)


def test_load_and_save_roundtrip() -> None:
    diagram(action="create", name="rt")
    draw(action="add_vertices", diagram_name="rt", vertices=[
        {"label": "RoundTrip", "x": 50, "y": 50},
    ])
    with tempfile.NamedTemporaryFile(suffix=".drawio", delete=False) as f:
        path = f.name
    try:
        diagram(action="save", name="rt", file_path=path)
        _diagrams.clear()
        diagram(action="load", name="rt_loaded", file_path=path)
        cells = json.loads(inspect(action="cells", diagram_name="rt_loaded"))
        assert any(c.get("label") == "RoundTrip" for c in cells)
    finally:
        os.unlink(path)


def test_error_handling() -> None:
    assert "Error" in draw(action="add_vertices", diagram_name="nonexistent", vertices=[
        {"label": "X", "x": 0, "y": 0},
    ])
    assert "Error" in draw(action="add_edges", diagram_name="nonexistent", edges=[
        {"source_id": "1", "target_id": "2"},
    ])
    assert "Error" in diagram(action="save", name="nonexistent", file_path="/tmp/x.drawio")
    assert "Error" in diagram(action="get_xml", name="nonexistent")


# ===================================================================
# Style alias resolution tests
# ===================================================================

def test_style_alias_short_names() -> None:
    """Short names like STORED_DATA should resolve to FLOWCHART_STORED_DATA."""
    diagram(action="create", name="alias")
    cid = json.loads(draw(action="add_vertices", diagram_name="alias", vertices=[
        {"label": "DB", "x": 100, "y": 100, "style_preset": "STORED_DATA"},
    ]))[0]
    cells = json.loads(inspect(action="cells", diagram_name="alias"))
    cell = next(c for c in cells if c["id"] == cid)
    assert "dataStorage" in cell["style"]


def test_style_alias_manual_input() -> None:
    """MANUAL_INPUT should resolve to FLOWCHART_MANUAL_INPUT."""
    diagram(action="create", name="alias2")
    cid = json.loads(draw(action="add_vertices", diagram_name="alias2", vertices=[
        {"label": "Input", "x": 100, "y": 100, "style_preset": "MANUAL_INPUT"},
    ]))[0]
    cells = json.loads(inspect(action="cells", diagram_name="alias2"))
    cell = next(c for c in cells if c["id"] == cid)
    assert "manualInput" in cell["style"]


def test_style_alias_decision() -> None:
    """DECISION should resolve to FLOWCHART_DECISION (rhombus)."""
    diagram(action="create", name="alias3")
    cid = json.loads(draw(action="add_vertices", diagram_name="alias3", vertices=[
        {"label": "?", "x": 100, "y": 100, "style_preset": "DECISION"},
    ]))[0]
    cells = json.loads(inspect(action="cells", diagram_name="alias3"))
    cell = next(c for c in cells if c["id"] == cid)
    assert "rhombus" in cell["style"]


def test_style_unknown_preset_falls_back() -> None:
    """An unknown preset should fall back to ROUNDED_RECTANGLE, not be used raw."""
    diagram(action="create", name="alias4")
    cid = json.loads(draw(action="add_vertices", diagram_name="alias4", vertices=[
        {"label": "X", "x": 100, "y": 100, "style_preset": "TOTALLY_BOGUS"},
    ]))[0]
    cells = json.loads(inspect(action="cells", diagram_name="alias4"))
    cell = next(c for c in cells if c["id"] == cid)
    assert "rounded=1" in cell["style"]
    assert "TOTALLY_BOGUS" not in cell["style"]


# ===================================================================
# Coordinate conversion tests
# ===================================================================

def test_abs_to_relative_nested_groups() -> None:
    """Children of nested groups should get doubly-offset coordinates."""
    diagram(action="create", name="nested")
    g1 = draw(action="add_group", diagram_name="nested", group_label="Outer",
              group_x=100, group_y=100, group_width=400, group_height=300)
    g2 = draw(action="add_group", diagram_name="nested", group_label="Inner",
              group_x=150, group_y=150, group_width=200, group_height=150,
              group_parent_id=g1)
    cid = json.loads(draw(action="add_vertices", diagram_name="nested", vertices=[
        {"label": "Deep", "x": 200, "y": 200, "parent_id": g2},
    ]))[0]
    cells = json.loads(inspect(action="cells", diagram_name="nested"))
    cell = next(c for c in cells if c["id"] == cid)
    # g1 at (100,100), g2 relative to g1 = (50, 50)
    # child relative to g2 = (200-150, 200-150) = (50, 50)
    assert cell["position"]["x"] == 50
    assert cell["position"]["y"] == 50


def test_bulk_vertices_in_group_coords() -> None:
    """Bulk-added vertices in a group should have relative coordinates."""
    diagram(action="create", name="bulk_grp")
    gid = draw(action="add_group", diagram_name="bulk_grp", group_label="G",
               group_x=200, group_y=200, group_width=300, group_height=200)
    ids = json.loads(draw(action="add_vertices", diagram_name="bulk_grp", vertices=[
        {"label": "A", "x": 220, "y": 240, "parent_id": gid},
        {"label": "B", "x": 350, "y": 240, "parent_id": gid},
    ]))
    cells = json.loads(inspect(action="cells", diagram_name="bulk_grp"))
    a = next(c for c in cells if c["id"] == ids[0])
    b = next(c for c in cells if c["id"] == ids[1])
    assert a["position"]["x"] == 20   # 220 - 200
    assert b["position"]["x"] == 150  # 350 - 200


# ===================================================================
# New tool tests: apply_theme, add_title, auto_connect
# ===================================================================

def test_apply_theme_all_cells() -> None:
    """apply_theme without cell_ids should theme all vertices."""
    diagram(action="create", name="themed")
    draw(action="add_vertices", diagram_name="themed", vertices=[
        {"label": "A", "x": 50, "y": 50},
        {"label": "B", "x": 200, "y": 50},
    ])
    result = style(action="apply_theme", diagram_name="themed", theme="BLUE")
    assert "2 cell(s)" in result
    cells = json.loads(inspect(action="cells", diagram_name="themed"))
    for c in cells:
        if c.get("type") == "vertex":
            assert "#dae8fc" in c["style"]


def test_apply_theme_specific_cells() -> None:
    """apply_theme with cell_ids should only theme selected cells."""
    diagram(action="create", name="themed2")
    ids = json.loads(draw(action="add_vertices", diagram_name="themed2", vertices=[
        {"label": "A", "x": 50, "y": 50},
        {"label": "B", "x": 200, "y": 50},
    ]))
    a, b = ids[0], ids[1]
    style(action="apply_theme", diagram_name="themed2", theme="RED", cell_ids=[a])
    cells = json.loads(inspect(action="cells", diagram_name="themed2"))
    cell_a = next(c for c in cells if c["id"] == a)
    cell_b = next(c for c in cells if c["id"] == b)
    assert "#f8cecc" in cell_a["style"]  # RED applied
    assert "#f8cecc" not in cell_b["style"]  # untouched


def test_add_title() -> None:
    """add_title should create title and subtitle cells."""
    diagram(action="create", name="titled")
    result = json.loads(draw(action="add_title", diagram_name="titled",
                             title="My Diagram", subtitle="Architecture Overview"))
    assert len(result) == 2
    cells = json.loads(inspect(action="cells", diagram_name="titled"))
    labels = [c.get("label", "") for c in cells]
    assert "My Diagram" in labels
    assert "Architecture Overview" in labels


def test_add_title_no_subtitle() -> None:
    """add_title with no subtitle should create one cell."""
    diagram(action="create", name="titled2")
    result = json.loads(draw(action="add_title", diagram_name="titled2",
                             title="Simple Title"))
    assert len(result) == 1


def test_auto_connect() -> None:
    """smart_connect should create edges for all connection pairs."""
    diagram(action="create", name="autoconn")
    ids = json.loads(draw(action="add_vertices", diagram_name="autoconn", vertices=[
        {"label": "A", "x": 50, "y": 50},
        {"label": "B", "x": 200, "y": 50},
        {"label": "C", "x": 350, "y": 50},
    ]))
    a, b, c = ids[0], ids[1], ids[2]
    edge_ids = json.loads(layout(action="smart_connect", diagram_name="autoconn",
                                 connections=[
                                     {"source_id": a, "target_id": b, "label": "flow"},
                                     {"source_id": b, "target_id": c},
                                 ]))
    assert len(edge_ids) == 2
    cells = json.loads(inspect(action="cells", diagram_name="autoconn"))
    edges = [c for c in cells if c.get("type") == "edge"]
    assert len(edges) == 2
    # Should use ROUNDED style by default
    for e in edges:
        assert "rounded=1" in e["style"]


def test_arch_presets_resolve() -> None:
    """ARCH_* presets should resolve and contain colors."""
    diagram(action="create", name="arch")
    ids = json.loads(draw(action="add_vertices", diagram_name="arch", vertices=[
        {"label": "DB", "x": 50, "y": 50, "style_preset": "ARCH_DATABASE"},
        {"label": "API", "x": 200, "y": 50, "style_preset": "ARCH_SERVICE"},
    ]))
    cells = json.loads(inspect(action="cells", diagram_name="arch"))
    db_cell = next(c for c in cells if c["id"] == ids[0])
    svc_cell = next(c for c in cells if c["id"] == ids[1])
    assert "cylinder3" in db_cell["style"]
    assert "#dae8fc" in db_cell["style"]
    assert "#dae8fc" in svc_cell["style"]


def test_colored_edge_presets() -> None:
    """COLORED_* edge presets should resolve properly."""
    diagram(action="create", name="cedge")
    ids = json.loads(draw(action="add_vertices", diagram_name="cedge", vertices=[
        {"label": "A", "x": 50, "y": 50},
        {"label": "B", "x": 200, "y": 50},
    ]))
    a, b = ids[0], ids[1]
    eid = json.loads(draw(action="add_edges", diagram_name="cedge", edges=[
        {"source_id": a, "target_id": b, "style_preset": "COLORED_BLUE"},
    ]))[0]
    cells = json.loads(inspect(action="cells", diagram_name="cedge"))
    edge = next(c for c in cells if c["id"] == eid)
    assert "#6c8ebf" in edge["style"]


# ===================================================================
# Auto-sizing tests
# ===================================================================

def test_auto_size_short_label() -> None:
    """Short labels should keep default 120 width."""
    diagram(action="create", name="asize1")
    cid = json.loads(draw(action="add_vertices", diagram_name="asize1", vertices=[
        {"label": "OK", "x": 50, "y": 50},
    ]))[0]
    cells = json.loads(inspect(action="cells", diagram_name="asize1"))
    cell = next(c for c in cells if c["id"] == cid)
    assert cell["position"]["width"] == 120  # min width


def test_auto_size_long_label() -> None:
    """Long multi-line labels should get larger size."""
    diagram(action="create", name="asize2")
    label = "<b>Server Component</b><br>Handles all API requests<br>Rate limiting<br>Authentication"
    cid = json.loads(draw(action="add_vertices", diagram_name="asize2", vertices=[
        {"label": label, "x": 50, "y": 50},
    ]))[0]
    cells = json.loads(inspect(action="cells", diagram_name="asize2"))
    cell = next(c for c in cells if c["id"] == cid)
    # Should be taller than default 60
    assert cell["position"]["height"] > 60


def test_explicit_size_not_overridden() -> None:
    """Explicitly set width/height should not be auto-sized."""
    diagram(action="create", name="asize3")
    cid = json.loads(draw(action="add_vertices", diagram_name="asize3", vertices=[
        {"label": "Very long label text here", "x": 50, "y": 50, "width": 80, "height": 40},
    ]))[0]
    cells = json.loads(inspect(action="cells", diagram_name="asize3"))
    cell = next(c for c in cells if c["id"] == cid)
    assert cell["position"]["width"] == 80
    assert cell["position"]["height"] == 40


# ===================================================================
# Edge parent auto-resolution tests
# ===================================================================

def test_edge_parent_resolved_in_group() -> None:
    """Edge between cells in the same group should have group as parent."""
    diagram(action="create", name="ep1")
    gid = draw(action="add_group", diagram_name="ep1", group_label="G",
               group_x=50, group_y=50, group_width=300, group_height=200)
    ids = json.loads(draw(action="add_vertices", diagram_name="ep1", vertices=[
        {"label": "A", "x": 80, "y": 100, "parent_id": gid},
        {"label": "B", "x": 200, "y": 100, "parent_id": gid},
    ]))
    a, b = ids[0], ids[1]
    eid = json.loads(draw(action="add_edges", diagram_name="ep1", edges=[
        {"source_id": a, "target_id": b},
    ]))[0]
    cells = json.loads(inspect(action="cells", diagram_name="ep1"))
    edge = next(c for c in cells if c["id"] == eid)
    assert edge["parent"] == gid


def test_edge_parent_cross_group() -> None:
    """Edge between cells in different groups should use root layer."""
    diagram(action="create", name="ep2")
    g1 = draw(action="add_group", diagram_name="ep2", group_label="G1",
              group_x=50, group_y=50, group_width=200, group_height=150)
    g2 = draw(action="add_group", diagram_name="ep2", group_label="G2",
              group_x=300, group_y=50, group_width=200, group_height=150)
    ids1 = json.loads(draw(action="add_vertices", diagram_name="ep2", vertices=[
        {"label": "A", "x": 100, "y": 100, "parent_id": g1},
    ]))
    ids2 = json.loads(draw(action="add_vertices", diagram_name="ep2", vertices=[
        {"label": "B", "x": 400, "y": 100, "parent_id": g2},
    ]))
    a, b = ids1[0], ids2[0]
    eid = json.loads(draw(action="add_edges", diagram_name="ep2", edges=[
        {"source_id": a, "target_id": b},
    ]))[0]
    cells = json.loads(inspect(action="cells", diagram_name="ep2"))
    edge = next(c for c in cells if c["id"] == eid)
    assert edge["parent"] == "1"  # root layer


# ===================================================================
# Legend tool tests
# ===================================================================

def test_add_legend() -> None:
    """add_legend should create a stacked legend container."""
    diagram(action="create", name="leg1")
    lid = draw(action="add_legend", diagram_name="leg1", legend_entries=[
        {"label": "Service", "fill_color": "#dae8fc", "stroke_color": "#6c8ebf"},
        {"label": "Database", "fill_color": "#d5e8d4", "stroke_color": "#82b366"},
    ])
    cells = json.loads(inspect(action="cells", diagram_name="leg1"))
    legend_cell = next(c for c in cells if c["id"] == lid)
    assert "stackLayout" in legend_cell["style"]
    # Check children exist
    children = [c for c in cells if c.get("parent") == lid]
    assert len(children) == 2


def test_default_edge_style_is_orthogonal() -> None:
    """Default edge style should now be orthogonal+rounded."""
    diagram(action="create", name="defedge")
    ids = json.loads(draw(action="add_vertices", diagram_name="defedge", vertices=[
        {"label": "A", "x": 50, "y": 50},
        {"label": "B", "x": 300, "y": 200},
    ]))
    a, b = ids[0], ids[1]
    eid = json.loads(draw(action="add_edges", diagram_name="defedge", edges=[
        {"source_id": a, "target_id": b},
    ]))[0]
    cells = json.loads(inspect(action="cells", diagram_name="defedge"))
    edge = next(c for c in cells if c["id"] == eid)
    assert "orthogonalEdgeStyle" in edge["style"]
    assert "rounded=1" in edge["style"]


# ===================================================================
# New tests: snap-to-grid
# ===================================================================

def test_snap_to_grid_vertex() -> None:
    """Vertices should snap their position to the grid."""
    diagram(action="create", name="snap1")
    vid = json.loads(draw(action="add_vertices", diagram_name="snap1", vertices=[
        {"label": "Test", "x": 53, "y": 77},
    ]))[0]
    cells = json.loads(inspect(action="cells", diagram_name="snap1"))
    vertex = next(c for c in cells if c["id"] == vid)
    pos = vertex["position"]
    # Default grid is 10px, so 53→50, 77→80
    assert pos["x"] == 50
    assert pos["y"] == 80


def test_snap_to_grid_group() -> None:
    """Groups should snap their position to the grid."""
    diagram(action="create", name="snapgrp")
    gid = draw(action="add_group", diagram_name="snapgrp", group_label="Group",
               group_x=123, group_y=456)
    cells = json.loads(inspect(action="cells", diagram_name="snapgrp"))
    group = next(c for c in cells if c["id"] == gid)
    pos = group["position"]
    assert pos["x"] == 120
    assert pos["y"] == 460


# ===================================================================
# New tests: smart ports
# ===================================================================

def test_smart_ports_horizontal() -> None:
    """When target is to the right, exit should be RIGHT, entry LEFT."""
    diagram(action="create", name="port1")
    ids = json.loads(draw(action="add_vertices", diagram_name="port1", vertices=[
        {"label": "A", "x": 50, "y": 100},
        {"label": "B", "x": 400, "y": 100},
    ]))
    a, b = ids[0], ids[1]
    eid = json.loads(draw(action="add_edges", diagram_name="port1", edges=[
        {"source_id": a, "target_id": b},
    ]))[0]
    cells = json.loads(inspect(action="cells", diagram_name="port1"))
    edge = next(c for c in cells if c["id"] == eid)
    # Should have exitX=1 (right) and entryX=0 (left)
    assert "exitX=1" in edge["style"]
    assert "entryX=0" in edge["style"]


def test_smart_ports_vertical() -> None:
    """When target is below, exit should be BOTTOM, entry TOP."""
    diagram(action="create", name="port2")
    ids = json.loads(draw(action="add_vertices", diagram_name="port2", vertices=[
        {"label": "A", "x": 100, "y": 50},
        {"label": "B", "x": 100, "y": 400},
    ]))
    a, b = ids[0], ids[1]
    eid = json.loads(draw(action="add_edges", diagram_name="port2", edges=[
        {"source_id": a, "target_id": b},
    ]))[0]
    cells = json.loads(inspect(action="cells", diagram_name="port2"))
    edge = next(c for c in cells if c["id"] == eid)
    assert "exitY=1" in edge["style"]
    assert "entryY=0" in edge["style"]


def test_explicit_ports() -> None:
    """Explicit exit_port/entry_port should override smart ports."""
    diagram(action="create", name="port3")
    ids = json.loads(draw(action="add_vertices", diagram_name="port3", vertices=[
        {"label": "A", "x": 50, "y": 50},
        {"label": "B", "x": 300, "y": 300},
    ]))
    a, b = ids[0], ids[1]
    eid = json.loads(draw(action="add_edges", diagram_name="port3", edges=[
        {"source_id": a, "target_id": b, "exit_port": "BOTTOM", "entry_port": "TOP"},
    ]))[0]
    cells = json.loads(inspect(action="cells", diagram_name="port3"))
    edge = next(c for c in cells if c["id"] == eid)
    assert "exitX=0.5" in edge["style"]
    assert "exitY=1" in edge["style"]
    assert "entryX=0.5" in edge["style"]
    assert "entryY=0" in edge["style"]


# ===================================================================
# New tests: align_cells
# ===================================================================

def test_align_cells_center() -> None:
    """align should center-align shapes."""
    diagram(action="create", name="align1")
    ids = json.loads(draw(action="add_vertices", diagram_name="align1", vertices=[
        {"label": "A", "x": 50, "y": 50, "width": 100},
        {"label": "B", "x": 200, "y": 150, "width": 100},
        {"label": "C", "x": 120, "y": 250, "width": 100},
    ]))
    a, b, c = ids[0], ids[1], ids[2]
    result = layout(action="align", diagram_name="align1",
                    cell_ids=[a, b, c], alignment="center")
    assert "3 cells" in result
    cells = json.loads(inspect(action="cells", diagram_name="align1"))
    xs = [cell["position"]["x"] for cell in cells
          if cell["id"] in (a, b, c)]
    # All center x should be the same (within grid snap)
    centers = [x + 50 for x in xs]  # width=100, center = x + 50
    assert max(centers) - min(centers) <= 10  # within grid snap


def test_align_cells_top() -> None:
    """align should top-align shapes."""
    diagram(action="create", name="align2")
    ids = json.loads(draw(action="add_vertices", diagram_name="align2", vertices=[
        {"label": "A", "x": 50, "y": 100},
        {"label": "B", "x": 200, "y": 200},
    ]))
    a, b = ids[0], ids[1]
    result = layout(action="align", diagram_name="align2",
                    cell_ids=[a, b], alignment="top")
    assert "2 cells" in result
    cells = json.loads(inspect(action="cells", diagram_name="align2"))
    vertex_a = next(c for c in cells if c["id"] == a)
    vertex_b = next(c for c in cells if c["id"] == b)
    assert vertex_a["position"]["y"] == vertex_b["position"]["y"]


# ===================================================================
# New tests: distribute_cells
# ===================================================================

def test_distribute_cells_horizontal() -> None:
    """distribute should space shapes evenly."""
    diagram(action="create", name="dist1")
    ids = json.loads(draw(action="add_vertices", diagram_name="dist1", vertices=[
        {"label": "A", "x": 50, "y": 100, "width": 100},
        {"label": "B", "x": 100, "y": 100, "width": 100},  # clustered
        {"label": "C", "x": 500, "y": 100, "width": 100},
    ]))
    a, b, c_id = ids[0], ids[1], ids[2]
    result = layout(action="distribute", diagram_name="dist1",
                    cell_ids=[a, b, c_id], dist_direction="horizontal")
    assert "3 cells" in result
    cells = json.loads(inspect(action="cells", diagram_name="dist1"))
    target_ids = (a, b, c_id)
    positions = sorted(
        [cell["position"]["x"] for cell in cells if cell["id"] in target_ids]
    )
    # Gaps should be approximately equal
    gap1 = positions[1] - positions[0]
    gap2 = positions[2] - positions[1]
    assert abs(gap1 - gap2) <= 10  # within grid snap


# ===================================================================
# New tests: smart_connect
# ===================================================================

def test_smart_connect() -> None:
    """smart_connect should create edges with port constraints."""
    diagram(action="create", name="sconn1")
    ids = json.loads(draw(action="add_vertices", diagram_name="sconn1", vertices=[
        {"label": "A", "x": 50, "y": 50},
        {"label": "B", "x": 400, "y": 50},
        {"label": "C", "x": 200, "y": 300},
    ]))
    a, b, c = ids[0], ids[1], ids[2]
    edge_ids = json.loads(layout(action="smart_connect", diagram_name="sconn1",
                                 connections=[
                                     {"source_id": a, "target_id": b},
                                     {"source_id": a, "target_id": c},
                                 ]))
    assert len(edge_ids) == 2
    cells = json.loads(inspect(action="cells", diagram_name="sconn1"))
    edges = [cell for cell in cells if cell.get("type") == "edge"]
    assert len(edges) == 2
    # All edges should have exit/entry constraints
    for edge in edges:
        assert "exitX=" in edge["style"]
        assert "entryX=" in edge["style"]


def test_smart_connect_distributes_ports() -> None:
    """When multiple edges share the same source side, ports should be distributed."""
    diagram(action="create", name="sconn_dist")
    # Source on left, three targets on right — all should exit RIGHT side
    ids = json.loads(draw(action="add_vertices", diagram_name="sconn_dist", vertices=[
        {"label": "Source", "x": 50, "y": 200},
        {"label": "T1", "x": 400, "y": 50},
        {"label": "T2", "x": 400, "y": 200},
        {"label": "T3", "x": 400, "y": 350},
    ]))
    src, t1, t2, t3 = ids[0], ids[1], ids[2], ids[3]
    edge_ids = json.loads(layout(action="smart_connect", diagram_name="sconn_dist",
                                 connections=[
                                     {"source_id": src, "target_id": t1},
                                     {"source_id": src, "target_id": t2},
                                     {"source_id": src, "target_id": t3},
                                 ]))
    assert len(edge_ids) == 3
    cells = json.loads(inspect(action="cells", diagram_name="sconn_dist"))
    edges = [cell for cell in cells if cell.get("type") == "edge"]
    # All exit from RIGHT side (exitX=1)
    exit_ys = []
    for edge in edges:
        assert "exitX=1" in edge["style"]
        # Extract exitY values — they should be DIFFERENT (distributed)
        for part in edge["style"].split(";"):
            if part.startswith("exitY="):
                exit_ys.append(float(part.split("=")[1]))
    assert len(set(exit_ys)) == 3, f"Expected 3 different exitY values, got {exit_ys}"


def test_smart_connect_with_waypoints() -> None:
    """smart_connect should compute obstacle-avoiding paths."""
    diagram(action="create", name="sconn2")
    ids = json.loads(draw(action="add_vertices", diagram_name="sconn2", vertices=[
        {"label": "A", "x": 50, "y": 50},
        {"label": "Obstacle", "x": 250, "y": 100, "width": 100, "height": 100},
        {"label": "B", "x": 500, "y": 50},
    ]))
    a, _, b = ids[0], ids[1], ids[2]
    edge_ids = json.loads(layout(action="smart_connect", diagram_name="sconn2",
                                 connections=[
                                     {"source_id": a, "target_id": b},
                                 ]))
    assert len(edge_ids) == 1


# ===================================================================
# New tests: resize_container_to_fit
# ===================================================================

def test_resize_container_to_fit() -> None:
    """resize_container should auto-size container to wrap children."""
    diagram(action="create", name="rcf1")
    gid = draw(action="add_group", diagram_name="rcf1", group_label="Container",
               group_x=50, group_y=50, group_width=200, group_height=100)
    draw(action="add_vertices", diagram_name="rcf1", vertices=[
        {"label": "Child1", "x": 70, "y": 90, "parent_id": gid},
        {"label": "Child2", "x": 70, "y": 170, "parent_id": gid},
    ])
    result = layout(action="resize_container", diagram_name="rcf1",
                    container_id=gid)
    assert "resized" in result
    cells = json.loads(inspect(action="cells", diagram_name="rcf1"))
    container = next(c for c in cells if c["id"] == gid)
    # Container should be large enough to fit children
    assert container["position"]["width"] >= 140
    assert container["position"]["height"] >= 150


# ===================================================================
# New tests: list_ports
# ===================================================================

def test_list_ports() -> None:
    """list_ports should return port presets."""
    result = inspect(action="ports")
    assert "TOP" in result
    assert "BOTTOM" in result
    assert "LEFT" in result
    assert "RIGHT" in result


# ===================================================================
# New tests: crossing minimization in tree layout
# ===================================================================

def test_tree_layout_crossing_minimization() -> None:
    """Tree layout should minimize crossings via barycenter heuristic."""
    diagram(action="create", name="crossing1")
    adjacency = {
        "Root": ["A", "B"],
        "A": ["D", "C"],  # intentionally reversed
        "B": ["E", "F"],
    }
    result = json.loads(layout(action="tree", diagram_name="crossing1",
                               adjacency=adjacency, root="Root"))
    assert "Root" in result
    assert len(result) == 7  # Root + A + B + C + D + E + F

    # Verify all nodes are placed
    cells = json.loads(inspect(action="cells", diagram_name="crossing1"))
    labels = [c.get("label", "") for c in cells if c.get("type") == "vertex"]
    for node in ["Root", "A", "B", "C", "D", "E", "F"]:
        assert node in labels


# ===========================================================================
# Layer support
# ===========================================================================

def test_add_layer_via_diagram_tool() -> None:
    """The diagram(action='add_layer') creates a layer cell."""
    diagram(action="create", name="layer_test")
    result = json.loads(diagram(action="add_layer", name="layer_test", page_name="Background"))
    assert "layer_id" in result
    assert result["name"] == "Background"

    # Inspect should show the layer
    info = json.loads(inspect(action="info", diagram_name="layer_test"))
    assert info["pages"][0]["layers"] == 2  # default layer "1" + new layer


def test_vertex_on_custom_layer() -> None:
    """Vertices can be placed on a custom layer."""
    diagram(action="create", name="layer2")
    result = json.loads(diagram(action="add_layer", name="layer2", page_name="Overlay"))
    lid = result["layer_id"]

    ids = json.loads(draw(action="add_vertices", diagram_name="layer2", vertices=[
        {"label": "On overlay", "x": 100, "y": 100, "parent_id": lid},
    ]))
    cells = json.loads(inspect(action="cells", diagram_name="layer2"))
    vertex = next(c for c in cells if c["id"] == ids[0])
    assert vertex["parent"] == lid


def test_inspect_shows_layer_type() -> None:
    """inspect(action='cells') identifies layers correctly."""
    diagram(action="create", name="layer3")
    diagram(action="add_layer", name="layer3", page_name="My Layer")
    cells = json.loads(inspect(action="cells", diagram_name="layer3"))
    layer_cells = [c for c in cells if c.get("type") == "layer"]
    assert len(layer_cells) == 2  # default "1" + "My Layer"


# ===========================================================================
# Metadata support (tooltip, link, custom properties)
# ===========================================================================

def test_add_vertex_with_tooltip() -> None:
    """Vertices can have tooltips via metadata."""
    diagram(action="create", name="meta1")
    ids = json.loads(draw(action="add_vertices", diagram_name="meta1", vertices=[
        {"label": "Hover me", "x": 100, "y": 100, "tooltip": "My tooltip"},
    ]))
    xml = diagram(action="get_xml", name="meta1")
    assert "tooltip" in xml
    assert "My tooltip" in xml
    assert "<object" in xml


def test_add_vertex_with_link() -> None:
    """Vertices can have clickable links."""
    diagram(action="create", name="meta2")
    ids = json.loads(draw(action="add_vertices", diagram_name="meta2", vertices=[
        {"label": "Click me", "x": 100, "y": 100, "link": "https://example.com"},
    ]))
    xml = diagram(action="get_xml", name="meta2")
    assert "https://example.com" in xml


def test_add_vertex_with_custom_metadata() -> None:
    """Vertices can have arbitrary metadata attributes."""
    diagram(action="create", name="meta3")
    ids = json.loads(draw(action="add_vertices", diagram_name="meta3", vertices=[
        {"label": "Subnet", "x": 100, "y": 100,
         "metadata": {"subnet": "10.0.0.0/24", "region": "us-east-1"}},
    ]))
    xml = diagram(action="get_xml", name="meta3")
    assert 'subnet="10.0.0.0/24"' in xml
    assert 'region="us-east-1"' in xml


def test_inspect_shows_metadata() -> None:
    """inspect(action='cells') includes metadata in output."""
    diagram(action="create", name="meta4")
    draw(action="add_vertices", diagram_name="meta4", vertices=[
        {"label": "Node", "x": 100, "y": 100, "tooltip": "tip", "link": "http://x.com"},
    ])
    cells = json.loads(inspect(action="cells", diagram_name="meta4"))
    vertex = next(c for c in cells if c.get("label") == "Node")
    assert vertex.get("tooltip") == "tip"
    assert vertex.get("link") == "http://x.com"


# ===========================================================================
# Import with <object> wrapper elements
# ===========================================================================

def test_import_xml_with_object_wrapper() -> None:
    """Import correctly parses <object> wrappers with metadata."""
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
    <mxfile host="test">
      <diagram name="test" id="t1">
        <mxGraphModel>
          <root>
            <mxCell id="0"/>
            <mxCell id="1" parent="0"/>
            <object label="Server" id="2" tooltip="Main server" link="https://server.com" env="production">
              <mxCell style="rounded=1;whiteSpace=wrap;html=1;" parent="1" vertex="1">
                <mxGeometry as="geometry" x="100" y="100" width="120" height="60"/>
              </mxCell>
            </object>
          </root>
        </mxGraphModel>
      </diagram>
    </mxfile>'''
    result = diagram(action="import_xml", name="obj_import", xml_content=xml_content)
    assert "Imported" in result

    cells = json.loads(inspect(action="cells", diagram_name="obj_import"))
    server = next(c for c in cells if c.get("label") == "Server")
    assert server["tooltip"] == "Main server"
    assert server["link"] == "https://server.com"
    assert server["metadata"]["env"] == "production"


def test_import_xml_with_user_object() -> None:
    """Import also handles <UserObject> (alternative to <object>)."""
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
    <mxfile host="test">
      <diagram name="test" id="t1">
        <mxGraphModel>
          <root>
            <mxCell id="0"/>
            <mxCell id="1" parent="0"/>
            <UserObject label="Database" id="3" tooltip="Primary DB">
              <mxCell style="shape=cylinder3;" parent="1" vertex="1">
                <mxGeometry as="geometry" x="200" y="200" width="100" height="80"/>
              </mxCell>
            </UserObject>
          </root>
        </mxGraphModel>
      </diagram>
    </mxfile>'''
    result = diagram(action="import_xml", name="uo_import", xml_content=xml_content)
    assert "Imported" in result
    cells = json.loads(inspect(action="cells", diagram_name="uo_import"))
    db = next(c for c in cells if c.get("label") == "Database")
    assert db["tooltip"] == "Primary DB"


# ===========================================================================
# mxfile attributes
# ===========================================================================

def test_xml_contains_mxfile_attributes() -> None:
    """Generated XML includes modified, agent, version attributes."""
    diagram(action="create", name="attrs_test")
    xml = diagram(action="get_xml", name="attrs_test")
    assert 'agent="drawio-mcp/1.0"' in xml
    assert 'modified=' in xml
    assert 'version=' in xml
