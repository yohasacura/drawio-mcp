"""
Automatic layout helpers for positioning cells in draw.io diagrams.

These are algorithmic layouts implementing professional graph drawing techniques:
- Sugiyama-style layered layout with crossing minimization (barycenter heuristic)
- Orthogonal edge routing with obstacle avoidance
- Smart spacing and distribution
- Snap-to-grid alignment
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from drawio_mcp.models import CellBounds, Diagram, Point, snap_to_grid


# ---------------------------------------------------------------------------
# Grid / auto-layout helpers
# ---------------------------------------------------------------------------

@dataclass
class LayoutConfig:
    """Configuration for automatic layout algorithms."""
    start_x: float = 50
    start_y: float = 50
    h_spacing: float = 60
    v_spacing: float = 60
    default_width: float = 120
    default_height: float = 60
    grid_size: int = 10  # Snap to grid


def layout_horizontal(
    diagram: Diagram,
    labels: list[str],
    style: str = "rounded=1;whiteSpace=wrap;html=1;",
    config: Optional[LayoutConfig] = None,
    y: Optional[float] = None,
) -> list[str]:
    """Place vertices in a horizontal row and return their IDs."""
    cfg = config or LayoutConfig()
    ids: list[str] = []
    row_y = snap_to_grid(y if y is not None else cfg.start_y, cfg.grid_size)
    for i, label in enumerate(labels):
        x = snap_to_grid(cfg.start_x + i * (cfg.default_width + cfg.h_spacing), cfg.grid_size)
        cid = diagram.add_vertex(
            label, x, row_y, cfg.default_width, cfg.default_height, style
        )
        ids.append(cid)
    return ids


def layout_vertical(
    diagram: Diagram,
    labels: list[str],
    style: str = "rounded=1;whiteSpace=wrap;html=1;",
    config: Optional[LayoutConfig] = None,
    x: Optional[float] = None,
) -> list[str]:
    """Place vertices in a vertical column and return their IDs."""
    cfg = config or LayoutConfig()
    ids: list[str] = []
    col_x = snap_to_grid(x if x is not None else cfg.start_x, cfg.grid_size)
    for i, label in enumerate(labels):
        cy = snap_to_grid(cfg.start_y + i * (cfg.default_height + cfg.v_spacing), cfg.grid_size)
        cid = diagram.add_vertex(
            label, col_x, cy, cfg.default_width, cfg.default_height, style
        )
        ids.append(cid)
    return ids


def layout_grid(
    diagram: Diagram,
    labels: list[str],
    columns: int = 3,
    style: str = "rounded=1;whiteSpace=wrap;html=1;",
    config: Optional[LayoutConfig] = None,
) -> list[str]:
    """Place vertices in a grid and return their IDs."""
    cfg = config or LayoutConfig()
    ids: list[str] = []
    for i, label in enumerate(labels):
        col = i % columns
        row = i // columns
        x = snap_to_grid(cfg.start_x + col * (cfg.default_width + cfg.h_spacing), cfg.grid_size)
        y = snap_to_grid(cfg.start_y + row * (cfg.default_height + cfg.v_spacing), cfg.grid_size)
        cid = diagram.add_vertex(
            label, x, y, cfg.default_width, cfg.default_height, style
        )
        ids.append(cid)
    return ids


def layout_tree(
    diagram: Diagram,
    adjacency: dict[str, list[str]],
    root_label: str,
    style: str = "rounded=1;whiteSpace=wrap;html=1;",
    edge_style: str = "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=classic;",
    config: Optional[LayoutConfig] = None,
    direction: str = "TB",  # TB, BT, LR, RL
) -> dict[str, str]:
    """
    Lay out a tree given an adjacency list.

    Uses barycenter heuristic for crossing minimization:
    - Assigns nodes to layers via BFS
    - Orders nodes within each layer by the average position of their
      parents in the previous layer (barycenter method from Sugiyama)
    - Centers each layer for balanced appearance
    - Snaps all coordinates to grid

    Returns a mapping of label → cell ID.
    """
    cfg = config or LayoutConfig()

    # BFS to assign levels
    levels: dict[str, int] = {root_label: 0}
    order: list[str] = [root_label]
    queue = [root_label]
    while queue:
        node = queue.pop(0)
        for child in adjacency.get(node, []):
            if child not in levels:
                levels[child] = levels[node] + 1
                order.append(child)
                queue.append(child)

    # Group by level
    by_level: dict[int, list[str]] = {}
    for label, lvl in levels.items():
        by_level.setdefault(lvl, []).append(label)

    # Build reverse adjacency (child -> parents)
    reverse_adj: dict[str, list[str]] = {}
    for parent_lbl, children in adjacency.items():
        for child in children:
            reverse_adj.setdefault(child, []).append(parent_lbl)

    # --- Crossing minimization via barycenter heuristic ---
    # For each level > 0, sort nodes by the average position of their
    # parents in the previous level. This is the core of Sugiyama step 3.
    max_lvl = max(by_level.keys()) if by_level else 0
    # Assign initial positions (index within level)
    pos_in_level: dict[str, float] = {}
    for lbl in by_level.get(0, []):
        pos_in_level[lbl] = float(by_level[0].index(lbl))

    # Forward sweep (top to bottom)
    for lvl in range(1, max_lvl + 1):
        nodes = by_level.get(lvl, [])
        barycenters: dict[str, float] = {}
        for node in nodes:
            parents = [p for p in reverse_adj.get(node, []) if p in pos_in_level]
            if parents:
                barycenters[node] = sum(pos_in_level[p] for p in parents) / len(parents)
            else:
                barycenters[node] = float(nodes.index(node))
        # Sort by barycenter
        nodes.sort(key=lambda n: barycenters.get(n, 0))
        by_level[lvl] = nodes
        for i, n in enumerate(nodes):
            pos_in_level[n] = float(i)

    # Backward sweep (bottom to top) for refinement
    for lvl in range(max_lvl - 1, -1, -1):
        nodes = by_level.get(lvl, [])
        barycenters: dict[str, float] = {}
        for node in nodes:
            children = [c for c in adjacency.get(node, []) if c in pos_in_level]
            if children:
                barycenters[node] = sum(pos_in_level[c] for c in children) / len(children)
            else:
                barycenters[node] = pos_in_level.get(node, 0)
        nodes.sort(key=lambda n: barycenters.get(n, 0))
        by_level[lvl] = nodes
        for i, n in enumerate(nodes):
            pos_in_level[n] = float(i)

    max_width_count = max(len(v) for v in by_level.values())

    # Assign positions with snap-to-grid
    label_to_id: dict[str, str] = {}
    for lvl, labels_at in sorted(by_level.items()):
        count = len(labels_at)
        # Center this level
        total_width = count * cfg.default_width + (count - 1) * cfg.h_spacing
        max_total = max_width_count * cfg.default_width + (max_width_count - 1) * cfg.h_spacing
        offset = (max_total - total_width) / 2

        for i, lbl in enumerate(labels_at):
            if direction in ("TB", "BT"):
                x = cfg.start_x + offset + i * (cfg.default_width + cfg.h_spacing)
                y = cfg.start_y + lvl * (cfg.default_height + cfg.v_spacing)
                if direction == "BT":
                    y = cfg.start_y + (max_lvl - lvl) * (cfg.default_height + cfg.v_spacing)
            else:
                y = cfg.start_y + offset + i * (cfg.default_height + cfg.v_spacing)
                x = cfg.start_x + lvl * (cfg.default_width + cfg.h_spacing)
                if direction == "RL":
                    x = cfg.start_x + (max_lvl - lvl) * (cfg.default_width + cfg.h_spacing)

            # Snap to grid
            x = snap_to_grid(x, cfg.grid_size)
            y = snap_to_grid(y, cfg.grid_size)

            cid = diagram.add_vertex(lbl, x, y, cfg.default_width, cfg.default_height, style)
            label_to_id[lbl] = cid

    # Add edges
    for parent_lbl, children in adjacency.items():
        for child_lbl in children:
            if parent_lbl in label_to_id and child_lbl in label_to_id:
                diagram.add_edge(label_to_id[parent_lbl], label_to_id[child_lbl], style=edge_style)

    return label_to_id


def connect_chain(
    diagram: Diagram,
    ids: list[str],
    style: str = "endArrow=classic;html=1;",
    labels: Optional[list[str]] = None,
) -> list[str]:
    """Connect a list of vertex IDs sequentially, return edge IDs."""
    edge_ids: list[str] = []
    for i in range(len(ids) - 1):
        lbl = labels[i] if labels and i < len(labels) else ""
        eid = diagram.add_edge(ids[i], ids[i + 1], value=lbl, style=style)
        edge_ids.append(eid)
    return edge_ids


# ---------------------------------------------------------------------------
# Smart edge connection port selection
# ---------------------------------------------------------------------------

def choose_best_ports(
    src_bounds: CellBounds,
    tgt_bounds: CellBounds,
    direction: str = "auto",
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Choose optimal exit/entry port positions for a single edge.

    Analyzes the relative positions of source and target shapes and picks
    connection points that produce the cleanest orthogonal path.

    Returns:
        ((exit_x, exit_y), (entry_x, entry_y)) — values 0..1 relative to shape.
    """
    dx = tgt_bounds.cx - src_bounds.cx
    dy = tgt_bounds.cy - src_bounds.cy

    # Determine dominant direction of the connection
    if direction == "auto":
        if abs(dx) > abs(dy) * 1.5:
            direction = "horizontal"
        elif abs(dy) > abs(dx) * 1.5:
            direction = "vertical"
        else:
            # Diagonal — pick based on relative position
            direction = "vertical" if abs(dy) >= abs(dx) else "horizontal"

    if direction == "horizontal":
        if dx >= 0:
            return (1.0, 0.5), (0.0, 0.5)  # right → left
        else:
            return (0.0, 0.5), (1.0, 0.5)  # left → right
    else:
        if dy >= 0:
            return (0.5, 1.0), (0.5, 0.0)  # bottom → top
        else:
            return (0.5, 0.0), (0.5, 1.0)  # top → bottom


def _determine_side(
    src_bounds: CellBounds,
    tgt_bounds: CellBounds,
) -> tuple[str, str]:
    """Determine which side of each shape the edge should connect to.

    Returns (exit_side, entry_side) — one of "top", "bottom", "left", "right".
    """
    dx = tgt_bounds.cx - src_bounds.cx
    dy = tgt_bounds.cy - src_bounds.cy

    if abs(dx) > abs(dy) * 1.2:
        # Predominantly horizontal
        if dx >= 0:
            return "right", "left"
        else:
            return "left", "right"
    elif abs(dy) > abs(dx) * 1.2:
        # Predominantly vertical
        if dy >= 0:
            return "bottom", "top"
        else:
            return "top", "bottom"
    else:
        # Diagonal — prefer vertical connection for orthogonal routing
        if dy >= 0:
            return "bottom", "top"
        else:
            return "top", "bottom"


def _side_to_base_port(side: str) -> tuple[float, float]:
    """Convert a side name to its center port coordinates."""
    return {
        "top": (0.5, 0.0),
        "bottom": (0.5, 1.0),
        "left": (0.0, 0.5),
        "right": (1.0, 0.5),
    }[side]


def _distribute_ports_on_side(
    side: str,
    count: int,
    index: int,
) -> tuple[float, float]:
    """Distribute port positions evenly along one side of a shape.

    When multiple edges connect to the same side of a shape, this
    spreads them evenly (e.g. at 0.25, 0.5, 0.75 along that side)
    instead of stacking them all at the center.

    Args:
        side: "top", "bottom", "left", or "right".
        count: Total number of edges on this side.
        index: 0-based index of this edge among siblings.

    Returns:
        (x, y) port coordinates in 0..1 range.
    """
    if count <= 1:
        return _side_to_base_port(side)

    # Spread positions from 0.2 to 0.8 to avoid corners
    margin = 0.15
    t = margin + (1.0 - 2 * margin) * index / (count - 1)

    if side == "top":
        return (t, 0.0)
    elif side == "bottom":
        return (t, 1.0)
    elif side == "left":
        return (0.0, t)
    elif side == "right":
        return (1.0, t)
    return (0.5, 0.5)


def distribute_ports_for_batch(
    connections: list[tuple[str, str]],
    bounds: dict[str, CellBounds],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Compute distributed port positions for a batch of connections.

    Unlike choose_best_ports (which handles one edge at a time), this
    function considers ALL connections together. When multiple edges
    share the same source or target node AND connect on the same side,
    it distributes their ports evenly to prevent overlapping.

    Args:
        connections: List of (source_id, target_id) pairs.
        bounds: Bounding boxes for all vertices.

    Returns:
        List of ((exit_x, exit_y), (entry_x, entry_y)) tuples,
        one per connection, in the same order as input.
    """
    if not connections:
        return []

    # Step 1: determine which side each edge uses on each node
    edge_sides: list[tuple[str, str]] = []  # (exit_side, entry_side)
    for src_id, tgt_id in connections:
        src_b = bounds.get(src_id)
        tgt_b = bounds.get(tgt_id)
        if src_b and tgt_b:
            exit_side, entry_side = _determine_side(src_b, tgt_b)
            edge_sides.append((exit_side, entry_side))
        else:
            edge_sides.append(("right", "left"))  # fallback

    # Step 2: group edges by (node_id, side) to find siblings
    # For exits: group by (source_id, exit_side)
    from collections import defaultdict
    exit_groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    entry_groups: dict[tuple[str, str], list[int]] = defaultdict(list)

    for i, (src_id, tgt_id) in enumerate(connections):
        exit_side, entry_side = edge_sides[i]
        exit_groups[(src_id, exit_side)].append(i)
        entry_groups[(tgt_id, entry_side)].append(i)

    # Step 3: sort siblings within each group by target/source position
    # so ports are ordered spatially (left-to-right, top-to-bottom)
    for (node_id, side), indices in exit_groups.items():
        if len(indices) > 1:
            # Sort by target position along the perpendicular axis.
            # Capture `side` via default arg to avoid late-binding.
            def _sort_key_exit(idx: int, _side: str = side) -> float:
                tgt_id = connections[idx][1]
                tgt_b = bounds.get(tgt_id)
                if not tgt_b:
                    return 0.0
                if _side in ("top", "bottom"):
                    return tgt_b.cx  # sort left-to-right
                else:
                    return tgt_b.cy  # sort top-to-bottom
            indices.sort(key=_sort_key_exit)

    for (node_id, side), indices in entry_groups.items():
        if len(indices) > 1:
            def _sort_key_entry(idx: int, _side: str = side) -> float:
                src_id = connections[idx][0]
                src_b = bounds.get(src_id)
                if not src_b:
                    return 0.0
                if _side in ("top", "bottom"):
                    return src_b.cx  # sort left-to-right
                else:
                    return src_b.cy  # sort top-to-bottom
            indices.sort(key=_sort_key_entry)

    # Step 4: assign distributed ports
    results: list[tuple[tuple[float, float], tuple[float, float]]] = [
        ((0.5, 0.5), (0.5, 0.5)) for _ in connections
    ]

    for i in range(len(connections)):
        src_id, tgt_id = connections[i]
        exit_side, entry_side = edge_sides[i]

        # Find this edge's position among its exit siblings
        exit_key = (src_id, exit_side)
        exit_siblings = exit_groups[exit_key]
        exit_idx = exit_siblings.index(i)
        exit_port = _distribute_ports_on_side(exit_side, len(exit_siblings), exit_idx)

        # Find this edge's position among its entry siblings
        entry_key = (tgt_id, entry_side)
        entry_siblings = entry_groups[entry_key]
        entry_idx = entry_siblings.index(i)
        entry_port = _distribute_ports_on_side(entry_side, len(entry_siblings), entry_idx)

        results[i] = (exit_port, entry_port)

    return results


# ---------------------------------------------------------------------------
# Smart spacing / distribution
# ---------------------------------------------------------------------------

def distribute_evenly(
    positions: list[float],
    sizes: list[float],
    start: float,
    end: float,
) -> list[float]:
    """Distribute items evenly between start and end.

    Given N items with their sizes, computes new positions so they're
    evenly distributed with equal spacing between them.

    Args:
        positions: Current positions (ignored, just for count).
        sizes: Size of each item (width or height).
        start: Start of the distribution range.
        end: End of the distribution range.

    Returns:
        New positions for each item.
    """
    n = len(positions)
    if n <= 1:
        return positions

    total_item_size = sum(sizes)
    available_space = (end - start) - total_item_size
    gap = available_space / (n - 1) if n > 1 else 0
    gap = max(gap, 10)  # minimum 10px spacing

    result: list[float] = []
    current = start
    for size in sizes:
        result.append(current)
        current += size + gap
    return result


# ---------------------------------------------------------------------------
# Orthogonal edge routing with obstacle avoidance
# ---------------------------------------------------------------------------

def compute_orthogonal_waypoints(
    src: CellBounds,
    tgt: CellBounds,
    obstacles: list[CellBounds],
    margin: float = 20,
) -> list[Point]:
    """Compute orthogonal waypoints that avoid obstacles.

    Uses a simplified channel-based routing:
    1. Determine if the path should go horizontally-first or vertically-first
    2. Route through a midpoint in the gap between shapes
    3. Check if the path crosses any obstacle; if so, route around it

    Args:
        src: Source bounding box.
        tgt: Target bounding box.
        obstacles: List of bounding boxes to avoid.
        margin: Minimum clearance around obstacles.

    Returns:
        List of waypoint Points for the edge.
    """
    # Exit from source center-right/bottom, enter target center-left/top
    sx, sy = src.cx, src.cy
    tx, ty = tgt.cx, tgt.cy

    dx = tx - sx
    dy = ty - sy

    waypoints: list[Point] = []

    # Simple case: shapes are aligned (same row or column)
    if abs(dy) < src.height / 2 + margin:
        # Horizontally aligned — straight horizontal path
        return waypoints

    if abs(dx) < src.width / 2 + margin:
        # Vertically aligned — straight vertical path
        return waypoints

    # L-shaped routing: go horizontal first, then vertical
    # or vertical first then horizontal — pick the one with fewer crossings
    mid_x = sx + dx / 2
    mid_y = sy + dy / 2

    # Option A: horizontal first (sx → mid_x, sy) then (mid_x, sy → ty)
    waypoint_a = [Point(mid_x, sy), Point(mid_x, ty)]
    crossings_a = _count_obstacle_crossings(sx, sy, mid_x, sy, obstacles, margin) + \
                  _count_obstacle_crossings(mid_x, sy, mid_x, ty, obstacles, margin)

    # Option B: vertical first (sx, sy → mid_y) then (sx → tx, mid_y)
    waypoint_b = [Point(sx, mid_y), Point(tx, mid_y)]
    crossings_b = _count_obstacle_crossings(sx, sy, sx, mid_y, obstacles, margin) + \
                  _count_obstacle_crossings(sx, mid_y, tx, mid_y, obstacles, margin)

    if crossings_a <= crossings_b:
        waypoints = waypoint_a
    else:
        waypoints = waypoint_b

    # If there are still crossings, try routing around the obstacle
    if min(crossings_a, crossings_b) > 0:
        waypoints = _route_around_obstacles(src, tgt, obstacles, margin)

    return waypoints


def _count_obstacle_crossings(
    x1: float, y1: float,
    x2: float, y2: float,
    obstacles: list[CellBounds],
    margin: float,
) -> int:
    """Count how many obstacles a line segment crosses."""
    count = 0
    for obs in obstacles:
        # Create an expanded bounding box
        expanded = CellBounds(
            obs.x - margin, obs.y - margin,
            obs.width + 2 * margin, obs.height + 2 * margin,
        )
        # Check if the line segment passes through the obstacle
        if _segment_intersects_rect(x1, y1, x2, y2, expanded):
            count += 1
    return count


def _segment_intersects_rect(
    x1: float, y1: float,
    x2: float, y2: float,
    rect: CellBounds,
) -> bool:
    """Check if a line segment intersects a rectangle."""
    # For orthogonal segments (horizontal or vertical lines)
    if abs(x1 - x2) < 0.1:  # Vertical segment
        min_y, max_y = min(y1, y2), max(y1, y2)
        return (rect.x <= x1 <= rect.right and
                max_y >= rect.y and min_y <= rect.bottom)
    if abs(y1 - y2) < 0.1:  # Horizontal segment
        min_x, max_x = min(x1, x2), max(x1, x2)
        return (rect.y <= y1 <= rect.bottom and
                max_x >= rect.x and min_x <= rect.right)
    return False


def _route_around_obstacles(
    src: CellBounds,
    tgt: CellBounds,
    obstacles: list[CellBounds],
    margin: float,
) -> list[Point]:
    """Route an orthogonal path around obstacles using channel routing.

    Uses a 3-segment path that goes around any blocking obstacles
    by finding a clear vertical or horizontal channel.
    """
    dx = tgt.cx - src.cx
    dy = tgt.cy - src.cy

    # Try going wide around obstacles
    # Find the clear Y coordinate above or below all obstacles
    all_tops = [o.y for o in obstacles]
    all_bottoms = [o.bottom for o in obstacles]

    # Try routing above all obstacles
    route_y_above = min(all_tops) - margin if all_tops else src.cy
    route_y_below = max(all_bottoms) + margin if all_bottoms else src.cy

    # Pick the route that's closer to the midpoint
    mid_y = (src.cy + tgt.cy) / 2
    if abs(route_y_above - mid_y) < abs(route_y_below - mid_y):
        route_y = route_y_above
    else:
        route_y = route_y_below

    # 3-segment path: down/up to route_y, across, then down/up to target
    if abs(dx) > abs(dy):
        return [Point(src.cx, route_y), Point(tgt.cx, route_y)]
    else:
        # Find clear X coordinate
        all_lefts = [o.x for o in obstacles]
        all_rights = [o.right for o in obstacles]
        route_x_left = min(all_lefts) - margin if all_lefts else src.cx
        route_x_right = max(all_rights) + margin if all_rights else src.cx
        mid_x = (src.cx + tgt.cx) / 2
        route_x = route_x_left if abs(route_x_left - mid_x) < abs(route_x_right - mid_x) else route_x_right
        return [Point(route_x, src.cy), Point(route_x, tgt.cy)]


# ---------------------------------------------------------------------------
# Get cell bounds from diagram
# ---------------------------------------------------------------------------

def get_all_vertex_bounds(diagram: Diagram) -> dict[str, CellBounds]:
    """Extract bounding boxes for all vertices in a diagram.

    Walks the parent chain to compute absolute coordinates for
    vertices that are children of groups/containers.
    """
    bounds: dict[str, CellBounds] = {}
    # First pass: collect raw geometry
    raw: dict[str, tuple[float, float, float, float, str]] = {}
    for cell in diagram.cells:
        if cell.vertex and cell.geometry and not cell.geometry.relative:
            raw[cell.id] = (
                cell.geometry.x,
                cell.geometry.y,
                cell.geometry.width,
                cell.geometry.height,
                cell.parent or "1",
            )

    # Compute absolute positions by walking parent chain
    def abs_pos(cell_id: str) -> tuple[float, float]:
        if cell_id not in raw:
            return 0.0, 0.0
        x, y, _, _, parent = raw[cell_id]
        if parent in ("0", "1", ""):
            return x, y
        px, py = abs_pos(parent)
        return px + x, py + y

    for cell_id, (rx, ry, w, h, _) in raw.items():
        ax, ay = abs_pos(cell_id)
        bounds[cell_id] = CellBounds(ax, ay, w, h)

    return bounds
