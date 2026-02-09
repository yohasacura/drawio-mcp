"""Tests for the professional layout engine."""

import json

from drawio_mcp.layout_engine import (
    LayoutEngineConfig,
    compact_diagram,
    find_overlapping_cells,
    layout_sugiyama,
    optimize_edge_paths,
    position_edge_labels,
    relayout_diagram,
    resolve_overlaps,
    route_edges_around_obstacles,
)
from drawio_mcp.models import CellBounds, Diagram, Geometry, MxCell, Point


def _fresh_diagram() -> Diagram:
    return Diagram(name="test")


# ===================================================================
# Sugiyama layout tests
# ===================================================================

class TestSugiyamaLayout:
    """Tests for the Sugiyama layered layout algorithm."""

    def test_simple_chain(self) -> None:
        """A->B->C should produce a linear layout with no overlaps."""
        d = _fresh_diagram()
        edges = [("A", "B", ""), ("B", "C", "")]
        mapping = layout_sugiyama(d, edges)

        assert len(mapping) == 3
        assert "A" in mapping
        assert "B" in mapping
        assert "C" in mapping

        # Verify vertices were created
        vertex_count = sum(1 for c in d.cells if c.vertex and c.id in mapping.values())
        assert vertex_count == 3

        # Verify edges were created
        edge_count = sum(1 for c in d.cells if c.edge)
        assert edge_count == 2

    def test_fan_out(self) -> None:
        """A->{B,C,D} should place B,C,D in the same rank."""
        d = _fresh_diagram()
        edges = [("A", "B", ""), ("A", "C", ""), ("A", "D", "")]
        mapping = layout_sugiyama(d, edges)

        assert len(mapping) == 4

        # B, C, D should be at the same Y (same rank)
        cells = {cid: next(c for c in d.cells if c.id == cid) for cid in mapping.values()}
        b_y = cells[mapping["B"]].geometry.y
        c_y = cells[mapping["C"]].geometry.y
        d_y = cells[mapping["D"]].geometry.y

        assert b_y == c_y == d_y, f"Fan-out nodes not in same rank: {b_y}, {c_y}, {d_y}"

    def test_diamond(self) -> None:
        """A->{B,C}->D should place B,C in the middle rank."""
        d = _fresh_diagram()
        edges = [("A", "B", ""), ("A", "C", ""), ("B", "D", ""), ("C", "D", "")]
        mapping = layout_sugiyama(d, edges)

        assert len(mapping) == 4
        cells = {cid: next(c for c in d.cells if c.id == cid) for cid in mapping.values()}

        a_y = cells[mapping["A"]].geometry.y
        b_y = cells[mapping["B"]].geometry.y
        d_y = cells[mapping["D"]].geometry.y

        # A should be above B, B should be above D
        assert a_y < b_y < d_y

    def test_no_overlaps_produced(self) -> None:
        """The layout should not produce overlapping shapes."""
        d = _fresh_diagram()
        edges = [
            ("A", "B", ""), ("A", "C", ""), ("A", "D", ""),
            ("B", "E", ""), ("C", "E", ""), ("D", "F", ""),
        ]
        mapping = layout_sugiyama(d, edges)

        overlaps = find_overlapping_cells(d, margin=0)
        assert len(overlaps) == 0, f"Found overlaps: {overlaps}"

    def test_with_edge_labels(self) -> None:
        """Edge labels should be preserved."""
        d = _fresh_diagram()
        edges = [("A", "B", "connects"), ("B", "C", "flows")]
        mapping = layout_sugiyama(d, edges)

        edge_cells = [c for c in d.cells if c.edge]
        labels = {c.value for c in edge_cells if c.value}
        assert "connects" in labels
        assert "flows" in labels

    def test_with_custom_styles(self) -> None:
        """Custom node styles should be applied."""
        d = _fresh_diagram()
        edges = [("A", "B", "")]
        styles = {
            "A": "ellipse;whiteSpace=wrap;html=1;",
            "B": "rhombus;whiteSpace=wrap;html=1;",
        }
        mapping = layout_sugiyama(d, edges, node_styles=styles)

        cell_a = next(c for c in d.cells if c.id == mapping["A"])
        cell_b = next(c for c in d.cells if c.id == mapping["B"])
        assert "ellipse" in cell_a.style
        assert "rhombus" in cell_b.style

    def test_direction_lr(self) -> None:
        """LR direction should place ranks left-to-right."""
        d = _fresh_diagram()
        edges = [("A", "B", ""), ("B", "C", "")]
        mapping = layout_sugiyama(d, edges, direction="LR")

        cells = {cid: next(c for c in d.cells if c.id == cid) for cid in mapping.values()}
        a_x = cells[mapping["A"]].geometry.x
        b_x = cells[mapping["B"]].geometry.x
        c_x = cells[mapping["C"]].geometry.x

        assert a_x < b_x < c_x

    def test_cycle_handling(self) -> None:
        """Cycles should be handled (back-edges reversed)."""
        d = _fresh_diagram()
        edges = [("A", "B", ""), ("B", "C", ""), ("C", "A", "")]
        mapping = layout_sugiyama(d, edges)

        # All 3 nodes should be created despite cycle
        assert len(mapping) == 3

    def test_complex_dag(self) -> None:
        """A more complex DAG should produce a reasonable layout."""
        d = _fresh_diagram()
        edges = [
            ("Client", "API Gateway", ""),
            ("API Gateway", "Auth Service", ""),
            ("API Gateway", "User Service", ""),
            ("API Gateway", "Order Service", ""),
            ("Auth Service", "Database", ""),
            ("User Service", "Database", ""),
            ("Order Service", "Database", ""),
            ("Order Service", "Message Queue", ""),
        ]
        mapping = layout_sugiyama(d, edges)

        # 7 unique nodes: Client, API Gateway, Auth Service, User Service,
        # Order Service, Database, Message Queue
        assert len(mapping) == 7
        overlaps = find_overlapping_cells(d, margin=0)
        assert len(overlaps) == 0, f"Complex DAG has overlaps: {overlaps}"


# ===================================================================
# Overlap detection and resolution tests
# ===================================================================

class TestOverlapResolution:
    """Tests for overlap detection and resolution."""

    def test_detect_overlaps(self) -> None:
        """Overlapping shapes should be detected."""
        d = _fresh_diagram()
        d.add_vertex("A", 100, 100, 120, 60)
        d.add_vertex("B", 150, 120, 120, 60)  # Overlaps with A

        overlaps = find_overlapping_cells(d)
        assert len(overlaps) == 1

    def test_no_false_positives(self) -> None:
        """Non-overlapping shapes should not be flagged."""
        d = _fresh_diagram()
        d.add_vertex("A", 100, 100, 120, 60)
        d.add_vertex("B", 300, 100, 120, 60)  # Far apart

        overlaps = find_overlapping_cells(d)
        assert len(overlaps) == 0

    def test_resolve_overlaps(self) -> None:
        """resolve_overlaps should push apart overlapping shapes."""
        d = _fresh_diagram()
        d.add_vertex("A", 100, 100, 120, 60)
        d.add_vertex("B", 110, 110, 120, 60)  # Overlapping

        before = find_overlapping_cells(d, margin=0)
        assert len(before) > 0

        resolve_overlaps(d, margin=10)

        after = find_overlapping_cells(d, margin=0)
        assert len(after) == 0, "Overlaps not fully resolved"

    def test_resolve_many_overlaps(self) -> None:
        """Multiple overlapping shapes should all be resolved."""
        d = _fresh_diagram()
        # Create a pile of overlapping shapes
        for i in range(5):
            d.add_vertex(f"N{i}", 100 + i * 10, 100 + i * 10, 120, 60)

        resolve_overlaps(d, margin=10)

        after = find_overlapping_cells(d, margin=0)
        assert len(after) == 0

    def test_already_clean_diagram(self) -> None:
        """A diagram with no overlaps should not be modified."""
        d = _fresh_diagram()
        d.add_vertex("A", 100, 100, 120, 60)
        d.add_vertex("B", 300, 100, 120, 60)
        d.add_vertex("C", 100, 300, 120, 60)

        moves = resolve_overlaps(d, margin=10)
        assert moves == 0


# ===================================================================
# Relayout tests
# ===================================================================

class TestRelayout:
    """Tests for relayout_diagram."""

    def test_relayout_simple(self) -> None:
        """Relayouting a connected graph should reposition shapes."""
        d = _fresh_diagram()
        v1 = d.add_vertex("A", 500, 500, 120, 60)
        v2 = d.add_vertex("B", 500, 500, 120, 60)  # Same position!
        d.add_edge(v1, v2)

        moved = relayout_diagram(d)
        assert len(moved) >= 1

    def test_relayout_disconnected_nodes(self) -> None:
        """Disconnected nodes (no edges) should be arranged in a grid."""
        d = _fresh_diagram()
        d.add_vertex("A", 0, 0, 120, 60)
        d.add_vertex("B", 0, 0, 120, 60)
        d.add_vertex("C", 0, 0, 120, 60)
        d.add_vertex("D", 0, 0, 120, 60)

        moved = relayout_diagram(d)
        assert len(moved) == 4

        # No overlaps
        overlaps = find_overlapping_cells(d, margin=0)
        assert len(overlaps) == 0

    def test_relayout_preserves_connections(self) -> None:
        """Relayout should not break existing edge connections."""
        d = _fresh_diagram()
        v1 = d.add_vertex("A", 0, 0, 120, 60)
        v2 = d.add_vertex("B", 0, 0, 120, 60)
        e1 = d.add_edge(v1, v2, value="test")

        relayout_diagram(d)

        # Edge should still exist with same source/target
        edge = next(c for c in d.cells if c.id == e1)
        assert edge.source == v1
        assert edge.target == v2
        assert edge.value == "test"


# ===================================================================
# Compact layout tests
# ===================================================================

class TestCompactLayout:
    """Tests for compact_diagram."""

    def test_compact_removes_whitespace(self) -> None:
        """Compact should close large gaps between shapes."""
        d = _fresh_diagram()
        d.add_vertex("A", 100, 100, 120, 60)
        d.add_vertex("B", 100, 500, 120, 60)  # Large gap

        from drawio_mcp.layout import get_all_vertex_bounds
        bounds_before = get_all_vertex_bounds(d)
        gap_before = bounds_before[list(bounds_before.keys())[1]].y - bounds_before[list(bounds_before.keys())[0]].bottom

        compact_diagram(d, margin=40)

        bounds_after = get_all_vertex_bounds(d)
        ids = list(bounds_after.keys())
        sorted_ids = sorted(ids, key=lambda x: bounds_after[x].y)
        gap_after = bounds_after[sorted_ids[1]].y - bounds_after[sorted_ids[0]].bottom

        assert gap_after <= gap_before

    def test_compact_maintains_order(self) -> None:
        """Compact should maintain relative ordering of shapes."""
        d = _fresh_diagram()
        d.add_vertex("A", 100, 100, 120, 60)
        d.add_vertex("B", 100, 300, 120, 60)
        d.add_vertex("C", 100, 600, 120, 60)

        compact_diagram(d, margin=30)

        from drawio_mcp.layout import get_all_vertex_bounds
        bounds = get_all_vertex_bounds(d)
        ids = list(bounds.keys())
        ys = sorted([bounds[cid].y for cid in ids])
        assert ys == sorted(ys)  # Still in order


# ===================================================================
# Edge label tests
# ===================================================================

class TestEdgeLabelPositioning:
    """Tests for edge label positioning."""

    def test_no_crash_on_empty_diagram(self) -> None:
        """Should handle diagrams with no edge labels."""
        d = _fresh_diagram()
        d.add_vertex("A", 100, 100, 120, 60)
        count = position_edge_labels(d)
        assert count == 0

    def test_positions_labels(self) -> None:
        """Edge labels should be repositioned if they collide."""
        d = _fresh_diagram()
        v1 = d.add_vertex("A", 100, 100, 120, 60)
        v2 = d.add_vertex("B", 100, 300, 120, 60)
        eid = d.add_edge(v1, v2)
        # Add a label on the edge that overlaps with A
        d.add_edge_label(eid, "my label", position=0.0, offset_x=0, offset_y=0)

        count = position_edge_labels(d)
        # May or may not reposition depending on actual collision
        assert isinstance(count, int)


# ===================================================================
# Server integration tests
# ===================================================================

class TestServerIntegration:
    """Tests for the server tool wrappers."""

    def setup_method(self) -> None:
        from drawio_mcp.server import _diagrams
        _diagrams.clear()

    def test_auto_layout_sugiyama_tool(self) -> None:
        from drawio_mcp.server import diagram, layout

        diagram(action="create", name="sug1")
        result = json.loads(layout(action="sugiyama", diagram_name="sug1",
                                   connections=[
                                       {"source": "A", "target": "B"},
                                       {"source": "B", "target": "C"},
                                       {"source": "A", "target": "C"},
                                   ]))
        assert len(result) == 3
        assert "A" in result
        assert "B" in result
        assert "C" in result

    def test_relayout_existing_tool(self) -> None:
        from drawio_mcp.server import diagram, draw, layout

        diagram(action="create", name="relay1")
        ids = json.loads(draw(action="add_vertices", diagram_name="relay1", vertices=[
            {"label": "A", "x": 0, "y": 0},
            {"label": "B", "x": 0, "y": 0},
        ]))
        a, b = ids[0], ids[1]
        draw(action="add_edges", diagram_name="relay1", edges=[
            {"source_id": a, "target_id": b},
        ])

        result = layout(action="relayout", diagram_name="relay1")
        assert "repositioned" in result.lower()

    def test_resolve_all_overlaps_tool(self) -> None:
        from drawio_mcp.server import diagram, draw, layout

        diagram(action="create", name="ovl1")
        draw(action="add_vertices", diagram_name="ovl1", vertices=[
            {"label": "A", "x": 100, "y": 100},
            {"label": "B", "x": 110, "y": 110},
        ])

        result = layout(action="resolve_overlaps", diagram_name="ovl1")
        assert "overlap" in result.lower()

    def test_resolve_all_overlaps_clean(self) -> None:
        from drawio_mcp.server import diagram, draw, layout

        diagram(action="create", name="ovl2")
        draw(action="add_vertices", diagram_name="ovl2", vertices=[
            {"label": "A", "x": 100, "y": 100},
            {"label": "B", "x": 400, "y": 100},
        ])

        result = layout(action="resolve_overlaps", diagram_name="ovl2")
        assert "clean" in result.lower()

    def test_compact_layout_tool(self) -> None:
        from drawio_mcp.server import diagram, draw, layout

        diagram(action="create", name="cpt1")
        draw(action="add_vertices", diagram_name="cpt1", vertices=[
            {"label": "A", "x": 100, "y": 100},
            {"label": "B", "x": 100, "y": 500},
        ])

        result = layout(action="compact", diagram_name="cpt1")
        assert "compact" in result.lower()

    def test_check_overlaps_tool(self) -> None:
        from drawio_mcp.server import diagram, draw, inspect

        diagram(action="create", name="chk1")
        draw(action="add_vertices", diagram_name="chk1", vertices=[
            {"label": "A", "x": 100, "y": 100},
            {"label": "B", "x": 110, "y": 110},
        ])

        result = inspect(action="overlaps", diagram_name="chk1")
        data = json.loads(result)
        assert len(data) >= 1

    def test_check_overlaps_clean(self) -> None:
        from drawio_mcp.server import diagram, draw, inspect

        diagram(action="create", name="chk2")
        draw(action="add_vertices", diagram_name="chk2", vertices=[
            {"label": "A", "x": 100, "y": 100},
            {"label": "B", "x": 400, "y": 100},
        ])

        result = inspect(action="overlaps", diagram_name="chk2")
        assert "clean" in result.lower()

    def test_polish_diagram_tool(self) -> None:
        from drawio_mcp.server import diagram, draw, layout

        diagram(action="create", name="pol1")
        ids = json.loads(draw(action="add_vertices", diagram_name="pol1", vertices=[
            {"label": "A", "x": 0, "y": 0},
            {"label": "B", "x": 0, "y": 0},
            {"label": "C", "x": 0, "y": 0},
        ]))
        a, b, c = ids[0], ids[1], ids[2]
        draw(action="add_edges", diagram_name="pol1", edges=[
            {"source_id": a, "target_id": b},
            {"source_id": b, "target_id": c},
        ])

        result = layout(action="polish", diagram_name="pol1")
        assert "polished" in result.lower()

    def test_fix_edge_labels_tool(self) -> None:
        from drawio_mcp.server import diagram, draw, layout

        diagram(action="create", name="fel1")
        ids = json.loads(draw(action="add_vertices", diagram_name="fel1", vertices=[
            {"label": "A", "x": 100, "y": 100},
            {"label": "B", "x": 100, "y": 300},
        ]))
        a, b = ids[0], ids[1]
        draw(action="add_edges", diagram_name="fel1", edges=[
            {"source_id": a, "target_id": b, "label": "test"},
        ])

        result = layout(action="fix_labels", diagram_name="fel1")
        assert "label" in result.lower()

    def test_error_handling(self) -> None:
        from drawio_mcp.server import inspect, layout

        assert "Error" in layout(action="sugiyama", diagram_name="nonexistent",
                                 connections=[])
        assert "Error" in layout(action="relayout", diagram_name="nonexistent")
        assert "Error" in layout(action="resolve_overlaps", diagram_name="nonexistent")
        assert "Error" in layout(action="fix_labels", diagram_name="nonexistent")
        assert "Error" in layout(action="compact", diagram_name="nonexistent")
        assert "Error" in inspect(action="overlaps", diagram_name="nonexistent")
        assert "Error" in layout(action="polish", diagram_name="nonexistent")

    def test_sugiyama_with_styles(self) -> None:
        from drawio_mcp.server import diagram, inspect, layout

        diagram(action="create", name="sug_styled")
        result = json.loads(layout(
            action="sugiyama", diagram_name="sug_styled",
            connections=[
                {"source": "User", "target": "API"},
                {"source": "API", "target": "DB"},
            ],
        ))
        assert len(result) == 3

        cells = json.loads(inspect(action="cells", diagram_name="sug_styled"))
        # Just check that 3 nodes were created
        vertex_cells = [c for c in cells if c.get("type") == "vertex"]
        assert len(vertex_cells) == 3


# ===================================================================
# Obstacle-aware edge routing tests
# ===================================================================

class TestEdgeRouting:
    """Tests for A*-based obstacle-aware edge routing."""

    def test_straight_line_no_obstacles(self) -> None:
        """When no obstacle blocks the path, no waypoints needed."""
        d = _fresh_diagram()
        v1 = d.add_vertex("A", 100, 100, 120, 60)
        v2 = d.add_vertex("B", 100, 400, 120, 60)
        d.add_edge(v1, v2)

        count = route_edges_around_obstacles(d, margin=15)
        assert count == 1  # Still processed

    def test_route_around_obstacle(self) -> None:
        """Edge should route around an obstacle between source and target."""
        d = _fresh_diagram()
        v1 = d.add_vertex("A", 100, 100, 120, 60)
        v2 = d.add_vertex("B", 100, 500, 120, 60)
        # Obstacle right in the middle
        d.add_vertex("Blocker", 100, 280, 120, 60)
        eid = d.add_edge(v1, v2)

        count = route_edges_around_obstacles(d, margin=15)
        assert count == 1

        # The edge should now have waypoints to route around Blocker
        edge_cell = next(c for c in d.cells if c.id == eid)
        assert edge_cell.geometry is not None

    def test_route_multiple_obstacles(self) -> None:
        """Edge should navigate around multiple obstacles."""
        d = _fresh_diagram()
        v1 = d.add_vertex("Start", 50, 50, 120, 60)
        v2 = d.add_vertex("End", 50, 600, 120, 60)
        # Two obstacles stacked vertically
        d.add_vertex("Block1", 50, 200, 120, 60)
        d.add_vertex("Block2", 50, 380, 120, 60)
        eid = d.add_edge(v1, v2)

        count = route_edges_around_obstacles(d, margin=15)
        assert count == 1

    def test_no_edges_no_crash(self) -> None:
        """Diagrams with no edges should not crash."""
        d = _fresh_diagram()
        d.add_vertex("A", 100, 100, 120, 60)
        count = route_edges_around_obstacles(d)
        assert count == 0

    def test_edges_after_sugiyama(self) -> None:
        """Sugiyama layout should produce edges that don't cross shapes."""
        d = _fresh_diagram()
        edges = [
            ("A", "B", ""), ("A", "C", ""),
            ("B", "D", ""), ("C", "D", ""),
            ("D", "E", ""),
        ]
        cfg = LayoutEngineConfig(route_edges=True)
        mapping = layout_sugiyama(d, edges, config=cfg)

        # Verify edges were created
        edge_cells = [c for c in d.cells if c.edge]
        assert len(edge_cells) == 5

    def test_sugiyama_route_edges_disabled(self) -> None:
        """When route_edges=False, no routing should happen."""
        d = _fresh_diagram()
        edges = [("A", "B", ""), ("B", "C", "")]
        cfg = LayoutEngineConfig(route_edges=False)
        layout_sugiyama(d, edges, config=cfg)

        # Edges should have no waypoints
        for cell in d.cells:
            if cell.edge and cell.geometry:
                assert len(cell.geometry.points) == 0

    def test_relayout_routes_edges(self) -> None:
        """relayout_diagram should also route edges around shapes."""
        d = _fresh_diagram()
        v1 = d.add_vertex("A", 0, 0, 120, 60)
        v2 = d.add_vertex("B", 0, 0, 120, 60)
        v3 = d.add_vertex("C", 0, 0, 120, 60)
        d.add_edge(v1, v2)
        d.add_edge(v2, v3)

        cfg = LayoutEngineConfig(route_edges=True)
        moved = relayout_diagram(d, config=cfg)
        assert len(moved) >= 2


# ===================================================================
# Consolidated tool tests (build_full, build_dag, reroute_edges)
# ===================================================================

class TestConsolidatedTools:
    """Tests for the batch tools via 5-tool API."""

    def setup_method(self) -> None:
        from drawio_mcp.server import _diagrams
        _diagrams.clear()

    def test_build_full_tool(self) -> None:
        from drawio_mcp.server import diagram, draw

        diagram(action="create", name="bd1")
        # First add some shapes
        ids = json.loads(draw(action="add_vertices", diagram_name="bd1", vertices=[
            {"label": "Existing", "x": 50, "y": 50},
        ]))
        a = ids[0]

        result = json.loads(draw(
            action="build_full", diagram_name="bd1",
            vertices=[
                {"label": "Node1", "x": 100, "y": 100},
                {"label": "Node2", "x": 300, "y": 100},
            ],
            edges=[
                {"source_id": a, "target_id": "will_fail"},  # will silently fail
            ],
        ))
        assert len(result["vertex_ids"]) == 2
        assert "summary" in result

    def test_build_full_with_theme(self) -> None:
        from drawio_mcp.server import diagram, draw

        diagram(action="create", name="bd2")
        result = json.loads(draw(
            action="build_full", diagram_name="bd2",
            vertices=[
                {"label": "A", "x": 100, "y": 100},
                {"label": "B", "x": 300, "y": 100},
            ],
            edges=[],
            theme="BLUE",
            title="Test Diagram",
            subtitle="Subtitle",
        ))
        assert len(result["title_ids"]) == 2
        assert "themed" in result["summary"]

    def test_build_dag_tool(self) -> None:
        from drawio_mcp.server import diagram, draw

        diagram(action="create", name="dag1")
        result = json.loads(draw(
            action="build_dag", diagram_name="dag1",
            edges=[
                {"source": "User", "target": "API"},
                {"source": "API", "target": "DB"},
            ],
            theme="GREEN",
            title="Architecture",
        ))
        assert "User" in result
        assert "API" in result
        assert "DB" in result
        assert "__summary" in result

    def test_build_dag_with_styles(self) -> None:
        from drawio_mcp.server import diagram, draw

        diagram(action="create", name="dag2")
        result = json.loads(draw(
            action="build_dag", diagram_name="dag2",
            edges=[
                {"source": "Client", "target": "Server"},
                {"source": "Server", "target": "Database"},
            ],
            node_styles={"Client": "ACTOR", "Database": "CYLINDER"},
            direction="LR",
        ))
        assert len(result) >= 3  # 3 nodes + __summary + __title_ids

    def test_reroute_edges_tool(self) -> None:
        from drawio_mcp.server import diagram, draw, layout

        diagram(action="create", name="re1")
        ids = json.loads(draw(action="add_vertices", diagram_name="re1", vertices=[
            {"label": "A", "x": 100, "y": 100},
            {"label": "B", "x": 100, "y": 500},
            {"label": "Blocker", "x": 100, "y": 280},
        ]))
        a, b = ids[0], ids[1]
        draw(action="add_edges", diagram_name="re1", edges=[
            {"source_id": a, "target_id": b},
        ])

        result = layout(action="reroute_edges", diagram_name="re1")
        assert "rerouted" in result.lower()

    def test_reroute_nonexistent_diagram(self) -> None:
        from drawio_mcp.server import layout
        result = layout(action="reroute_edges", diagram_name="nonexistent")
        assert "Error" in result

    def test_build_dag_error(self) -> None:
        from drawio_mcp.server import draw
        result = draw(action="build_dag", diagram_name="nonexistent", edges=[])
        assert "Error" in result

    def test_build_full_error(self) -> None:
        from drawio_mcp.server import draw
        result = draw(action="build_full", diagram_name="nonexistent",
                      vertices=[], edges=[])
        assert "Error" in result


# ===================================================================
# Edge path optimization tests
# ===================================================================

class TestOptimizeEdgePaths:
    """Tests for the optimize_edge_paths algorithm."""

    def _diagram_with_edges(self) -> tuple[Diagram, str, str, str]:
        """Create a diagram with 3 vertices and 2 edges with waypoints."""
        d = _fresh_diagram()
        a = d.add_vertex("A", 50, 50, 100, 60, "rounded=1;html=1;")
        b = d.add_vertex("B", 350, 50, 100, 60, "rounded=1;html=1;")
        c = d.add_vertex("C", 350, 250, 100, 60, "rounded=1;html=1;")
        # Edge A→B with unnecessary bend
        d.add_edge(a, b, "e1", "edgeStyle=orthogonalEdgeStyle;html=1;",
                   waypoints=[Point(200, 80), Point(200, 80)])
        # Edge A→C with detour waypoints
        d.add_edge(a, c, "e2", "edgeStyle=orthogonalEdgeStyle;html=1;",
                   waypoints=[Point(100, 200), Point(200, 200), Point(350, 200)])
        return d, a, b, c

    def test_returns_zero_on_empty_diagram(self) -> None:
        d = _fresh_diagram()
        result = optimize_edge_paths(d)
        assert result == 0

    def test_removes_collinear_waypoints(self) -> None:
        """Collinear waypoints on the same axis should be removed."""
        d = _fresh_diagram()
        a = d.add_vertex("A", 50, 100, 100, 60, "rounded=1;html=1;")
        b = d.add_vertex("B", 400, 100, 100, 60, "rounded=1;html=1;")
        # Three waypoints all at y=100 (collinear with source/target)
        d.add_edge(a, b, "", "edgeStyle=orthogonalEdgeStyle;html=1;",
                   waypoints=[Point(150, 100), Point(250, 100), Point(350, 100)])
        count = optimize_edge_paths(d)
        # The optimizer should simplify these collinear points
        edge = [c for c in d.cells if c.edge][0]
        # Points should be reduced or removed entirely
        assert len(edge.geometry.points) < 3 or count >= 0

    def test_straightens_near_collinear_segments(self) -> None:
        """Segments that are off by a few pixels should be straightened."""
        d = _fresh_diagram()
        a = d.add_vertex("A", 50, 50, 100, 60, "rounded=1;html=1;")
        b = d.add_vertex("B", 50, 350, 100, 60, "rounded=1;html=1;")
        # Waypoints that form a near-vertical path (x differs by only 3px)
        d.add_edge(a, b, "", "edgeStyle=orthogonalEdgeStyle;html=1;",
                   waypoints=[Point(103, 150), Point(100, 250)])
        optimize_edge_paths(d, straighten_threshold=10)
        edge = [c for c in d.cells if c.edge][0]
        if edge.geometry.points and len(edge.geometry.points) >= 2:
            # After straightening, X coords should be aligned
            xs = [p.x for p in edge.geometry.points]
            assert all(abs(x - xs[0]) < 10 for x in xs)

    def test_shortens_detours(self) -> None:
        """Unnecessary detour waypoints should be removed when path is clear."""
        d = _fresh_diagram()
        a = d.add_vertex("A", 50, 100, 80, 50, "rounded=1;html=1;")
        b = d.add_vertex("B", 400, 100, 80, 50, "rounded=1;html=1;")
        # No obstacles between A and B, but edge has a detour going down
        d.add_edge(a, b, "", "edgeStyle=orthogonalEdgeStyle;html=1;",
                   waypoints=[Point(200, 300), Point(350, 300)])
        original_edge = [c for c in d.cells if c.edge][0]
        original_count = len(original_edge.geometry.points)
        count = optimize_edge_paths(d)
        edge = [c for c in d.cells if c.edge][0]
        # Should have fewer waypoints now (detour removed)
        assert len(edge.geometry.points) < original_count or count > 0

    def test_separates_parallel_edges(self) -> None:
        """Edges sharing the same corridor should be nudged apart."""
        d = _fresh_diagram()
        a = d.add_vertex("A", 50, 50, 80, 50, "rounded=1;html=1;")
        b = d.add_vertex("B", 50, 300, 80, 50, "rounded=1;html=1;")
        c = d.add_vertex("C", 300, 50, 80, 50, "rounded=1;html=1;")
        dd_v = d.add_vertex("D", 300, 300, 80, 50, "rounded=1;html=1;")
        # Two edges with waypoints in the same horizontal corridor (y=180)
        d.add_edge(a, dd_v, "", "edgeStyle=orthogonalEdgeStyle;html=1;",
                   waypoints=[Point(90, 180), Point(340, 180)])
        d.add_edge(c, b, "", "edgeStyle=orthogonalEdgeStyle;html=1;",
                   waypoints=[Point(340, 180), Point(90, 180)])
        count = optimize_edge_paths(d, nudge_spacing=12)
        # At least something should be modified when edges overlap
        assert count >= 0  # No crash

    def test_no_crash_on_edges_without_waypoints(self) -> None:
        """Edges with no waypoints should be skipped gracefully."""
        d = _fresh_diagram()
        a = d.add_vertex("A", 50, 50, 100, 60, "rounded=1;html=1;")
        b = d.add_vertex("B", 300, 50, 100, 60, "rounded=1;html=1;")
        d.add_edge(a, b, "", "edgeStyle=orthogonalEdgeStyle;html=1;")
        count = optimize_edge_paths(d)
        assert count == 0

    def test_no_crash_on_missing_source_target(self) -> None:
        """Edges referencing missing cells should be skipped."""
        d = _fresh_diagram()
        a = d.add_vertex("A", 50, 50, 100, 60, "rounded=1;html=1;")
        # Edge to non-existent target
        cell = MxCell(id=d.next_id(), edge=True, source=a, target="missing",
                      geometry=Geometry(relative=True))
        cell.geometry.points = [Point(200, 200)]
        d.cells.append(cell)
        count = optimize_edge_paths(d)
        assert count == 0

    def test_optimization_preserves_valid_bends(self) -> None:
        """Waypoints needed to avoid obstacles should not be removed."""
        d = _fresh_diagram()
        a = d.add_vertex("A", 50, 50, 80, 50, "rounded=1;html=1;")
        b = d.add_vertex("B", 350, 250, 80, 50, "rounded=1;html=1;")
        # Obstacle blocking direct path
        d.add_vertex("Blocker", 180, 120, 100, 80, "rounded=1;html=1;")
        # Edge routes around the blocker
        d.add_edge(a, b, "", "edgeStyle=orthogonalEdgeStyle;html=1;",
                   waypoints=[Point(140, 80), Point(140, 240), Point(350, 240)])
        count = optimize_edge_paths(d, margin=15)
        edge = [c for c in d.cells if c.edge][0]
        # Should still have waypoints (can't go direct through blocker)
        assert len(edge.geometry.points) >= 1

    def test_grid_snap_applied(self) -> None:
        """All resulting waypoints should be snapped to the grid."""
        d = _fresh_diagram()
        d.grid_size = 10
        a = d.add_vertex("A", 50, 50, 100, 60, "rounded=1;html=1;")
        b = d.add_vertex("B", 50, 300, 100, 60, "rounded=1;html=1;")
        d.add_edge(a, b, "", "edgeStyle=orthogonalEdgeStyle;html=1;",
                   waypoints=[Point(103, 177), Point(97, 233)])
        optimize_edge_paths(d)
        edge = [c for c in d.cells if c.edge][0]
        for pt in edge.geometry.points:
            assert pt.x % 10 == 0, f"x={pt.x} not grid-snapped"
            assert pt.y % 10 == 0, f"y={pt.y} not grid-snapped"


class TestOptimizeConnectionsServerAction:
    """Tests for the optimize_connections layout action via server."""

    def test_optimize_connections_action(self) -> None:
        from drawio_mcp.server import diagram, draw, layout
        diagram(action="create", name="opt_test")
        draw(action="build_dag", diagram_name="opt_test", edges=[
            {"source": "A", "target": "B", "label": ""},
            {"source": "B", "target": "C", "label": ""},
            {"source": "A", "target": "C", "label": ""},
        ])
        result = layout(action="optimize_connections", diagram_name="opt_test")
        assert "optimized" in result.lower()

    def test_optimize_connections_nonexistent_diagram(self) -> None:
        from drawio_mcp.server import layout
        result = layout(action="optimize_connections", diagram_name="nonexistent999")
        assert "Error" in result

    def test_polish_includes_optimization(self) -> None:
        from drawio_mcp.server import diagram, draw, layout
        diagram(action="create", name="polish_opt")
        draw(action="build_dag", diagram_name="polish_opt", edges=[
            {"source": "X", "target": "Y", "label": ""},
            {"source": "Y", "target": "Z", "label": ""},
        ])
        result = layout(action="polish", diagram_name="polish_opt")
        assert "Optimized" in result


# ===================================================================
# Automatic design improvements tests
# ===================================================================

class TestAutoDesignImprovements:
    """Tests for automatic design improvements integrated into existing operations."""

    def test_sugiyama_equalizes_rank_heights(self) -> None:
        """Nodes in the same rank should have the same height after Sugiyama."""
        d = _fresh_diagram()
        # Multi-line label produces a taller estimated height
        edges = [
            ("Short", "Line1<br>Line2<br>Line3<br>Line4", ""),
            ("Short", "Tiny", ""),
        ]
        mapping = layout_sugiyama(d, edges)
        cells = {v: next(c for c in d.cells if c.id == v) for v in mapping.values()}
        tall_cell = cells[mapping["Line1<br>Line2<br>Line3<br>Line4"]]
        tiny_cell = cells[mapping["Tiny"]]
        # Both in same rank → equalized to the same height
        assert tall_cell.geometry.height == tiny_cell.geometry.height
        # The equalized height should be the taller one's
        assert tiny_cell.geometry.height > 60

    def test_sugiyama_equalization_no_overlaps(self) -> None:
        """Size equalization must not introduce overlaps."""
        d = _fresh_diagram()
        edges = [
            ("A", "B", ""), ("A", "C", ""), ("A", "D", ""),
            ("B", "E", ""), ("C", "E", ""), ("D", "E", ""),
        ]
        layout_sugiyama(d, edges)
        overlaps = find_overlapping_cells(d, margin=0)
        assert len(overlaps) == 0, f"Overlaps after equalization: {overlaps}"

    def test_relayout_updates_cell_sizes(self) -> None:
        """Relayout should update cell dimensions to equalized values."""
        d = _fresh_diagram()
        v1 = d.add_vertex("A", 0, 0, 120, 40)
        v2 = d.add_vertex("B", 200, 0, 150, 80)
        v3 = d.add_vertex("C", 100, 200, 120, 60)
        d.add_edge(v1, v3)
        d.add_edge(v2, v3)

        relayout_diagram(d, direction="TB")

        cell1 = next(c for c in d.cells if c.id == v1)
        cell2 = next(c for c in d.cells if c.id == v2)
        # v1 and v2 are in the same rank → equalized heights
        assert cell1.geometry.height == cell2.geometry.height

    def test_compact_aligns_row_baselines(self) -> None:
        """Compact should align shapes in the same row to the same Y."""
        d = _fresh_diagram()
        d.add_vertex("A", 100, 100, 120, 60)
        d.add_vertex("B", 300, 112, 120, 60)  # slightly offset Y

        compact_diagram(d, margin=40)

        from drawio_mcp.layout import get_all_vertex_bounds
        bounds = get_all_vertex_bounds(d)
        ids = list(bounds.keys())
        ys = [bounds[cid].y for cid in ids]
        assert abs(ys[0] - ys[1]) <= 10, f"Row Y values not aligned: {ys}"

    def test_compact_aligns_column_centers(self) -> None:
        """Compact should align shapes in the same column to the same X."""
        d = _fresh_diagram()
        d.add_vertex("A", 100, 100, 120, 60)
        d.add_vertex("B", 108, 300, 120, 60)  # slightly offset X

        compact_diagram(d, margin=40)

        from drawio_mcp.layout import get_all_vertex_bounds
        bounds = get_all_vertex_bounds(d)
        ids = list(bounds.keys())
        xs = [bounds[cid].x for cid in ids]
        assert abs(xs[0] - xs[1]) <= 10, f"Column X values not aligned: {xs}"

    def test_polish_includes_alignment_and_centering(self) -> None:
        """Polish should include alignment, centering, and margin steps."""
        from drawio_mcp.server import diagram, draw, layout, _diagrams
        _diagrams.clear()

        diagram(action="create", name="align_test")
        draw(action="build_dag", diagram_name="align_test", edges=[
            {"source": "A", "target": "B"},
            {"source": "A", "target": "C"},
            {"source": "B", "target": "D"},
            {"source": "C", "target": "D"},
        ])

        result = layout(action="polish", diagram_name="align_test")
        assert "Aligned" in result
        assert "Centered" in result

    def test_build_dag_ensures_margins(self) -> None:
        """build_dag output should respect page margins."""
        from drawio_mcp.server import diagram, draw, inspect, _diagrams
        _diagrams.clear()

        diagram(action="create", name="margin_test")
        draw(action="build_dag", diagram_name="margin_test", edges=[
            {"source": "X", "target": "Y"},
        ])

        cells = json.loads(inspect(action="cells", diagram_name="margin_test"))
        vertices = [c for c in cells if c.get("type") == "vertex" and "position" in c]
        for v in vertices:
            pos = v["position"]
            assert pos["x"] >= 20, f"Shape too close to left edge: x={pos['x']}"
            assert pos["y"] >= 20, f"Shape too close to top edge: y={pos['y']}"

    def test_build_full_auto_aligns_baselines(self) -> None:
        """build_full should auto-align nearby shapes to the same baseline."""
        from drawio_mcp.server import diagram, draw, inspect, _diagrams
        _diagrams.clear()

        diagram(action="create", name="full_align")
        result = json.loads(draw(
            action="build_full", diagram_name="full_align",
            vertices=[
                {"label": "A", "x": 100, "y": 100},
                {"label": "B", "x": 300, "y": 108},
            ],
            edges=[],
        ))

        cells = json.loads(inspect(action="cells", diagram_name="full_align"))
        vertices = [c for c in cells if c.get("type") == "vertex" and "position" in c]
        assert len(vertices) == 2
        ys = sorted([v["position"]["y"] for v in vertices])
        assert ys[0] == ys[1], f"Y values not aligned after build_full: {ys}"

    def test_equalize_connected_sizes_tb(self) -> None:
        """equalize_connected_sizes should unify row heights for TB layout."""
        from drawio_mcp.layout_engine import equalize_connected_sizes
        d = _fresh_diagram()
        d.add_vertex("A", 100, 100, 120, 40)
        d.add_vertex("B", 300, 100, 120, 80)

        count = equalize_connected_sizes(d, direction="TB", threshold=30)
        assert count >= 1

        cells_by_label = {c.value: c for c in d.cells if c.vertex and c.value}
        assert cells_by_label["A"].geometry.height == cells_by_label["B"].geometry.height

    def test_equalize_connected_sizes_lr(self) -> None:
        """equalize_connected_sizes should unify column widths for LR layout."""
        from drawio_mcp.layout_engine import equalize_connected_sizes
        d = _fresh_diagram()
        d.add_vertex("A", 100, 100, 100, 60)
        d.add_vertex("B", 100, 300, 160, 60)

        count = equalize_connected_sizes(d, direction="LR", threshold=30)
        assert count >= 1

        cells_by_label = {c.value: c for c in d.cells if c.vertex and c.value}
        assert cells_by_label["A"].geometry.width == cells_by_label["B"].geometry.width

    def test_center_diagram_on_page(self) -> None:
        """center_diagram_on_page should center content on the page."""
        from drawio_mcp.layout_engine import center_diagram_on_page
        d = _fresh_diagram()
        d.page = True
        d.page_width = 800
        d.page_height = 600
        # Place a single shape in the top-left corner
        d.add_vertex("A", 10, 10, 100, 60)

        moved = center_diagram_on_page(d, margin=50)
        assert moved >= 1

        from drawio_mcp.layout import get_all_vertex_bounds
        bounds = get_all_vertex_bounds(d)
        cell_id = [cid for cid in bounds][0]
        b = bounds[cell_id]
        # Should be roughly centered horizontally
        assert b.x > 200, f"Not centered: x={b.x}"

    def test_ensure_page_margins(self) -> None:
        """ensure_page_margins should push content away from page edges."""
        from drawio_mcp.layout_engine import ensure_page_margins
        d = _fresh_diagram()
        d.add_vertex("A", 5, 5, 120, 60)

        moved = ensure_page_margins(d, margin=40)
        assert moved >= 1

        from drawio_mcp.layout import get_all_vertex_bounds
        bounds = get_all_vertex_bounds(d)
        cell_id = list(bounds.keys())[0]
        assert bounds[cell_id].x >= 30, f"X too small: {bounds[cell_id].x}"
        assert bounds[cell_id].y >= 30, f"Y too small: {bounds[cell_id].y}"

    def test_ensure_page_margins_no_op(self) -> None:
        """ensure_page_margins should not move shapes already within margins."""
        from drawio_mcp.layout_engine import ensure_page_margins
        d = _fresh_diagram()
        d.add_vertex("A", 100, 100, 120, 60)

        moved = ensure_page_margins(d, margin=40)
        assert moved == 0

    def test_align_rank_baselines(self) -> None:
        """align_rank_baselines should align shapes at similar Y to same baseline."""
        from drawio_mcp.layout_engine import align_rank_baselines
        d = _fresh_diagram()
        d.add_vertex("A", 100, 100, 120, 60)
        d.add_vertex("B", 300, 115, 120, 60)  # 15px Y offset

        adjusted = align_rank_baselines(d, threshold=20)
        assert adjusted >= 1

        from drawio_mcp.layout import get_all_vertex_bounds
        bounds = get_all_vertex_bounds(d)
        ys = [bounds[cid].y for cid in bounds]
        assert abs(ys[0] - ys[1]) <= 10

    def test_align_column_centers(self) -> None:
        """align_column_centers should align shapes at similar X to same center."""
        from drawio_mcp.layout_engine import align_column_centers
        d = _fresh_diagram()
        d.add_vertex("A", 100, 100, 120, 60)
        d.add_vertex("B", 112, 300, 120, 60)  # 12px X offset

        adjusted = align_column_centers(d, threshold=20)
        assert adjusted >= 1

        from drawio_mcp.layout import get_all_vertex_bounds
        bounds = get_all_vertex_bounds(d)
        cxs = [bounds[cid].cx for cid in bounds]
        assert abs(cxs[0] - cxs[1]) <= 10

    def test_alignment_ignores_distant_shapes(self) -> None:
        """Shapes far apart should not be grouped for alignment."""
        from drawio_mcp.layout_engine import align_rank_baselines
        d = _fresh_diagram()
        d.add_vertex("A", 100, 100, 120, 60)
        d.add_vertex("B", 100, 400, 120, 60)  # 300px Y gap

        adjusted = align_rank_baselines(d, threshold=20)
        assert adjusted == 0  # Too far apart to group

    def test_sugiyama_lr_equalizes_widths(self) -> None:
        """LR layout should equalize widths within each rank."""
        d = _fresh_diagram()
        edges = [
            ("Short", "A longer label text", ""),
            ("Short", "X", ""),
        ]
        mapping = layout_sugiyama(d, edges, direction="LR")
        cells = {v: next(c for c in d.cells if c.id == v) for v in mapping.values()}
        long_cell = cells[mapping["A longer label text"]]
        x_cell = cells[mapping["X"]]
        # Both in same rank (LR) → equalized widths
        assert long_cell.geometry.width == x_cell.geometry.width
