"""
Professional layout engine for draw.io diagrams.

Implements graph drawing algorithms similar to PlantUML / Graphviz:
- Sugiyama-style layered layout for DAGs (directed acyclic graphs)
- Overlap removal with force-based repulsion
- Edge label collision avoidance
- Compact layout with minimum spacing constraints
- Auto-relayout for reorganizing existing diagrams

These algorithms produce clean, professional diagrams with:
- No overlapping shapes
- No overlapping edge labels
- Proper spacing and alignment
- Minimized edge crossings
- Orthogonal edge routing
"""

from __future__ import annotations

import heapq
import math
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional

from drawio_mcp.layout import get_all_vertex_bounds
from drawio_mcp.models import CellBounds, Diagram, Geometry, MxCell, Point, snap_to_grid


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class LayoutEngineConfig:
    """Configuration for the professional layout engine."""
    # Spacing
    rank_spacing: float = 100      # Vertical space between layers/ranks
    node_spacing: float = 60       # Horizontal space between nodes in same rank
    group_padding: float = 30      # Padding inside containers
    edge_label_margin: float = 10  # Min gap between edge labels and shapes
    min_node_distance: float = 40  # Minimum distance between any two nodes

    # Dimensions
    default_width: float = 120
    default_height: float = 60

    # Grid
    grid_size: int = 10

    # Algorithm tuning
    max_overlap_iterations: int = 50    # Max iterations for overlap removal
    overlap_padding: float = 20         # Extra padding when resolving overlaps
    barycenter_iterations: int = 4      # Crossing minimization sweeps
    compact: bool = True                # Whether to compact the layout

    # Edge routing
    edge_margin: float = 15            # Clearance around shapes for edges
    route_edges: bool = True           # Enable obstacle-aware edge routing

    # Starting position
    start_x: float = 50
    start_y: float = 80


# ---------------------------------------------------------------------------
# Sugiyama Layered Layout (for DAGs — like PlantUML)
# ---------------------------------------------------------------------------

@dataclass
class _Node:
    """Internal node representation for layout algorithms."""
    id: str
    label: str
    width: float
    height: float
    rank: int = 0       # Layer assignment
    order: float = 0    # Position within layer
    x: float = 0
    y: float = 0
    is_virtual: bool = False  # Virtual nodes for long edges


@dataclass
class _Edge:
    """Internal edge representation."""
    source: str
    target: str
    label: str = ""
    cell_id: str = ""


def layout_sugiyama(
    diagram: Diagram,
    edges: list[tuple[str, str, str]],  # (source_label, target_label, edge_label)
    node_styles: dict[str, str] | None = None,
    edge_style: str = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;",
    config: LayoutEngineConfig | None = None,
    direction: str = "TB",
) -> dict[str, str]:
    """Lay out a directed graph using the Sugiyama framework.

    This is the same algorithm used by PlantUML and Graphviz's 'dot'.
    It produces layered layouts with minimized edge crossings.

    Steps:
    1. Cycle removal (reverse back-edges)
    2. Layer assignment (longest path)
    3. Virtual node insertion for long edges
    4. Crossing minimization (barycenter heuristic, multi-pass)
    5. Coordinate assignment with compaction
    6. Edge routing

    Args:
        diagram: Target diagram.
        edges: List of (source_label, target_label, edge_label) tuples.
        node_styles: Optional dict mapping label → style string.
        edge_style: Default edge style.
        config: Layout configuration.
        direction: TB (top-bottom), BT, LR, RL.

    Returns:
        Mapping of label → cell ID.
    """
    cfg = config or LayoutEngineConfig()
    styles = node_styles or {}
    default_style = "rounded=1;whiteSpace=wrap;html=1;"

    # Collect unique nodes
    all_labels: set[str] = set()
    adj: dict[str, list[str]] = defaultdict(list)
    reverse_adj: dict[str, list[str]] = defaultdict(list)
    edge_list: list[_Edge] = []

    for src, tgt, lbl in edges:
        all_labels.add(src)
        all_labels.add(tgt)
        adj[src].append(tgt)
        reverse_adj[tgt].append(src)
        edge_list.append(_Edge(source=src, target=tgt, label=lbl))

    # Add isolated nodes (sources with no incoming edges)
    nodes: dict[str, _Node] = {}
    for label in all_labels:
        w, h = _estimate_node_size(label, cfg.default_width, cfg.default_height)
        nodes[label] = _Node(id=label, label=label, width=w, height=h)

    # --- Step 1: Cycle removal ---
    # Find back-edges using DFS and temporarily reverse them
    back_edges = _find_back_edges(all_labels, adj)
    effective_adj = defaultdict(list)
    effective_rev = defaultdict(list)
    reversed_edges: set[tuple[str, str]] = set()

    for src in adj:
        for tgt in adj[src]:
            if (src, tgt) in back_edges:
                effective_adj[tgt].append(src)
                effective_rev[src].append(tgt)
                reversed_edges.add((src, tgt))
            else:
                effective_adj[src].append(tgt)
                effective_rev[tgt].append(src)

    # --- Step 2: Layer assignment (longest path from sources) ---
    ranks = _assign_ranks_longest_path(all_labels, effective_adj, effective_rev)
    for label, rank in ranks.items():
        nodes[label].rank = rank

    # --- Step 3: Virtual nodes for long edges ---
    virtual_count = 0
    expanded_edges: list[tuple[str, str]] = []
    for edge in edge_list:
        src_label = edge.source
        tgt_label = edge.target

        if (src_label, tgt_label) in reversed_edges:
            src_rank = ranks[tgt_label]
            tgt_rank = ranks[src_label]
        else:
            src_rank = ranks[src_label]
            tgt_rank = ranks[tgt_label]

        span = tgt_rank - src_rank
        if span <= 1:
            expanded_edges.append((src_label, tgt_label))
        else:
            # Insert virtual nodes
            prev = src_label
            for r in range(src_rank + 1, tgt_rank):
                vname = f"__virtual_{virtual_count}"
                virtual_count += 1
                nodes[vname] = _Node(
                    id=vname, label="", width=1, height=1,
                    rank=r, is_virtual=True,
                )
                expanded_edges.append((prev, vname))
                prev = vname
            expanded_edges.append((prev, tgt_label))

    # --- Step 4: Crossing minimization ---
    by_rank: dict[int, list[str]] = defaultdict(list)
    for label, node in nodes.items():
        by_rank[node.rank].append(label)

    # Build adjacency for expanded graph
    exp_adj: dict[str, list[str]] = defaultdict(list)
    exp_rev: dict[str, list[str]] = defaultdict(list)
    for s, t in expanded_edges:
        exp_adj[s].append(t)
        exp_rev[t].append(s)

    max_rank = max(by_rank.keys()) if by_rank else 0

    # Initialize order
    for rank_nodes in by_rank.values():
        for i, label in enumerate(rank_nodes):
            nodes[label].order = float(i)

    # Multi-pass barycenter
    for iteration in range(cfg.barycenter_iterations):
        # Forward sweep
        for r in range(1, max_rank + 1):
            _barycenter_sort(by_rank[r], nodes, exp_rev, nodes)
        # Backward sweep
        for r in range(max_rank - 1, -1, -1):
            _barycenter_sort(by_rank[r], nodes, exp_adj, nodes)

    # --- Step 4.5: Equalize node sizes within ranks ---
    # Makes all nodes in the same rank share the same height (TB/BT) or
    # width (LR/RL) for cleaner, grid-like alignment.
    _equalize_rank_sizes(by_rank, nodes, direction)

    # --- Step 5: Coordinate assignment ---
    _assign_coordinates(by_rank, nodes, cfg, direction, max_rank)

    # --- Step 6: Overlap removal ---
    real_nodes = {k: v for k, v in nodes.items() if not v.is_virtual}
    _remove_overlaps(list(real_nodes.values()), cfg)

    # --- Step 7: Create cells ---
    label_to_id: dict[str, str] = {}
    for label, node in nodes.items():
        if node.is_virtual:
            continue
        style = styles.get(label, default_style)
        x = snap_to_grid(node.x, cfg.grid_size)
        y = snap_to_grid(node.y, cfg.grid_size)
        cid = diagram.add_vertex(label, x, y, node.width, node.height, style)
        label_to_id[label] = cid

    # --- Step 8: Create edges with labels ---
    for edge in edge_list:
        if edge.source in label_to_id and edge.target in label_to_id:
            src_id = label_to_id[edge.source]
            tgt_id = label_to_id[edge.target]

            eid = diagram.add_edge(
                src_id, tgt_id,
                value=edge.label, style=edge_style,
            )
            edge.cell_id = eid

    # --- Step 9: Route edges around obstacles ---
    if cfg.route_edges:
        route_edges_around_obstacles(diagram, margin=cfg.edge_margin)

    return label_to_id


def _find_back_edges(
    all_nodes: set[str],
    adj: dict[str, list[str]],
) -> set[tuple[str, str]]:
    """Find back-edges in a directed graph using iterative DFS."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in all_nodes}
    back_edges: set[tuple[str, str]] = set()

    for start in all_nodes:
        if color[start] != WHITE:
            continue
        # Iterative DFS using explicit stack.
        # Each frame is (node, iterator_over_neighbors).
        color[start] = GRAY
        stack: list[tuple[str, int]] = [(start, 0)]
        while stack:
            u, idx = stack[-1]
            neighbors = adj.get(u, [])
            if idx < len(neighbors):
                stack[-1] = (u, idx + 1)
                v = neighbors[idx]
                if v not in color:
                    continue
                if color[v] == GRAY:
                    back_edges.add((u, v))
                elif color[v] == WHITE:
                    color[v] = GRAY
                    stack.append((v, 0))
            else:
                color[u] = BLACK
                stack.pop()

    return back_edges


def _assign_ranks_longest_path(
    all_nodes: set[str],
    adj: dict[str, list[str]],
    rev_adj: dict[str, list[str]],
) -> dict[str, int]:
    """Assign ranks using longest path from sources."""
    ranks: dict[str, int] = {}

    # Find sources (nodes with no incoming edges)
    sources = [n for n in all_nodes if not rev_adj.get(n)]
    if not sources:
        # Cycle — pick arbitrary start
        sources = [next(iter(all_nodes))]

    # BFS from sources, assigning max depth
    queue = deque(sources)
    for s in sources:
        ranks[s] = 0

    while queue:
        node = queue.popleft()
        for child in adj.get(node, []):
            new_rank = ranks[node] + 1
            if child not in ranks or ranks[child] < new_rank:
                ranks[child] = new_rank
                queue.append(child)

    # Assign rank 0 to any unranked nodes
    for n in all_nodes:
        if n not in ranks:
            ranks[n] = 0

    return ranks


def _barycenter_sort(
    rank_nodes: list[str],
    nodes: dict[str, _Node],
    neighbor_adj: dict[str, list[str]],
    all_nodes: dict[str, _Node],
) -> None:
    """Sort nodes in a rank by barycenter of their neighbors."""
    barycenters: dict[str, float] = {}
    for label in rank_nodes:
        neighbors = neighbor_adj.get(label, [])
        neighbor_orders = [
            all_nodes[n].order for n in neighbors if n in all_nodes
        ]
        if neighbor_orders:
            barycenters[label] = sum(neighbor_orders) / len(neighbor_orders)
        else:
            barycenters[label] = nodes[label].order

    rank_nodes.sort(key=lambda n: barycenters.get(n, 0))
    for i, label in enumerate(rank_nodes):
        nodes[label].order = float(i)


def _assign_coordinates(
    by_rank: dict[int, list[str]],
    nodes: dict[str, _Node],
    cfg: LayoutEngineConfig,
    direction: str,
    max_rank: int,
) -> None:
    """Assign x, y coordinates based on rank and order."""
    # Find the widest rank for centering
    max_rank_width = 0
    for rank, rank_nodes in by_rank.items():
        real_nodes = [n for n in rank_nodes if not nodes[n].is_virtual]
        if real_nodes:
            total_w = sum(nodes[n].width for n in real_nodes)
            total_w += (len(real_nodes) - 1) * cfg.node_spacing
            max_rank_width = max(max_rank_width, total_w)

    # Precompute the maximum node height/width per rank for consistent spacing
    max_height_per_rank: dict[int, float] = {}
    max_width_per_rank: dict[int, float] = {}
    for rank, rank_nodes in by_rank.items():
        real_nodes = [n for n in rank_nodes if not nodes[n].is_virtual]
        max_height_per_rank[rank] = max((nodes[n].height for n in real_nodes), default=cfg.default_height)
        max_width_per_rank[rank] = max((nodes[n].width for n in real_nodes), default=cfg.default_width)

    # Precompute cumulative Y/X offsets for each rank so all nodes in a rank share the same baseline
    rank_offsets: dict[int, float] = {}
    if direction in ("TB", "BT"):
        cumulative = cfg.start_y
        ordered_ranks = sorted(by_rank.keys()) if direction == "TB" else sorted(by_rank.keys(), reverse=True)
        for r in ordered_ranks:
            rank_offsets[r] = cumulative
            cumulative += max_height_per_rank[r] + cfg.rank_spacing
    else:
        cumulative = cfg.start_x
        ordered_ranks = sorted(by_rank.keys()) if direction == "LR" else sorted(by_rank.keys(), reverse=True)
        for r in ordered_ranks:
            rank_offsets[r] = cumulative
            cumulative += max_width_per_rank[r] + cfg.rank_spacing

    for rank, rank_nodes in sorted(by_rank.items()):
        # Calculate total width of this rank
        real_nodes = [n for n in rank_nodes if not nodes[n].is_virtual]

        if direction in ("TB", "BT"):
            # Horizontal arrangement within rank
            total_w = sum(nodes[n].width for n in real_nodes)
            total_w += (len(real_nodes) - 1) * cfg.node_spacing if real_nodes else 0
            offset = (max_rank_width - total_w) / 2

            x_cursor = cfg.start_x + offset
            rank_y_pos = rank_offsets[rank]

            for label in rank_nodes:
                node = nodes[label]
                if node.is_virtual:
                    node.y = rank_y_pos
                    node.x = x_cursor
                    continue
                node.x = x_cursor
                node.y = rank_y_pos
                x_cursor += node.width + cfg.node_spacing
        else:
            # Vertical arrangement within rank (LR/RL)
            total_h = sum(nodes[n].height for n in real_nodes)
            total_h += (len(real_nodes) - 1) * cfg.node_spacing if real_nodes else 0

            y_cursor = cfg.start_y
            rank_x_pos = rank_offsets[rank]

            for label in rank_nodes:
                node = nodes[label]
                if node.is_virtual:
                    node.x = rank_x_pos
                    node.y = y_cursor
                    continue
                node.x = rank_x_pos
                node.y = y_cursor
                y_cursor += node.height + cfg.node_spacing

    # Position virtual nodes at barycenter of real endpoints
    for label, node in nodes.items():
        if not node.is_virtual:
            continue
        # Simple: just center between the rank positions
        # (already roughly positioned by _assign_coordinates)


def _find_virtual_chain(
    src_label: str,
    tgt_label: str,
    expanded_edges: list[tuple[str, str]],
    nodes: dict[str, _Node],
) -> list[str]:
    """Find the chain of virtual nodes between src and tgt."""
    _dummy = _Node(id="", label="", width=0, height=0)
    # Build forward adjacency for the chain
    chain_adj: dict[str, str] = {}
    for s, t in expanded_edges:
        if nodes.get(s, _dummy).is_virtual or nodes.get(t, _dummy).is_virtual:
            chain_adj[s] = t

    chain: list[str] = []
    current = src_label
    visited: set[str] = set()
    while current in chain_adj and current not in visited:
        visited.add(current)
        nxt = chain_adj[current]
        if nxt == tgt_label:
            break
        if nodes.get(nxt, _dummy).is_virtual:
            chain.append(nxt)
            current = nxt
        else:
            break
    return chain


# ---------------------------------------------------------------------------
# Obstacle-Aware Orthogonal Edge Routing
# ---------------------------------------------------------------------------

def route_edges_around_obstacles(
    diagram: Diagram,
    margin: float = 15,
) -> int:
    """Reroute ALL edges in a diagram so they don't cross any shape bounding box.

    Uses A*-based orthogonal routing on a visibility grid built from
    all vertex bounding boxes.  Each edge gets waypoints that navigate
    around every obstacle (every vertex that is not the edge's own
    source or target).

    Args:
        diagram: The diagram whose edges will be rerouted.
        margin: Clearance around shapes (pixels).

    Returns:
        Number of edges rerouted.
    """
    bounds = get_all_vertex_bounds(diagram)
    if not bounds:
        return 0

    count = 0
    for cell in diagram.cells:
        if not cell.edge or not cell.source or not cell.target:
            continue
        src_b = bounds.get(cell.source)
        tgt_b = bounds.get(cell.target)
        if not src_b or not tgt_b:
            continue

        # Obstacles = every vertex except source and target
        obstacles = [
            b for cid, b in bounds.items()
            if cid != cell.source and cid != cell.target
        ]

        waypoints = _route_orthogonal_astar(
            src_b, tgt_b, obstacles, margin, grid_snap=diagram.grid_size,
        )

        if cell.geometry is None:
            cell.geometry = Geometry(relative=True)
        cell.geometry.points = waypoints
        count += 1

    return count


def _route_orthogonal_astar(
    src: CellBounds,
    tgt: CellBounds,
    obstacles: list[CellBounds],
    margin: float,
    grid_snap: int = 10,
) -> list[Point]:
    """A*-based orthogonal router that avoids all obstacle bounding boxes.

    Algorithm:
    1. Build a sparse set of candidate X and Y coordinates from the edges
       of every obstacle (with margin), plus source/target centers.
    2. Build a visibility graph on those grid lines — an edge exists
       between two adjacent grid-intersection points if the segment
       between them does not pass through any obstacle.
    3. Run A* from source exit-point to target entry-point.
    4. Simplify the resulting path to remove redundant collinear waypoints.

    Returns:
        Waypoints (may be empty for trivially-routable edges).
    """
    sx, sy = src.cx, src.cy
    tx, ty = tgt.cx, tgt.cy

    # Fast exit: if the straight line doesn't cross anything, skip routing
    if not _any_obstacle_on_segment(sx, sy, tx, ty, obstacles, margin):
        return []

    # --- 1. Build candidate coordinates ---
    xs: set[float] = {sx, tx}
    ys: set[float] = {sy, ty}
    for obs in obstacles:
        xs.add(snap_to_grid(obs.x - margin, grid_snap))
        xs.add(snap_to_grid(obs.right + margin, grid_snap))
        ys.add(snap_to_grid(obs.y - margin, grid_snap))
        ys.add(snap_to_grid(obs.bottom + margin, grid_snap))
    # Add source/target exit/entry points
    xs.add(snap_to_grid(src.right + margin, grid_snap))
    xs.add(snap_to_grid(src.x - margin, grid_snap))
    ys.add(snap_to_grid(src.bottom + margin, grid_snap))
    ys.add(snap_to_grid(src.y - margin, grid_snap))
    xs.add(snap_to_grid(tgt.right + margin, grid_snap))
    xs.add(snap_to_grid(tgt.x - margin, grid_snap))
    ys.add(snap_to_grid(tgt.bottom + margin, grid_snap))
    ys.add(snap_to_grid(tgt.y - margin, grid_snap))

    sorted_xs = sorted(xs)
    sorted_ys = sorted(ys)

    # --- 2. Build nodes + adjacency ---
    # Node = (xi, yi) indices into sorted_xs / sorted_ys
    # A segment between adjacent nodes is passable if no obstacle blocks it.
    node_count_x = len(sorted_xs)
    node_count_y = len(sorted_ys)

    # Quick lookup: is a point inside any obstacle?
    def _blocked(px: float, py: float) -> bool:
        for obs in obstacles:
            if (obs.x - margin / 2 < px < obs.right + margin / 2 and
                    obs.y - margin / 2 < py < obs.bottom + margin / 2):
                return True
        return False

    def _segment_blocked(x1: float, y1: float, x2: float, y2: float) -> bool:
        """Check if an orthogonal segment passes through any obstacle."""
        for obs in obstacles:
            ex = CellBounds(obs.x - margin / 2, obs.y - margin / 2,
                            obs.width + margin, obs.height + margin)
            if _seg_hits_rect(x1, y1, x2, y2, ex):
                return True
        return False

    # Find closest unblocked grid node to source / target centers
    def _closest_node(px: float, py: float) -> tuple[int, int]:
        best: tuple[int, int] | None = None
        best_dist = float('inf')
        for xi in range(node_count_x):
            for yi in range(node_count_y):
                gx, gy = sorted_xs[xi], sorted_ys[yi]
                if _blocked(gx, gy):
                    continue
                d = abs(gx - px) + abs(gy - py)
                if d < best_dist:
                    best_dist = d
                    best = (xi, yi)
        return best or (0, 0)

    start = _closest_node(sx, sy)
    goal = _closest_node(tx, ty)

    if start == goal:
        return []

    # --- 3. A* search ---
    # State = (xi, yi)
    open_set: list[tuple[float, tuple[int, int]]] = []
    heapq.heappush(open_set, (0.0, start))
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    g_score: dict[tuple[int, int], float] = {start: 0.0}

    goal_x = sorted_xs[goal[0]]
    goal_y = sorted_ys[goal[1]]

    def _h(node: tuple[int, int]) -> float:
        return abs(sorted_xs[node[0]] - goal_x) + abs(sorted_ys[node[1]] - goal_y)

    found = False
    while open_set:
        _, current = heapq.heappop(open_set)
        if current == goal:
            found = True
            break

        xi, yi = current
        cx_val, cy_val = sorted_xs[xi], sorted_ys[yi]

        # Neighbors: move along grid lines to adjacent coordinates
        for dxi, dyi in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nxi, nyi = xi + dxi, yi + dyi
            if nxi < 0 or nxi >= node_count_x or nyi < 0 or nyi >= node_count_y:
                continue
            nx_val, ny_val = sorted_xs[nxi], sorted_ys[nyi]

            # Check if segment is blocked
            if _segment_blocked(cx_val, cy_val, nx_val, ny_val):
                continue

            dist = abs(nx_val - cx_val) + abs(ny_val - cy_val)
            # Add bend penalty to prefer fewer turns
            parent = came_from.get(current)
            if parent is not None:
                prev_dx = xi - parent[0]
                prev_dy = yi - parent[1]
                if (prev_dx, prev_dy) != (dxi, dyi):
                    dist += 5  # bend penalty

            tent_g = g_score[current] + dist
            neighbor = (nxi, nyi)
            if tent_g < g_score.get(neighbor, float('inf')):
                g_score[neighbor] = tent_g
                f = tent_g + _h(neighbor)
                came_from[neighbor] = current
                heapq.heappush(open_set, (f, neighbor))

    if not found:
        # Fallback: simple L-shaped route going around
        return _fallback_route(src, tgt, obstacles, margin, grid_snap)

    # --- 4. Reconstruct path ---
    path: list[tuple[float, float]] = []
    node: tuple[int, int] | None = goal
    while node is not None:
        path.append((sorted_xs[node[0]], sorted_ys[node[1]]))
        node = came_from.get(node)
    path.reverse()

    # --- 5. Simplify: remove collinear intermediate points ---
    simplified = _simplify_path(path)

    # Convert to Point list (skip first/last — those are src/tgt centers)
    waypoints: list[Point] = []
    for wx, wy in simplified:
        waypoints.append(Point(
            snap_to_grid(wx, grid_snap),
            snap_to_grid(wy, grid_snap),
        ))

    return waypoints


def _any_obstacle_on_segment(
    x1: float, y1: float, x2: float, y2: float,
    obstacles: list[CellBounds], margin: float,
) -> bool:
    """Check if ANY obstacle bounding box (expanded by margin) intersects
    the straight line from (x1,y1) to (x2,y2)."""
    for obs in obstacles:
        ex = CellBounds(obs.x - margin, obs.y - margin,
                        obs.width + 2 * margin, obs.height + 2 * margin)
        if _line_intersects_rect(x1, y1, x2, y2, ex):
            return True
    return False


def _line_intersects_rect(
    x1: float, y1: float, x2: float, y2: float,
    rect: CellBounds,
) -> bool:
    """Liang-Barsky parametric clipping test: does segment (x1,y1)-(x2,y2) cross rect?"""
    dx = x2 - x1
    dy = y2 - y1

    t0, t1 = 0.0, 1.0
    for edge_p, edge_q in [
        (-dx, x1 - rect.x),
        (dx, rect.right - x1),
        (-dy, y1 - rect.y),
        (dy, rect.bottom - y1),
    ]:
        if abs(edge_p) < 1e-9:
            if edge_q < 0:
                return False
        else:
            t = edge_q / edge_p
            if edge_p < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
    return t0 <= t1


def _seg_hits_rect(
    x1: float, y1: float, x2: float, y2: float,
    rect: CellBounds,
) -> bool:
    """Check if an orthogonal segment passes through a rectangle."""
    if abs(x1 - x2) < 0.5:  # Vertical segment
        min_y, max_y = min(y1, y2), max(y1, y2)
        return (rect.x <= x1 <= rect.right and
                max_y >= rect.y and min_y <= rect.bottom)
    if abs(y1 - y2) < 0.5:  # Horizontal segment
        min_x, max_x = min(x1, x2), max(x1, x2)
        return (rect.y <= y1 <= rect.bottom and
                max_x >= rect.x and min_x <= rect.right)
    return _line_intersects_rect(x1, y1, x2, y2, rect)


def _simplify_path(path: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Remove collinear intermediate points from a path."""
    if len(path) <= 2:
        return path[1:-1] if len(path) == 2 else []

    result: list[tuple[float, float]] = [path[0]]
    for i in range(1, len(path) - 1):
        px, py = path[i - 1]
        cx, cy = path[i]
        nx, ny = path[i + 1]
        # Keep point if direction changes
        dx1 = cx - px
        dy1 = cy - py
        dx2 = nx - cx
        dy2 = ny - cy
        if (abs(dx1) > 0.5 and abs(dy2) > 0.5) or (abs(dy1) > 0.5 and abs(dx2) > 0.5):
            result.append((cx, cy))
    result.append(path[-1])

    # Strip first and last (those are source/target exit/entry points)
    # — keep only the intermediate waypoints
    if len(result) >= 2:
        return result[1:-1]
    return []


def _fallback_route(
    src: CellBounds, tgt: CellBounds,
    obstacles: list[CellBounds], margin: float,
    grid_snap: int,
) -> list[Point]:
    """Simple 3-segment route when A* can't find a path."""
    # Try going wide: pick a Y above/below all obstacles, or X left/right
    all_tops = [o.y for o in obstacles]
    all_bottoms = [o.bottom for o in obstacles]
    route_above = (min(all_tops) - margin * 2) if all_tops else src.cy
    route_below = (max(all_bottoms) + margin * 2) if all_bottoms else src.cy

    mid_y = (src.cy + tgt.cy) / 2
    route_y = route_above if abs(route_above - mid_y) < abs(route_below - mid_y) else route_below

    return [
        Point(snap_to_grid(src.cx, grid_snap), snap_to_grid(route_y, grid_snap)),
        Point(snap_to_grid(tgt.cx, grid_snap), snap_to_grid(route_y, grid_snap)),
    ]


# ---------------------------------------------------------------------------
# Overlap Removal
# ---------------------------------------------------------------------------

def _remove_overlaps(
    nodes: list[_Node],
    cfg: LayoutEngineConfig,
) -> None:
    """Remove overlaps between nodes using iterative push-apart.

    Uses a simple but effective algorithm:
    1. Sort nodes by position
    2. For each pair of overlapping nodes, push them apart
    3. Repeat until no overlaps remain
    """
    padding = cfg.overlap_padding

    for iteration in range(cfg.max_overlap_iterations):
        moved = False
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a = nodes[i]
                b = nodes[j]
                overlap_x, overlap_y = _compute_overlap(a, b, padding)

                if overlap_x > 0 and overlap_y > 0:
                    # Push apart along the axis with less overlap
                    if overlap_x < overlap_y:
                        push = overlap_x / 2 + 1
                        if a.x < b.x:
                            a.x -= push
                            b.x += push
                        else:
                            a.x += push
                            b.x -= push
                    else:
                        push = overlap_y / 2 + 1
                        if a.y < b.y:
                            a.y -= push
                            b.y += push
                        else:
                            a.y += push
                            b.y -= push
                    moved = True

        if not moved:
            break

    # Snap to grid after overlap removal
    for node in nodes:
        node.x = snap_to_grid(node.x, cfg.grid_size)
        node.y = snap_to_grid(node.y, cfg.grid_size)


def _compute_overlap(a: _Node, b: _Node, padding: float) -> tuple[float, float]:
    """Compute overlap between two nodes. Returns (overlap_x, overlap_y).
    Positive values mean overlap exists on that axis."""
    a_right = a.x + a.width + padding
    b_right = b.x + b.width + padding
    a_bottom = a.y + a.height + padding
    b_bottom = b.y + b.height + padding

    overlap_x = min(a_right, b_right) - max(a.x, b.x)
    overlap_y = min(a_bottom, b_bottom) - max(a.y, b.y)

    return overlap_x, overlap_y


# ---------------------------------------------------------------------------
# Auto-relayout existing diagrams
# ---------------------------------------------------------------------------

def relayout_diagram(
    diagram: Diagram,
    direction: str = "TB",
    config: LayoutEngineConfig | None = None,
    preserve_groups: bool = True,
) -> dict[str, tuple[float, float]]:
    """Reorganize all shapes in an existing diagram for cleaner layout.

    Analyzes the existing graph structure (vertices and edges) and
    recomputes positions using the Sugiyama algorithm.

    Args:
        diagram: The diagram to relayout.
        direction: TB, BT, LR, RL.
        config: Layout configuration.
        preserve_groups: If True, layout within groups separately.

    Returns:
        Dict mapping cell_id → (new_x, new_y).
    """
    cfg = config or LayoutEngineConfig()

    # Extract graph structure from existing cells
    vertices: dict[str, MxCell] = {}
    edges_data: list[tuple[str, str, str]] = []
    edge_cells: list[MxCell] = []

    for cell in diagram.cells:
        if cell.id in ("0", "1"):
            continue
        if cell.vertex and cell.geometry and not cell.geometry.relative:
            if cell.parent in ("1", "0", ""):
                vertices[cell.id] = cell
        elif cell.edge and cell.source and cell.target:
            edge_cells.append(cell)
            edges_data.append((cell.source, cell.target, cell.value or ""))

    if not vertices:
        return {}

    # If no edges, arrange in a grid
    if not edges_data:
        return _relayout_grid(list(vertices.values()), cfg)

    # Build node info
    nodes: dict[str, _Node] = {}
    for cid, cell in vertices.items():
        nodes[cid] = _Node(
            id=cid,
            label=cell.value,
            width=cell.geometry.width,
            height=cell.geometry.height,
        )

    # Filter edges to only include ones where both endpoints exist
    valid_edges: list[tuple[str, str, str]] = []
    adj: dict[str, list[str]] = defaultdict(list)
    rev_adj: dict[str, list[str]] = defaultdict(list)
    for src, tgt, lbl in edges_data:
        if src in nodes and tgt in nodes:
            valid_edges.append((src, tgt, lbl))
            adj[src].append(tgt)
            rev_adj[tgt].append(src)

    if not valid_edges:
        return _relayout_grid(list(vertices.values()), cfg)

    # Run Sugiyama steps
    back_edges = _find_back_edges(set(nodes.keys()), adj)

    effective_adj: dict[str, list[str]] = defaultdict(list)
    effective_rev: dict[str, list[str]] = defaultdict(list)
    for src in adj:
        for tgt in adj[src]:
            if (src, tgt) in back_edges:
                effective_adj[tgt].append(src)
                effective_rev[src].append(tgt)
            else:
                effective_adj[src].append(tgt)
                effective_rev[tgt].append(src)

    ranks = _assign_ranks_longest_path(set(nodes.keys()), effective_adj, effective_rev)
    for cid, rank in ranks.items():
        if cid in nodes:
            nodes[cid].rank = rank

    # Group by rank
    by_rank: dict[int, list[str]] = defaultdict(list)
    for cid, node in nodes.items():
        by_rank[node.rank].append(cid)

    max_rank = max(by_rank.keys()) if by_rank else 0

    # Initialize order
    for rank_nodes in by_rank.values():
        for i, cid in enumerate(rank_nodes):
            nodes[cid].order = float(i)

    # Crossing minimization
    for _ in range(cfg.barycenter_iterations):
        for r in range(1, max_rank + 1):
            _barycenter_sort(by_rank[r], nodes, effective_rev, nodes)
        for r in range(max_rank - 1, -1, -1):
            _barycenter_sort(by_rank[r], nodes, effective_adj, nodes)

    # Equalize node sizes within ranks for cleaner alignment
    _equalize_rank_sizes(by_rank, nodes, direction)

    # Coordinate assignment
    _assign_coordinates(by_rank, nodes, cfg, direction, max_rank)

    # Overlap removal
    _remove_overlaps(list(nodes.values()), cfg)

    # Apply new positions and equalized sizes
    moved: dict[str, tuple[float, float]] = {}
    for cid, node in nodes.items():
        cell = vertices[cid]
        new_x = snap_to_grid(node.x, cfg.grid_size)
        new_y = snap_to_grid(node.y, cfg.grid_size)
        cell.geometry.x = new_x
        cell.geometry.y = new_y
        cell.geometry.width = node.width
        cell.geometry.height = node.height
        moved[cid] = (new_x, new_y)

    # Route edges around shapes
    if cfg.route_edges:
        route_edges_around_obstacles(diagram, margin=cfg.edge_margin)

    return moved


def _relayout_grid(
    cells: list[MxCell],
    cfg: LayoutEngineConfig,
) -> dict[str, tuple[float, float]]:
    """Arrange cells in a grid when no edges exist."""
    cols = max(1, int(math.sqrt(len(cells))))
    moved: dict[str, tuple[float, float]] = {}

    for i, cell in enumerate(cells):
        col = i % cols
        row = i // cols
        x = snap_to_grid(
            cfg.start_x + col * (cell.geometry.width + cfg.node_spacing),
            cfg.grid_size,
        )
        y = snap_to_grid(
            cfg.start_y + row * (cell.geometry.height + cfg.rank_spacing),
            cfg.grid_size,
        )
        cell.geometry.x = x
        cell.geometry.y = y
        moved[cell.id] = (x, y)

    return moved


# ---------------------------------------------------------------------------
# Overlap Detection (for diagrams)
# ---------------------------------------------------------------------------

def find_overlapping_cells(diagram: Diagram, margin: float = 5) -> list[tuple[str, str]]:
    """Find all pairs of overlapping vertices in a diagram.

    Args:
        diagram: The diagram to check.
        margin: Minimum required gap between shapes.

    Returns:
        List of (cell_id_1, cell_id_2) pairs that overlap.
    """
    bounds = get_all_vertex_bounds(diagram)
    overlaps: list[tuple[str, str]] = []

    ids = list(bounds.keys())
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a = bounds[ids[i]]
            b = bounds[ids[j]]
            if a.intersects(b, margin):
                overlaps.append((ids[i], ids[j]))

    return overlaps


def resolve_overlaps(
    diagram: Diagram,
    margin: float = 20,
    max_iterations: int = 50,
) -> int:
    """Push apart overlapping shapes in a diagram.

    Non-destructive: only moves shapes that actually overlap.

    Args:
        diagram: The diagram to fix.
        margin: Minimum gap between shapes after resolution.
        max_iterations: Maximum iterations.

    Returns:
        Number of shapes moved.
    """
    moved_count = 0

    for iteration in range(max_iterations):
        bounds = get_all_vertex_bounds(diagram)
        any_overlap = False

        ids = list(bounds.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a_id, b_id = ids[i], ids[j]
                a_bounds = bounds[a_id]
                b_bounds = bounds[b_id]

                if not a_bounds.intersects(b_bounds, margin):
                    continue

                any_overlap = True
                # Find the cells
                a_cell = b_cell = None
                for cell in diagram.cells:
                    if cell.id == a_id:
                        a_cell = cell
                    elif cell.id == b_id:
                        b_cell = cell

                if not (a_cell and b_cell and a_cell.geometry and b_cell.geometry):
                    continue

                # Compute push direction and magnitude
                dx = b_bounds.cx - a_bounds.cx
                dy = b_bounds.cy - a_bounds.cy

                # How much overlap on each axis
                overlap_x = (a_bounds.width / 2 + b_bounds.width / 2 + margin) - abs(dx)
                overlap_y = (a_bounds.height / 2 + b_bounds.height / 2 + margin) - abs(dy)

                if overlap_x > 0 and overlap_y > 0:
                    if overlap_x < overlap_y:
                        push = overlap_x / 2 + 1
                        if dx >= 0:
                            a_cell.geometry.x = snap_to_grid(
                                a_cell.geometry.x - push, diagram.grid_size
                            )
                            b_cell.geometry.x = snap_to_grid(
                                b_cell.geometry.x + push, diagram.grid_size
                            )
                        else:
                            a_cell.geometry.x = snap_to_grid(
                                a_cell.geometry.x + push, diagram.grid_size
                            )
                            b_cell.geometry.x = snap_to_grid(
                                b_cell.geometry.x - push, diagram.grid_size
                            )
                    else:
                        push = overlap_y / 2 + 1
                        if dy >= 0:
                            a_cell.geometry.y = snap_to_grid(
                                a_cell.geometry.y - push, diagram.grid_size
                            )
                            b_cell.geometry.y = snap_to_grid(
                                b_cell.geometry.y + push, diagram.grid_size
                            )
                        else:
                            a_cell.geometry.y = snap_to_grid(
                                a_cell.geometry.y + push, diagram.grid_size
                            )
                            b_cell.geometry.y = snap_to_grid(
                                b_cell.geometry.y - push, diagram.grid_size
                            )
                    moved_count += 1

        if not any_overlap:
            break

    return moved_count


# ---------------------------------------------------------------------------
# Edge Label Positioning
# ---------------------------------------------------------------------------

def position_edge_labels(
    diagram: Diagram,
    margin: float = 8,
) -> int:
    """Reposition edge labels to avoid overlapping with shapes.

    Finds all edge labels (child cells of edges) and adjusts their
    offset to avoid colliding with vertex shapes.

    Args:
        diagram: The diagram to fix.
        margin: Minimum gap between labels and shapes.

    Returns:
        Number of labels repositioned.
    """
    bounds = get_all_vertex_bounds(diagram)
    count = 0

    for cell in diagram.cells:
        # Edge labels are vertex cells parented to an edge
        if not cell.vertex or cell.geometry is None:
            continue
        if not cell.geometry.relative:
            continue
        # Check if parent is an edge
        parent_cell = None
        for c in diagram.cells:
            if c.id == cell.parent and c.edge:
                parent_cell = c
                break
        if not parent_cell:
            continue

        # This is an edge label — check for collisions with shapes
        if cell.geometry.offset is None:
            cell.geometry.offset = Point(0, -10)

        # Try different offsets to avoid collisions
        original_offset = Point(cell.geometry.offset.x, cell.geometry.offset.y)
        offsets_to_try = [
            Point(0, -20),   # Above
            Point(0, 20),    # Below
            Point(20, 0),    # Right
            Point(-20, 0),   # Left
            Point(15, -15),  # Diagonal
            Point(-15, -15),
            Point(15, 15),
            Point(-15, 15),
        ]

        # Estimate label bounds (rough approximation)
        label_width = max(len(cell.value) * 7, 30)
        label_height = 16

        # Check if current position collides
        collides = False
        for cid, cb in bounds.items():
            if _label_collides(parent_cell, cell, cb, label_width, label_height, bounds, margin):
                collides = True
                break

        if not collides:
            continue

        # Try each offset
        best_offset = original_offset
        min_collisions = float('inf')
        for offset in offsets_to_try:
            cell.geometry.offset = offset
            collision_count = sum(
                1 for cid, cb in bounds.items()
                if _label_collides(parent_cell, cell, cb, label_width, label_height, bounds, margin)
            )
            if collision_count < min_collisions:
                min_collisions = collision_count
                best_offset = Point(offset.x, offset.y)
            if collision_count == 0:
                break

        cell.geometry.offset = best_offset
        if best_offset.x != original_offset.x or best_offset.y != original_offset.y:
            count += 1

    return count


def _label_collides(
    edge_cell: MxCell,
    label_cell: MxCell,
    shape_bounds: CellBounds,
    label_width: float,
    label_height: float,
    all_bounds: dict[str, CellBounds],
    margin: float,
) -> bool:
    """Check if an edge label approximately collides with a shape."""
    # Estimate label position from edge midpoint + offset
    src_bounds = all_bounds.get(edge_cell.source or "")
    tgt_bounds = all_bounds.get(edge_cell.target or "")
    if not src_bounds or not tgt_bounds:
        return False

    position = label_cell.geometry.x if label_cell.geometry else 0
    mid_x = src_bounds.cx + (tgt_bounds.cx - src_bounds.cx) * ((position + 1) / 2)
    mid_y = src_bounds.cy + (tgt_bounds.cy - src_bounds.cy) * ((position + 1) / 2)

    offset = label_cell.geometry.offset if label_cell.geometry else None
    if offset:
        mid_x += offset.x
        mid_y += offset.y

    label_bounds = CellBounds(
        mid_x - label_width / 2,
        mid_y - label_height / 2,
        label_width,
        label_height,
    )

    return label_bounds.intersects(shape_bounds, margin)


# ---------------------------------------------------------------------------
# Compact Layout
# ---------------------------------------------------------------------------

def compact_diagram(
    diagram: Diagram,
    margin: float = 40,
) -> int:
    """Compact a diagram by removing excessive whitespace.

    Shifts nodes closer together while maintaining relative ordering
    and minimum spacing constraints.

    Args:
        diagram: The diagram to compact.
        margin: Minimum gap between adjacent shapes.

    Returns:
        Number of shapes moved.
    """
    bounds = get_all_vertex_bounds(diagram)
    if len(bounds) < 2:
        return 0

    # Collect cells
    cells: dict[str, MxCell] = {}
    for cell in diagram.cells:
        if cell.id in bounds:
            cells[cell.id] = cell

    # Sort by position
    sorted_by_y = sorted(cells.keys(), key=lambda cid: bounds[cid].y)
    sorted_by_x = sorted(cells.keys(), key=lambda cid: bounds[cid].x)

    moved = 0

    # Compact vertically — close gaps between rows
    rows = _group_into_rows(sorted_by_y, bounds, threshold=20)
    current_y = bounds[sorted_by_y[0]].y  # Keep first row position
    for row in rows:
        # Find top-most cell in this row
        row_top = min(bounds[cid].y for cid in row)
        row_bottom = max(bounds[cid].bottom for cid in row)
        row_height = row_bottom - row_top

        # Move row to current_y
        shift = current_y - row_top
        if abs(shift) > 5:  # Only move if significant
            for cid in row:
                cell = cells[cid]
                if cell.geometry:
                    cell.geometry.y = snap_to_grid(
                        cell.geometry.y + shift, diagram.grid_size
                    )
                    moved += 1

        current_y += row_height + margin

    # Recompute bounds after vertical compaction so horizontal pass uses fresh positions
    bounds = get_all_vertex_bounds(diagram)

    # Compact horizontally — close gaps between columns within each row
    for row in rows:
        if len(row) < 2:
            continue
        row_sorted = sorted(row, key=lambda cid: bounds[cid].x)
        current_x = bounds[row_sorted[0]].x
        for cid in row_sorted:
            cell = cells[cid]
            if cell.geometry:
                shift = current_x - bounds[cid].x
                if abs(shift) > 5:
                    cell.geometry.x = snap_to_grid(current_x, diagram.grid_size)
                    moved += 1
                current_x = bounds[cid].x + bounds[cid].width + margin

    # Post-compact: align rows and columns for cleaner appearance
    moved += align_rank_baselines(diagram, threshold=20)
    moved += align_column_centers(diagram, threshold=20)

    return moved


def _group_into_rows(
    sorted_ids: list[str],
    bounds: dict[str, CellBounds],
    threshold: float = 20,
) -> list[list[str]]:
    """Group cells into rows based on Y proximity."""
    rows: list[list[str]] = []
    current_row: list[str] = []
    last_y: float = -float('inf')

    for cid in sorted_ids:
        cell_y = bounds[cid].y
        if not current_row or abs(cell_y - last_y) <= threshold:
            current_row.append(cid)
        else:
            rows.append(current_row)
            current_row = [cid]
        last_y = cell_y

    if current_row:
        rows.append(current_row)

    return rows


# ---------------------------------------------------------------------------
# Helper: Estimate Node Size
# ---------------------------------------------------------------------------

def _estimate_node_size(
    label: str,
    default_w: float,
    default_h: float,
) -> tuple[float, float]:
    """Estimate reasonable width/height from a label's text content."""
    text = re.sub(r"<br\s*/?>", "\n", label, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        lines = [text.strip() or "X"]

    max_chars = max((len(l) for l in lines), default=10)
    n_lines = max(len(lines), 1)

    w = max(default_w, min(280, max_chars * 8 + 20))
    h = max(default_h, min(200, n_lines * 22 + 16))
    return float(w), float(h)


# ---------------------------------------------------------------------------
# Edge Path Optimization
# ---------------------------------------------------------------------------

def optimize_edge_paths(
    diagram: Diagram,
    margin: float = 15,
    straighten_threshold: float = 8,
    nudge_spacing: float = 10,
) -> int:
    """Optimize all edge paths in a diagram for cleaner, shorter routing.

    This is a post-processing pass that improves already-routed edges.
    It applies several optimization strategies in sequence:

    1. **Simplify** — remove redundant collinear waypoints.
    2. **Straighten** — snap near-collinear segments into true straight lines.
    3. **Shorten** — attempt to reduce total wire length by removing
       unnecessary detours while respecting obstacles.
    4. **Center channels** — reposition waypoint segments to run equidistant
       between adjacent obstacles rather than hugging one side.
    5. **Separate overlapping edges** — nudge edges that share the same
       corridor so they don't visually stack on top of each other.
    6. **Grid-snap** — snap all resulting waypoints to the diagram grid.

    Args:
        diagram: The diagram whose edges will be optimized.
        margin: Clearance around shapes (pixels).
        straighten_threshold: Maximum pixel deviation before two segments
            are considered "nearly collinear" and merged into one.
        nudge_spacing: Minimum pixel gap between parallel overlapping edges.

    Returns:
        Number of edges whose waypoints were modified.
    """
    bounds = get_all_vertex_bounds(diagram)
    if not bounds:
        return 0

    grid = diagram.grid_size or 10
    modified = 0

    # Collect all edge cells
    edge_cells: list[MxCell] = [
        c for c in diagram.cells
        if c.edge and c.source and c.target
    ]

    # --- Phase 1–4: per-edge optimizations ---
    for cell in edge_cells:
        src_b = bounds.get(cell.source)
        tgt_b = bounds.get(cell.target)
        if not src_b or not tgt_b:
            continue

        pts = cell.geometry.points if cell.geometry else []
        if not pts:
            continue

        obstacles = [
            b for cid, b in bounds.items()
            if cid != cell.source and cid != cell.target
        ]

        original_count = len(pts)
        original_coords = [(p.x, p.y) for p in pts]

        # Build full path (source center → waypoints → target center)
        full_path = [(src_b.cx, src_b.cy)] + [(p.x, p.y) for p in pts] + [(tgt_b.cx, tgt_b.cy)]

        # 1. Remove collinear waypoints
        full_path = _opt_remove_collinear(full_path)

        # 2. Straighten near-collinear segments
        full_path = _opt_straighten(full_path, straighten_threshold)

        # 3. Shorten detours
        full_path = _opt_shorten(full_path, obstacles, margin)

        # 4. Center in channels
        full_path = _opt_center_channels(full_path, obstacles, margin)

        # Extract waypoints (strip src/tgt endpoints)
        new_waypoints = full_path[1:-1]

        # Grid-snap
        new_waypoints = [
            (snap_to_grid(x, grid), snap_to_grid(y, grid))
            for x, y in new_waypoints
        ]

        # Check if anything changed
        if new_waypoints != original_coords:
            if cell.geometry is None:
                cell.geometry = Geometry(relative=True)
            cell.geometry.points = [Point(x, y) for x, y in new_waypoints]
            modified += 1

    # --- Phase 5: separate overlapping / parallel edges ---
    modified += _opt_separate_parallel_edges(edge_cells, bounds, nudge_spacing, grid)

    return modified


def _opt_remove_collinear(
    path: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Remove intermediate points that lie on a straight line segment."""
    if len(path) <= 2:
        return path

    result = [path[0]]
    for i in range(1, len(path) - 1):
        px, py = path[i - 1]
        cx, cy = path[i]
        nx, ny = path[i + 1]
        # Keep point if direction changes (i.e., it's a real bend)
        same_x = abs(px - cx) < 1 and abs(cx - nx) < 1
        same_y = abs(py - cy) < 1 and abs(cy - ny) < 1
        if not same_x and not same_y:
            result.append((cx, cy))
        # If all three share the same X or same Y → collinear → skip middle
    result.append(path[-1])
    return result


def _opt_straighten(
    path: list[tuple[float, float]],
    threshold: float,
) -> list[tuple[float, float]]:
    """Snap near-horizontal / near-vertical segments into true axis-aligned ones.

    If two consecutive waypoints differ by less than *threshold* on one axis,
    align them exactly, turning a slightly diagonal segment into a clean
    orthogonal one.
    """
    if len(path) <= 1:
        return path

    result = [path[0]]
    for i in range(1, len(path)):
        px, py = result[-1]
        cx, cy = path[i]
        if abs(cx - px) < threshold and abs(cy - py) >= threshold:
            # Nearly vertical — align X
            cx = px
        elif abs(cy - py) < threshold and abs(cx - px) >= threshold:
            # Nearly horizontal — align Y
            cy = py
        result.append((cx, cy))
    return result


def _opt_shorten(
    path: list[tuple[float, float]],
    obstacles: list[CellBounds],
    margin: float,
) -> list[tuple[float, float]]:
    """Remove unnecessary detour waypoints.

    Attempts to skip intermediate waypoints when a direct segment between
    their neighbors doesn't cross any obstacle. This reduces total wire
    length and unnecessary bends.
    """
    if len(path) <= 3:
        return path

    # Iterate removal passes until stable
    changed = True
    while changed:
        changed = False
        i = 1
        while i < len(path) - 1:
            # Try removing waypoint i — check if segment (i-1)→(i+1) is clear
            px, py = path[i - 1]
            nx, ny = path[i + 1]
            if not _any_obstacle_on_segment(px, py, nx, ny, obstacles, margin):
                path = path[:i] + path[i + 1:]
                changed = True
                # Don't increment — check the new point at index i
            else:
                i += 1

    return path


def _opt_center_channels(
    path: list[tuple[float, float]],
    obstacles: list[CellBounds],
    margin: float,
) -> list[tuple[float, float]]:
    """Center edge segments within the channel between obstacles.

    For each horizontal or vertical segment of the path, find the nearest
    obstacles on either side and move the segment to the midpoint of the
    available channel. This prevents edges from running right along obstacle
    boundaries and produces more aesthetic, evenly-spaced routing.
    """
    if len(path) < 2:
        return path

    result = list(path)

    for i in range(len(result) - 1):
        ax, ay = result[i]
        bx, by = result[i + 1]

        if abs(ax - bx) < 1:
            # Vertical segment — try centering the X coordinate
            seg_x = ax
            seg_min_y = min(ay, by)
            seg_max_y = max(ay, by)

            # Find nearest obstacles to the left and right
            left_bound = -1e9
            right_bound = 1e9
            for obs in obstacles:
                # Obstacle must overlap the segment's Y range
                if obs.bottom + margin < seg_min_y or obs.y - margin > seg_max_y:
                    continue
                if obs.right + margin <= seg_x:
                    left_bound = max(left_bound, obs.right + margin)
                elif obs.x - margin >= seg_x:
                    right_bound = min(right_bound, obs.x - margin)

            if left_bound > -1e9 and right_bound < 1e9:
                channel_center = (left_bound + right_bound) / 2
                # Only adjust if the channel is wide enough and shift is modest
                channel_width = right_bound - left_bound
                if channel_width >= margin * 2 and abs(channel_center - seg_x) < channel_width * 0.4:
                    # Update both endpoints' X
                    result[i] = (channel_center, ay)
                    result[i + 1] = (channel_center, by)

        elif abs(ay - by) < 1:
            # Horizontal segment — try centering the Y coordinate
            seg_y = ay
            seg_min_x = min(ax, bx)
            seg_max_x = max(ax, bx)

            top_bound = -1e9
            bottom_bound = 1e9
            for obs in obstacles:
                if obs.right + margin < seg_min_x or obs.x - margin > seg_max_x:
                    continue
                if obs.bottom + margin <= seg_y:
                    top_bound = max(top_bound, obs.bottom + margin)
                elif obs.y - margin >= seg_y:
                    bottom_bound = min(bottom_bound, obs.y - margin)

            if top_bound > -1e9 and bottom_bound < 1e9:
                channel_center = (top_bound + bottom_bound) / 2
                channel_height = bottom_bound - top_bound
                if channel_height >= margin * 2 and abs(channel_center - seg_y) < channel_height * 0.4:
                    result[i] = (ax, channel_center)
                    result[i + 1] = (bx, channel_center)

    return result


def _opt_separate_parallel_edges(
    edge_cells: list[MxCell],
    bounds: dict[str, CellBounds],
    spacing: float,
    grid: int,
) -> int:
    """Separate edges that share overlapping corridors.

    When multiple edges run through the same horizontal or vertical corridor,
    nudge them apart so they're visually distinguishable rather than stacked.

    Returns the number of edges modified.
    """
    if len(edge_cells) < 2:
        return 0

    modified = 0

    # Group edges by the corridor they pass through.
    # A corridor key is (orientation, coordinate, range_start, range_end).
    # We'll use a simpler approach: find pairs of edges with overlapping segments.

    # Extract all horizontal / vertical segments from each edge
    @dataclass
    class _Segment:
        edge_idx: int
        point_idx: int       # index in waypoints list
        orientation: str     # "H" or "V"
        fixed_coord: float   # the Y for H segments, X for V segments
        range_start: float   # min of the variable coordinate
        range_end: float     # max of the variable coordinate

    segments: list[_Segment] = []
    for ei, cell in enumerate(edge_cells):
        pts = cell.geometry.points if cell.geometry else []
        if not pts:
            continue
        src_b = bounds.get(cell.source)
        tgt_b = bounds.get(cell.target)
        if not src_b or not tgt_b:
            continue

        full = [(src_b.cx, src_b.cy)] + [(p.x, p.y) for p in pts] + [(tgt_b.cx, tgt_b.cy)]
        for si in range(len(full) - 1):
            ax, ay = full[si]
            bx, by = full[si + 1]
            if abs(ay - by) < 1:
                # Horizontal segment
                segments.append(_Segment(
                    edge_idx=ei, point_idx=si,
                    orientation="H", fixed_coord=ay,
                    range_start=min(ax, bx), range_end=max(ax, bx),
                ))
            elif abs(ax - bx) < 1:
                # Vertical segment
                segments.append(_Segment(
                    edge_idx=ei, point_idx=si,
                    orientation="V", fixed_coord=ax,
                    range_start=min(ay, by), range_end=max(ay, by),
                ))

    # Find clusters of overlapping segments with same orientation
    # Two segments overlap if they have the same orientation,
    # similar fixed_coord, and overlapping range.
    processed: set[int] = set()
    for i in range(len(segments)):
        if i in processed:
            continue
        cluster = [i]
        for j in range(i + 1, len(segments)):
            if j in processed:
                continue
            si_seg = segments[i]
            sj_seg = segments[j]
            if si_seg.orientation != sj_seg.orientation:
                continue
            if si_seg.edge_idx == sj_seg.edge_idx:
                continue
            # Check if fixed coordinates are close (same corridor)
            if abs(si_seg.fixed_coord - sj_seg.fixed_coord) > spacing * 2:
                continue
            # Check if ranges overlap
            if si_seg.range_end < sj_seg.range_start or sj_seg.range_end < si_seg.range_start:
                continue
            cluster.append(j)
            processed.add(j)

        if len(cluster) < 2:
            continue

        processed.update(cluster)

        # Spread the cluster apart
        cluster_segs = [segments[k] for k in cluster]
        avg_coord = sum(s.fixed_coord for s in cluster_segs) / len(cluster_segs)
        n = len(cluster_segs)
        total_span = (n - 1) * spacing
        start_offset = avg_coord - total_span / 2

        for idx, seg in enumerate(cluster_segs):
            new_coord = snap_to_grid(start_offset + idx * spacing, grid)
            if abs(new_coord - seg.fixed_coord) < 1:
                continue

            cell = edge_cells[seg.edge_idx]
            pts = cell.geometry.points if cell.geometry else []
            if not pts:
                continue

            # The segment's point_idx is relative to the full path
            # (which includes src center at 0 and tgt center at end).
            # Waypoints index = point_idx - 1 (for first waypoint)
            # and point_idx (for second waypoint of the segment).
            # However, we can only modify actual waypoints (not src/tgt centers).
            wp_start = seg.point_idx - 1  # index into pts
            wp_end = seg.point_idx        # index into pts

            changed = False
            if seg.orientation == "H":
                if 0 <= wp_start < len(pts):
                    pts[wp_start] = Point(pts[wp_start].x, new_coord)
                    changed = True
                if 0 <= wp_end < len(pts):
                    pts[wp_end] = Point(pts[wp_end].x, new_coord)
                    changed = True
            else:  # "V"
                if 0 <= wp_start < len(pts):
                    pts[wp_start] = Point(new_coord, pts[wp_start].y)
                    changed = True
                if 0 <= wp_end < len(pts):
                    pts[wp_end] = Point(new_coord, pts[wp_end].y)
                    changed = True

            if changed:
                modified += 1

    return modified


# ---------------------------------------------------------------------------
# Automatic Design Improvements
# ---------------------------------------------------------------------------

def _equalize_rank_sizes(
    by_rank: dict[int, list[str]],
    nodes: dict[str, _Node],
    direction: str,
) -> None:
    """Make all real nodes in the same rank have uniform size.

    For TB/BT layouts: equalize height within each rank (same row height).
    For LR/RL layouts: equalize width within each rank (same column width).

    This produces cleaner alignment where all shapes in a row share
    the same baseline, similar to professional diagramming tools.
    """
    for rank, rank_nodes in by_rank.items():
        real = [n for n in rank_nodes if not nodes[n].is_virtual]
        if len(real) < 2:
            continue

        if direction in ("TB", "BT"):
            # Equalize heights within rank
            max_h = max(nodes[n].height for n in real)
            for n in real:
                nodes[n].height = max_h
        else:
            # Equalize widths within rank
            max_w = max(nodes[n].width for n in real)
            for n in real:
                nodes[n].width = max_w


def center_diagram_on_page(
    diagram: Diagram,
    margin: float = 50,
) -> int:
    """Center all diagram content on the page.

    Computes the bounding box of all top-level vertices and shifts
    everything so the content is centered horizontally and vertically
    on the page.  Also ensures a minimum margin from page edges.

    Args:
        diagram: The diagram to center.
        margin: Minimum margin from page edges.

    Returns:
        Number of cells moved.
    """
    bounds = get_all_vertex_bounds(diagram)
    if not bounds:
        return 0

    # Only consider top-level cells
    top_level_ids = set()
    for cell in diagram.cells:
        if cell.vertex and cell.geometry and not cell.geometry.relative:
            if cell.parent in ("0", "1", ""):
                top_level_ids.add(cell.id)

    tl_bounds = {cid: b for cid, b in bounds.items() if cid in top_level_ids}
    if not tl_bounds:
        return 0

    min_x = min(b.x for b in tl_bounds.values())
    min_y = min(b.y for b in tl_bounds.values())
    max_x = max(b.right for b in tl_bounds.values())
    max_y = max(b.bottom for b in tl_bounds.values())

    content_w = max_x - min_x
    content_h = max_y - min_y

    if diagram.page and diagram.page_width > 0 and diagram.page_height > 0:
        target_x = max(margin, (diagram.page_width - content_w) / 2)
        target_y = max(margin, (diagram.page_height - content_h) / 2)
    else:
        target_x = margin
        target_y = margin

    shift_x = target_x - min_x
    shift_y = target_y - min_y

    if abs(shift_x) < 5 and abs(shift_y) < 5:
        return 0

    moved = 0
    for cell in diagram.cells:
        if cell.id in ("0", "1"):
            continue
        if cell.vertex and cell.geometry and not cell.geometry.relative:
            if cell.parent in ("0", "1", ""):
                cell.geometry.x = snap_to_grid(
                    cell.geometry.x + shift_x, diagram.grid_size,
                )
                cell.geometry.y = snap_to_grid(
                    cell.geometry.y + shift_y, diagram.grid_size,
                )
                moved += 1

    return moved


def ensure_page_margins(
    diagram: Diagram,
    margin: float = 40,
) -> int:
    """Shift diagram content to ensure nothing is too close to page edges.

    Checks the top-left corner of the content bounding box and shifts
    all top-level cells so the minimum X and Y are at least ``margin``
    pixels from the page origin.

    Args:
        diagram: The diagram to adjust.
        margin: Minimum margin from page edges.

    Returns:
        Number of cells moved.
    """
    bounds = get_all_vertex_bounds(diagram)
    if not bounds:
        return 0

    # Only consider top-level cells for bounding box
    top_level_ids = set()
    for cell in diagram.cells:
        if cell.vertex and cell.geometry and not cell.geometry.relative:
            if cell.parent in ("0", "1", ""):
                top_level_ids.add(cell.id)

    tl_bounds = {cid: b for cid, b in bounds.items() if cid in top_level_ids}
    if not tl_bounds:
        return 0

    min_x = min(b.x for b in tl_bounds.values())
    min_y = min(b.y for b in tl_bounds.values())

    shift_x = max(0.0, margin - min_x)
    shift_y = max(0.0, margin - min_y)

    if shift_x < 1 and shift_y < 1:
        return 0

    moved = 0
    for cell in diagram.cells:
        if cell.id in ("0", "1"):
            continue
        if cell.vertex and cell.geometry and not cell.geometry.relative:
            if cell.parent in ("0", "1", ""):
                cell.geometry.x = snap_to_grid(
                    cell.geometry.x + shift_x, diagram.grid_size,
                )
                cell.geometry.y = snap_to_grid(
                    cell.geometry.y + shift_y, diagram.grid_size,
                )
                moved += 1

    return moved


def align_rank_baselines(
    diagram: Diagram,
    threshold: float = 20,
) -> int:
    """Align shapes that are approximately in the same row to share the exact same Y.

    Groups shapes into rows based on Y-center proximity, then aligns all
    shapes in each row to the row's average vertical center.  This fixes
    slight misalignments that occur during manual editing, overlap
    resolution, or other layout passes.

    Args:
        diagram: The diagram to adjust.
        threshold: Maximum Y-center difference (px) to consider shapes
            as belonging to the same row.

    Returns:
        Number of cells adjusted.
    """
    bounds = get_all_vertex_bounds(diagram)
    if len(bounds) < 2:
        return 0

    cells: dict[str, MxCell] = {}
    for cell in diagram.cells:
        if cell.id in bounds and cell.parent in ("0", "1", ""):
            cells[cell.id] = cell

    if len(cells) < 2:
        return 0

    # Group into rows by Y-center proximity
    sorted_ids = sorted(cells.keys(), key=lambda cid: bounds[cid].cy)
    rows: list[list[str]] = []
    current_row: list[str] = []
    last_cy: float = -1e9

    for cid in sorted_ids:
        cy = bounds[cid].cy
        if not current_row or abs(cy - last_cy) <= threshold:
            current_row.append(cid)
        else:
            rows.append(current_row)
            current_row = [cid]
        last_cy = cy
    if current_row:
        rows.append(current_row)

    adjusted = 0
    for row in rows:
        if len(row) < 2:
            continue

        # Align to average center Y
        avg_cy = sum(bounds[cid].cy for cid in row) / len(row)

        for cid in row:
            cell = cells.get(cid)
            if not cell or not cell.geometry:
                continue
            target_y = avg_cy - cell.geometry.height / 2
            target_y = snap_to_grid(target_y, diagram.grid_size)
            if abs(cell.geometry.y - target_y) > 1:
                cell.geometry.y = target_y
                adjusted += 1

    return adjusted


def align_column_centers(
    diagram: Diagram,
    threshold: float = 20,
) -> int:
    """Align shapes that are approximately in the same column to share the exact same X.

    Groups shapes into columns based on X-center proximity, then aligns
    all shapes in each column to the column's average horizontal center.

    Args:
        diagram: The diagram to adjust.
        threshold: Maximum X-center difference (px) to consider shapes
            as belonging to the same column.

    Returns:
        Number of cells adjusted.
    """
    bounds = get_all_vertex_bounds(diagram)
    if len(bounds) < 2:
        return 0

    cells: dict[str, MxCell] = {}
    for cell in diagram.cells:
        if cell.id in bounds and cell.parent in ("0", "1", ""):
            cells[cell.id] = cell

    if len(cells) < 2:
        return 0

    # Group into columns by X-center proximity
    sorted_ids = sorted(cells.keys(), key=lambda cid: bounds[cid].cx)
    cols: list[list[str]] = []
    current_col: list[str] = []
    last_cx: float = -1e9

    for cid in sorted_ids:
        cx = bounds[cid].cx
        if not current_col or abs(cx - last_cx) <= threshold:
            current_col.append(cid)
        else:
            cols.append(current_col)
            current_col = [cid]
        last_cx = cx
    if current_col:
        cols.append(current_col)

    adjusted = 0
    for col in cols:
        if len(col) < 2:
            continue

        # Align to average center X
        avg_cx = sum(bounds[cid].cx for cid in col) / len(col)

        for cid in col:
            cell = cells.get(cid)
            if not cell or not cell.geometry:
                continue
            target_x = avg_cx - cell.geometry.width / 2
            target_x = snap_to_grid(target_x, diagram.grid_size)
            if abs(cell.geometry.x - target_x) > 1:
                cell.geometry.x = target_x
                adjusted += 1

    return adjusted


def equalize_connected_sizes(
    diagram: Diagram,
    direction: str = "TB",
    threshold: float = 20,
) -> int:
    """Equalize the sizes of shapes in the same visual row or column.

    For TB/BT layouts, shapes in the same row get the same height.
    For LR/RL layouts, shapes in the same column get the same width.
    This creates a more professional, grid-like appearance.

    Args:
        diagram: The diagram to adjust.
        direction: Layout direction (TB, BT, LR, RL).
        threshold: Proximity threshold for grouping.

    Returns:
        Number of cells adjusted.
    """
    bounds = get_all_vertex_bounds(diagram)
    if len(bounds) < 2:
        return 0

    cells: dict[str, MxCell] = {}
    for cell in diagram.cells:
        if cell.id in bounds and cell.parent in ("0", "1", ""):
            cells[cell.id] = cell

    if len(cells) < 2:
        return 0

    adjusted = 0

    if direction in ("TB", "BT"):
        # Group into rows, equalize heights
        sorted_ids = sorted(cells.keys(), key=lambda cid: bounds[cid].cy)
        groups = _group_by_proximity(sorted_ids, bounds, "cy", threshold)

        for group in groups:
            if len(group) < 2:
                continue
            max_h = max(
                cells[cid].geometry.height
                for cid in group if cid in cells and cells[cid].geometry
            )
            for cid in group:
                cell = cells.get(cid)
                if cell and cell.geometry and cell.geometry.height < max_h:
                    cell.geometry.height = max_h
                    adjusted += 1
    else:
        # Group into columns, equalize widths
        sorted_ids = sorted(cells.keys(), key=lambda cid: bounds[cid].cx)
        groups = _group_by_proximity(sorted_ids, bounds, "cx", threshold)

        for group in groups:
            if len(group) < 2:
                continue
            max_w = max(
                cells[cid].geometry.width
                for cid in group if cid in cells and cells[cid].geometry
            )
            for cid in group:
                cell = cells.get(cid)
                if cell and cell.geometry and cell.geometry.width < max_w:
                    cell.geometry.width = max_w
                    adjusted += 1

    return adjusted


def _group_by_proximity(
    sorted_ids: list[str],
    bounds: dict[str, CellBounds],
    attr: str,
    threshold: float,
) -> list[list[str]]:
    """Group cell IDs by proximity of a center coordinate (cx or cy)."""
    groups: list[list[str]] = []
    current_group: list[str] = []
    last_val: float = -1e9

    for cid in sorted_ids:
        val = getattr(bounds[cid], attr)
        if not current_group or abs(val - last_val) <= threshold:
            current_group.append(cid)
        else:
            groups.append(current_group)
            current_group = [cid]
        last_val = val
    if current_group:
        groups.append(current_group)

    return groups
