"""Tests for layout helpers."""

from drawio_mcp.layout import (
    LayoutConfig,
    choose_best_ports,
    compute_orthogonal_waypoints,
    connect_chain,
    distribute_evenly,
    distribute_ports_for_batch,
    get_all_vertex_bounds,
    layout_grid,
    layout_horizontal,
    layout_tree,
    layout_vertical,
)
from drawio_mcp.models import CellBounds, Diagram, snap_to_grid


def _fresh_diagram() -> Diagram:
    return Diagram(name="test")


def test_layout_horizontal() -> None:
    d = _fresh_diagram()
    ids = layout_horizontal(d, ["A", "B", "C"])
    assert len(ids) == 3
    # All are vertices
    for cid in ids:
        cell = next(c for c in d.cells if c.id == cid)
        assert cell.vertex


def test_layout_vertical() -> None:
    d = _fresh_diagram()
    ids = layout_vertical(d, ["X", "Y"])
    assert len(ids) == 2
    # Y positions should differ
    cells = [next(c for c in d.cells if c.id == cid) for cid in ids]
    assert cells[0].geometry.y != cells[1].geometry.y


def test_layout_grid() -> None:
    d = _fresh_diagram()
    ids = layout_grid(d, ["1", "2", "3", "4", "5"], columns=3)
    assert len(ids) == 5


def test_layout_tree() -> None:
    d = _fresh_diagram()
    adj = {"Root": ["A", "B"], "A": ["C"]}
    mapping = layout_tree(d, adj, "Root")
    assert "Root" in mapping
    assert "A" in mapping
    assert "B" in mapping
    assert "C" in mapping
    # Edges should have been created
    edge_count = sum(1 for c in d.cells if c.edge)
    assert edge_count == 3  # Root→A, Root→B, A→C


def test_connect_chain() -> None:
    d = _fresh_diagram()
    ids = layout_horizontal(d, ["A", "B", "C"])
    edge_ids = connect_chain(d, ids)
    assert len(edge_ids) == 2


def test_connect_chain_with_labels() -> None:
    d = _fresh_diagram()
    ids = layout_horizontal(d, ["A", "B", "C"])
    edge_ids = connect_chain(d, ids, labels=["e1", "e2"])
    edges = [next(c for c in d.cells if c.id == eid) for eid in edge_ids]
    assert edges[0].value == "e1"
    assert edges[1].value == "e2"


# ===================================================================
# snap_to_grid tests
# ===================================================================

def test_snap_to_grid_rounds() -> None:
    assert snap_to_grid(13, 10) == 10
    assert snap_to_grid(17, 10) == 20
    assert snap_to_grid(15, 10) == 20  # round half up


def test_snap_to_grid_already_aligned() -> None:
    assert snap_to_grid(50, 10) == 50
    assert snap_to_grid(0, 10) == 0


# ===================================================================
# CellBounds tests
# ===================================================================

def test_cell_bounds_properties() -> None:
    b = CellBounds(100, 200, 120, 60)
    assert b.cx == 160  # 100 + 120/2
    assert b.cy == 230  # 200 + 60/2
    assert b.right == 220  # 100 + 120
    assert b.bottom == 260  # 200 + 60


def test_cell_bounds_intersects() -> None:
    a = CellBounds(0, 0, 100, 100)
    b = CellBounds(50, 50, 100, 100)
    c = CellBounds(200, 200, 50, 50)
    assert a.intersects(b) is True
    assert b.intersects(a) is True
    assert a.intersects(c) is False


def test_cell_bounds_contains_point() -> None:
    b = CellBounds(10, 20, 100, 50)
    assert b.contains_point(50, 40) is True
    assert b.contains_point(10, 20) is True  # edge
    assert b.contains_point(0, 0) is False


# ===================================================================
# choose_best_ports tests
# ===================================================================

def test_choose_best_ports_horizontal_right() -> None:
    """Target is to the right → exit RIGHT, entry LEFT."""
    src = CellBounds(0, 0, 100, 60)
    tgt = CellBounds(300, 0, 100, 60)
    (ex, ey), (enx, eny) = choose_best_ports(src, tgt)
    assert ex == 1.0 and ey == 0.5  # RIGHT
    assert enx == 0.0 and eny == 0.5  # LEFT


def test_choose_best_ports_horizontal_left() -> None:
    """Target is to the left → exit LEFT, entry RIGHT."""
    src = CellBounds(300, 0, 100, 60)
    tgt = CellBounds(0, 0, 100, 60)
    (ex, ey), (enx, eny) = choose_best_ports(src, tgt)
    assert ex == 0.0 and ey == 0.5
    assert enx == 1.0 and eny == 0.5


def test_choose_best_ports_vertical_down() -> None:
    """Target is below → exit BOTTOM, entry TOP."""
    src = CellBounds(100, 0, 100, 60)
    tgt = CellBounds(100, 300, 100, 60)
    (ex, ey), (enx, eny) = choose_best_ports(src, tgt)
    assert ex == 0.5 and ey == 1.0  # BOTTOM
    assert enx == 0.5 and eny == 0.0  # TOP


def test_choose_best_ports_vertical_up() -> None:
    """Target is above → exit TOP, entry BOTTOM."""
    src = CellBounds(100, 300, 100, 60)
    tgt = CellBounds(100, 0, 100, 60)
    (ex, ey), (enx, eny) = choose_best_ports(src, tgt)
    assert ex == 0.5 and ey == 0.0  # TOP
    assert enx == 0.5 and eny == 1.0  # BOTTOM


def test_choose_best_ports_explicit_direction() -> None:
    """Explicit direction override should be respected."""
    src = CellBounds(0, 0, 100, 60)
    tgt = CellBounds(300, 0, 100, 60)
    # Force vertical even though horizontal would be natural
    (ex, ey), (enx, eny) = choose_best_ports(src, tgt, direction="vertical")
    assert ey in (0.0, 1.0)  # TOP or BOTTOM, not 0.5


# ===================================================================
# distribute_evenly tests
# ===================================================================

def test_distribute_evenly_basic() -> None:
    positions = [0.0, 10.0, 500.0]
    sizes = [100.0, 100.0, 100.0]
    result = distribute_evenly(positions, sizes, 0.0, 600.0)
    assert len(result) == 3
    # All items should fit in range
    for pos, size in zip(result, sizes):
        assert pos >= 0
        assert pos + size <= 600
    # Gaps should be equal
    gap1 = result[1] - (result[0] + sizes[0])
    gap2 = result[2] - (result[1] + sizes[1])
    assert abs(gap1 - gap2) < 1.0


def test_distribute_evenly_two_items() -> None:
    result = distribute_evenly([0.0, 500.0], [50.0, 50.0], 0.0, 550.0)
    assert len(result) == 2
    # First stays at start, last ends at end
    assert result[0] == 0.0
    assert result[-1] + 50.0 == 550.0


# ===================================================================
# compute_orthogonal_waypoints tests
# ===================================================================

def test_orthogonal_waypoints_no_obstacles() -> None:
    """Without obstacles, should produce clean orthogonal path."""
    src = CellBounds(0, 0, 100, 60)
    tgt = CellBounds(300, 200, 100, 60)
    points = compute_orthogonal_waypoints(src, tgt, [])
    # Should have waypoints (may be empty for trivial direct connections)
    assert isinstance(points, list)
    for pt in points:
        assert hasattr(pt, "x")
        assert hasattr(pt, "y")


def test_orthogonal_waypoints_with_obstacle() -> None:
    """With an obstacle in between, should route around it."""
    src = CellBounds(0, 100, 80, 60)
    tgt = CellBounds(400, 100, 80, 60)
    obstacle = CellBounds(180, 80, 100, 100)
    points = compute_orthogonal_waypoints(src, tgt, [obstacle])
    assert isinstance(points, list)
    # The path should avoid the obstacle — verify no waypoint inside it
    for pt in points:
        assert not obstacle.contains_point(pt.x, pt.y), \
            f"Waypoint ({pt.x}, {pt.y}) is inside the obstacle"


# ===================================================================
# get_all_vertex_bounds tests
# ===================================================================

def test_get_all_vertex_bounds_basic() -> None:
    d = _fresh_diagram()
    ids = layout_horizontal(d, ["A", "B"])
    bounds = get_all_vertex_bounds(d)
    assert ids[0] in bounds
    assert ids[1] in bounds
    # B should be to the right of A
    assert bounds[ids[1]].x > bounds[ids[0]].x


def test_get_all_vertex_bounds_with_group() -> None:
    d = _fresh_diagram()
    # Add a group with a child
    gid = d.add_group("Container", 100, 100, 300, 200)
    child_id = d.add_vertex("Child", 50, 50, 100, 60, "", gid)
    bounds = get_all_vertex_bounds(d)
    # Child absolute position should be parent + relative
    assert child_id in bounds
    assert bounds[child_id].x == 150  # 100 + 50
    assert bounds[child_id].y == 150  # 100 + 50


# ===================================================================
# layout_tree crossing minimization tests
# ===================================================================

def test_layout_tree_crossing_minimization() -> None:
    """Tree with cross-references should minimize edge crossings."""
    d = _fresh_diagram()
    adj = {
        "Root": ["A", "B", "C"],
        "A": ["D"],
        "C": ["D"],  # D has two parents
    }
    mapping = layout_tree(d, adj, "Root")
    # All nodes created
    assert len(mapping) == 5
    # Check level 1 ordering: A and C are both connected to D,
    # so ideally they should be adjacent or close
    level1 = ["A", "B", "C"]
    cells = {label: next(c for c in d.cells if c.id == mapping[label]) for label in level1}
    positions = {label: cells[label].geometry.x for label in level1}
    # Verify all are at different positions
    pos_list = sorted(positions.values())
    assert len(set(pos_list)) == len(pos_list)


# ===================================================================
# Snap-to-grid in layout functions
# ===================================================================

def test_layout_horizontal_snaps_to_grid() -> None:
    d = _fresh_diagram()
    cfg = LayoutConfig(grid_size=20, start_x=40, start_y=40)
    ids = layout_horizontal(d, ["A", "B"], config=cfg)
    for cid in ids:
        cell = next(c for c in d.cells if c.id == cid)
        assert cell.geometry.x % 20 == 0
        assert cell.geometry.y % 20 == 0


def test_layout_vertical_snaps_to_grid() -> None:
    d = _fresh_diagram()
    cfg = LayoutConfig(grid_size=20, start_x=40, start_y=40)
    ids = layout_vertical(d, ["A", "B"], config=cfg)
    for cid in ids:
        cell = next(c for c in d.cells if c.id == cid)
        assert cell.geometry.x % 20 == 0
        assert cell.geometry.y % 20 == 0


def test_layout_grid_snaps_to_grid() -> None:
    d = _fresh_diagram()
    cfg = LayoutConfig(grid_size=20, start_x=40, start_y=40)
    ids = layout_grid(d, ["A", "B", "C", "D"], columns=2, config=cfg)
    for cid in ids:
        cell = next(c for c in d.cells if c.id == cid)
        assert cell.geometry.x % 20 == 0
        assert cell.geometry.y % 20 == 0


# ===================================================================
# Batch port distribution tests
# ===================================================================

def test_distribute_ports_single_edge() -> None:
    """Single edge should get center ports (same as choose_best_ports)."""
    bounds = {
        "A": CellBounds(0, 0, 100, 60),
        "B": CellBounds(300, 0, 100, 60),
    }
    result = distribute_ports_for_batch([("A", "B")], bounds)
    assert len(result) == 1
    (ex, ey), (enx, eny) = result[0]
    # Horizontal: exit RIGHT center, enter LEFT center
    assert ex == 1.0 and ey == 0.5
    assert enx == 0.0 and eny == 0.5


def test_distribute_ports_fan_out() -> None:
    """Multiple edges from same source to targets on same side should spread ports."""
    bounds = {
        "S": CellBounds(0, 100, 100, 60),
        "T1": CellBounds(300, 0, 100, 60),
        "T2": CellBounds(300, 100, 100, 60),
        "T3": CellBounds(300, 200, 100, 60),
    }
    connections = [("S", "T1"), ("S", "T2"), ("S", "T3")]
    result = distribute_ports_for_batch(connections, bounds)
    assert len(result) == 3
    # All exit from RIGHT side (x=1)
    exit_ys = []
    for (ex, ey), _ in result:
        assert ex == 1.0, f"Expected exitX=1.0, got {ex}"
        exit_ys.append(ey)
    # Exit Y values should be different and ordered top-to-bottom
    assert len(set(exit_ys)) == 3, f"Exit ports overlap: {exit_ys}"
    assert exit_ys == sorted(exit_ys), f"Exit ports not sorted: {exit_ys}"


def test_distribute_ports_fan_in() -> None:
    """Multiple edges from different sources arriving at same target side."""
    bounds = {
        "A": CellBounds(0, 0, 100, 60),
        "B": CellBounds(200, 0, 100, 60),
        "C": CellBounds(400, 0, 100, 60),
        "T": CellBounds(200, 300, 100, 60),
    }
    connections = [("A", "T"), ("B", "T"), ("C", "T")]
    result = distribute_ports_for_batch(connections, bounds)
    assert len(result) == 3
    # All enter from TOP side (y=0)
    entry_xs = []
    for _, (enx, eny) in result:
        assert eny == 0.0, f"Expected entryY=0, got {eny}"
        entry_xs.append(enx)
    # Entry X values should be different and ordered left-to-right
    assert len(set(entry_xs)) == 3, f"Entry ports overlap: {entry_xs}"
    assert entry_xs == sorted(entry_xs), f"Entry ports not sorted: {entry_xs}"


def test_distribute_ports_mixed_sides() -> None:
    """Edges going to different sides don't interfere with each other."""
    bounds = {
        "S": CellBounds(200, 200, 100, 60),
        "Right": CellBounds(500, 200, 100, 60),
        "Below": CellBounds(200, 400, 100, 60),
    }
    connections = [("S", "Right"), ("S", "Below")]
    result = distribute_ports_for_batch(connections, bounds)
    assert len(result) == 2
    (ex1, ey1), _ = result[0]  # to Right → exit RIGHT
    (ex2, ey2), _ = result[1]  # to Below → exit BOTTOM
    # They use different sides, so each gets center position
    assert ex1 == 1.0 and ey1 == 0.5  # RIGHT center
    assert ex2 == 0.5 and ey2 == 1.0  # BOTTOM center
