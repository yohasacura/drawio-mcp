"""
Draw.io MCP Server — create draw.io XML diagrams via Model Context Protocol.

Exposes 5 tools that let an LLM agent create, modify, and save .drawio files
directly without a browser.

Tools:
  1. diagram  — lifecycle: create, open, save, import, list, get_xml
  2. draw     — content:  add/update/delete vertices, edges, groups, titles, legends
  3. style    — appearance: build styles, apply themes, list presets
  4. layout   — positioning: sugiyama DAG, tree, grid, flowchart, align, distribute,
                             polish, relayout, compact, reroute edges, resolve overlaps
  5. inspect  — read-only: list cells, check overlaps, list ports, get info
"""

from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from drawio_mcp.models import (
    CellBounds,
    Diagram,
    DrawioFile,
    Geometry,
    MxCell,
    PageFormat,
    Point,
    snap_to_grid,
)
from drawio_mcp.styles import (
    ColorTheme,
    EdgeStylePreset,
    Port,
    StyleBuilder,
    Themes,
    VertexStyle,
)
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
from drawio_mcp.layout_engine import (
    LayoutEngineConfig,
    align_column_centers,
    align_rank_baselines,
    center_diagram_on_page,
    compact_diagram,
    ensure_page_margins,
    equalize_connected_sizes,
    find_overlapping_cells,
    layout_sugiyama,
    optimize_edge_paths,
    position_edge_labels,
    relayout_diagram,
    resolve_overlaps,
    route_edges_around_obstacles,
)
from drawio_mcp.validation import (
    ValidationError,
    validate_action,
    validate_adjacency,
    validate_alignment,
    validate_bool,
    validate_color,
    validate_columns,
    validate_connection_dict,
    validate_dag_edge_dict,
    validate_direction,
    validate_edge_dict,
    validate_extra_dict,
    validate_file_path,
    validate_flowchart_step,
    validate_font_size,
    validate_grid_size,
    validate_legend_entry,
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
    validate_string,
    validate_update_dict,
    validate_vertex_dict,
    _DIAGRAM_ACTIONS,
    _DRAW_ACTIONS,
    _STYLE_ACTIONS,
    _LAYOUT_ACTIONS,
    _INSPECT_ACTIONS,
)

# ---------------------------------------------------------------------------
# Logging — suppress routine FastMCP INFO messages that VS Code shows
# as warnings (they go to stderr which VS Code labels [warning]).
# ---------------------------------------------------------------------------
logging.getLogger("mcp.server").setLevel(logging.WARNING)
logger = logging.getLogger("drawio-mcp")

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "drawio-mcp",
    instructions=(
        "MCP server for creating draw.io / diagrams.net XML files.\n\n"
        "=== ONLY 5 TOOLS — use the 'action' parameter to pick the operation ===\n\n"
        "1. diagram(action, ...) — lifecycle: create, save, load, import_xml,\n"
        "   list, get_xml, add_page.\n"
        "2. draw(action, ...) — content: add_vertices, add_edges, add_group,\n"
        "   update_cells, delete_cells, add_title, add_legend, build_dag,\n"
        "   build_full (vertices + edges + theme + title in one shot).\n"
        "3. style(action, ...) — appearance: build, apply_theme,\n"
        "   list_vertex_presets, list_edge_presets, list_themes.\n"
        "4. layout(action, ...) — positioning: sugiyama, tree, horizontal,\n"
        "   vertical, grid, flowchart, smart_connect, align, distribute,\n"
        "   polish, relayout, compact, reroute_edges, resolve_overlaps,\n"
        "   fix_labels, optimize_connections, resize_container.\n"
        "5. inspect(action, ...) — read-only: cells, overlaps, ports, info.\n\n"
        "=== RULES FOR GOOD DIAGRAMS ===\n"
        "- ALL coordinates (x, y) are ABSOLUTE page positions.\n"
        "- Style presets accept short suffixes (STORED_DATA, DECISION, etc.).\n"
        "- Children inside a group: place x,y WITHIN the group bounding box.\n"
        "- PREFER draw(action='build_dag') for architecture/dependency diagrams —\n"
        "  it handles everything in ONE call: layout + routing + theme + title.\n"
        "- PREFER draw(action='build_full') for manually-positioned diagrams.\n"
        "- ALL edges are automatically routed around shape bounding boxes.\n"
        "- Use layout(action='polish') for one-click cleanup of messy diagrams.\n"
        "- Labels support HTML: <b>Title</b><br>subtitle.\n"
        "- Use colors! BLUE_BOX, GREEN_BOX, ARCH_SERVICE, ARCH_DATABASE, etc.\n"
        "- Edge default = orthogonal+rounded routing. Use STRAIGHT or CURVED.\n"
        "- Vertex size auto-adjusts from label text (120x60 default).\n"
        "- Keep diagrams clean: max 15-20 shapes per page.\n"
        "- AUTO: Nodes in the same rank are equalized to uniform height.\n"
        "- AUTO: Polish aligns rows/columns, equalizes sizes, centers on page.\n"
        "- AUTO: build_dag/build_full enforce page margins automatically.\n\n"
        "=== AGENT GUIDE ===\n"
        "Read the resource drawio://guide/agent for detailed workflow patterns,\n"
        "best practices, common mistakes, and step-by-step recipes for every\n"
        "diagram type. Always consult it before building complex diagrams.\n"
    ),
)

# In-memory diagram registry: name -> DrawioFile
# Guarded by _diagrams_lock for thread-safety.
_diagrams: dict[str, DrawioFile] = {}
_diagrams_lock = threading.Lock()


# ===================================================================
# RESOURCES — provide style catalogs to the LLM
# ===================================================================

@mcp.resource("drawio://styles/vertices")
def vertex_style_catalog() -> str:
    """Return all available vertex style presets as a reference."""
    entries: list[str] = []
    for name in sorted(dir(VertexStyle)):
        if name.startswith("_"):
            continue
        val = getattr(VertexStyle, name)
        if isinstance(val, str):
            entries.append(f"  {name}: {val}")
    return "Available vertex style presets:\n" + "\n".join(entries)


@mcp.resource("drawio://styles/edges")
def edge_style_catalog() -> str:
    """Return all available edge style presets as a reference."""
    entries: list[str] = []
    for name in sorted(dir(EdgeStylePreset)):
        if name.startswith("_"):
            continue
        val = getattr(EdgeStylePreset, name)
        if isinstance(val, str):
            entries.append(f"  {name}: {val}")
    return "Available edge style presets:\n" + "\n".join(entries)


@mcp.resource("drawio://styles/themes")
def theme_catalog() -> str:
    """Return all available color themes."""
    entries: list[str] = []
    for name in sorted(dir(Themes)):
        if name.startswith("_"):
            continue
        val = getattr(Themes, name)
        if isinstance(val, ColorTheme):
            entries.append(
                f"  {name}: fill={val.fill} stroke={val.stroke} font={val.font}"
            )
    return "Available color themes:\n" + "\n".join(entries)


@mcp.resource("drawio://guide/agent")
def agent_guide() -> str:
    """Comprehensive guide for AI agents on how to use the draw.io MCP tools effectively."""
    return """# Draw.io MCP — Agent Guide

You have 5 tools. Each tool uses an `action` parameter to pick the operation.
This guide teaches you HOW and WHEN to use them for best results.

## Quick Decision Tree

1. Need a NEW diagram?  → diagram(action='create', name='...')
2. Architecture / dependency / flow diagram?  → draw(action='build_dag', ...)
   This is the FASTEST path — one call does layout + routing + theme.
3. Manually positioned diagram?  → draw(action='build_full', ...)
   You control exact x,y positions for every shape.
4. Diagram looks messy?  → layout(action='polish', ...)
   One-click cleanup: re-layout, align, compact, route edges, fix labels.
5. Need to inspect what you built?  → inspect(action='cells', ...)
6. Done? Save it  → diagram(action='save', name='...', file_path='...')

## Workflow Recipes

### Recipe 1: Architecture Diagram (recommended for most cases)
```
1. diagram(action='create', name='my-arch')
2. draw(action='build_dag', diagram_name='my-arch',
       edges=[{"source": "Client", "target": "API Gateway"},
              {"source": "API Gateway", "target": "Auth Service"},
              {"source": "API Gateway", "target": "User Service"},
              {"source": "User Service", "target": "PostgreSQL"}],
       node_styles={"PostgreSQL": "DATABASE", "Client": "USER"},
       theme='BLUE', title='System Architecture',
       direction='TB')
3. diagram(action='save', name='my-arch', file_path='my-arch.drawio')
```
That's it — 3 calls for a complete, professional diagram.

### Recipe 2: Flowchart
```
1. diagram(action='create', name='flow')
2. layout(action='flowchart', diagram_name='flow',
         steps=[{"label": "Start", "type": "terminator"},
                {"label": "Process Data", "type": "process"},
                {"label": "Valid?", "type": "decision"},
                {"label": "End", "type": "terminator"}],
         direction='TB')
3. style(action='apply_theme', diagram_name='flow', theme='GREEN')
4. diagram(action='save', name='flow', file_path='flow.drawio')
```

### Recipe 3: Manually Positioned Diagram
```
1. diagram(action='create', name='custom')
2. draw(action='build_full', diagram_name='custom',
       vertices=[{"label": "Web App", "x": 100, "y": 50, "style_preset": "BLUE_BOX"},
                 {"label": "API", "x": 100, "y": 200, "style_preset": "GREEN_BOX"},
                 {"label": "DB", "x": 100, "y": 350, "style_preset": "DATABASE"}],
       edges=[{"source_id": "<id1>", "target_id": "<id2>"},
              {"source_id": "<id2>", "target_id": "<id3>"}],
       theme='BLUE', title='My System')
```
Note: build_full auto-aligns nearby shapes, equalizes sizes, and enforces margins.

### Recipe 4: Edit an Existing Diagram
```
1. diagram(action='load', name='existing', file_path='existing.drawio')
2. inspect(action='cells', diagram_name='existing')  # see what's there
3. draw(action='add_vertices', diagram_name='existing',
       vertices=[{"label": "New Service", "x": 300, "y": 200}])
4. draw(action='add_edges', diagram_name='existing',
       edges=[{"source_id": "<existing_id>", "target_id": "<new_id>"}])
5. layout(action='polish', diagram_name='existing')  # clean up
6. diagram(action='save', name='existing', file_path='existing.drawio')
```

### Recipe 5: Tree / Org Chart
```
1. diagram(action='create', name='org')
2. layout(action='tree', diagram_name='org',
         adjacency={"CEO": ["CTO", "CFO", "COO"],
                    "CTO": ["VP Eng", "VP Product"],
                    "CFO": ["Controller"]},
         root='CEO', direction='TB')
3. style(action='apply_theme', diagram_name='org', theme='BLUE')
```

### Recipe 6: Simple Row or Column
```
layout(action='horizontal', diagram_name='d',
       labels=['Step 1', 'Step 2', 'Step 3'],
       connect=true, style_preset='ROUNDED_RECTANGLE')
```

## Tool-by-Tool Best Practices

### diagram()
- Always create BEFORE any draw/layout/style/inspect calls.
- Use descriptive names — they become the default filename.
- page_format: use 'A4_LANDSCAPE' for wide diagrams, 'A4_PORTRAIT' for tall.
- Use 'INFINITE' format for very large diagrams with many shapes.
- After load, always inspect(action='cells') to learn existing cell IDs.

### draw()
- PREFER build_dag over manual add_vertices + add_edges. It's faster and produces
  better results because it handles layout + routing + theme in one shot.
- build_dag edge format: {"source": "Label", "target": "Label"} — uses LABELS.
- add_edges edge format: {"source_id": "id", "target_id": "id"} — uses CELL IDs.
- node_styles maps LABELS to style presets: {"PostgreSQL": "DATABASE"}.
- Use short suffix names for styles: DATABASE, CLOUD, DECISION, SERVICE, QUEUE.
  The server resolves ARCH_DATABASE, FLOWCHART_DECISION, etc. automatically.
- Labels support HTML: "<b>Service</b><br><i>v2.1</i>" for rich text.
- For build_full, you MUST get vertex IDs from the result before adding edges
  that reference them. Call draw(add_vertices) first, capture IDs, then add_edges.
- delete_cells cascades: deleting a group deletes its children and connected edges.
- Use add_title and add_legend to make diagrams self-documenting.

### style()
- ALWAYS apply a theme for professional-looking diagrams. BLUE is the safest default.
- apply_theme after all shapes are added — it colors everything at once.
- Use skip_edges=true if you want edges to keep their default black color.
- build creates a raw style string — useful for custom_style parameters.
- Colored box presets: BLUE_BOX, GREEN_BOX, ORANGE_BOX, RED_BOX, YELLOW_BOX,
  PURPLE_BOX, GRAY_BOX, DARK_BOX, PINK_BOX, TEAL_BOX, WHITE_BOX.
- Architecture presets: ARCH_SERVICE, ARCH_DATABASE, ARCH_QUEUE, ARCH_CLOUD,
  ARCH_USER, ARCH_API, ARCH_GATEWAY, ARCH_CACHE, ARCH_FIREWALL, ARCH_SERVER.

### layout()
- polish is the "fix everything" button — use it after manual edits.
- polish does: relayout → resolve overlaps → compact → align rows/columns →
  equalize sizes → reroute edges → optimize paths → fix labels → center on page.
- relayout infers the graph structure from existing edges and repositions nodes.
- compact removes excess whitespace without breaking the layout.
- smart_connect is better than add_edges for complex wiring — it distributes
  ports evenly and routes around obstacles.
- align + distribute are for fine-tuning: align(cell_ids=[...], alignment='center').
- resize_container auto-sizes a group/swimlane to fit its children.
- Use direction='LR' for left-to-right flows, 'TB' for top-to-bottom (default).

### inspect()
- Use cells to get all cell IDs, labels, positions, and styles.
- Use overlaps to check quality — 0 overlaps means a clean diagram.
- Use info for a quick summary (page count, vertex/edge counts).
- Use ports to see all available connection port positions (TOP, BOTTOM, LEFT, etc.).

## Common Mistakes to Avoid

1. DON'T call add_vertices + add_edges when build_dag can do it all.
2. DON'T forget to create the diagram first — all tools need diagram_name.
3. DON'T use cell IDs in build_dag edges — use labels. build_dag creates the cells.
4. DON'T hardcode IDs — always capture them from return values.
5. DON'T place shapes at (0,0) — page margins are auto-enforced at 40px.
6. DON'T skip themes — unthemed diagrams look unprofessional.
7. DON'T manually position every shape when build_dag or tree layout can do it.
8. DON'T forget to save — diagrams are in-memory only until saved.
9. DON'T add too many shapes per page — keep it under 15-20 for readability.
   Use add_page for additional content.
10. DON'T worry about edge routing — it's all automatic.

## Size and Spacing Guidelines

- Default shape: 120×60 px. Auto-sized from label text.
- Rank spacing (vertical gap between layers): 100px default. Increase for dense diagrams.
- Node spacing (horizontal gap between siblings): 60px default.
- Grid size: 10px default. All positions snap to grid.
- For small diagrams (3-5 shapes): defaults work great.
- For medium diagrams (6-15 shapes): consider rank_spacing=120, node_spacing=80.
- For large diagrams (15+ shapes): use multiple pages, or INFINITE page format.

## Color Strategy

Use color to encode meaning:
- Blue  = core services / primary components
- Green = APIs / interfaces / entry points
- Orange = queues / async / gateways
- Red   = external / security / firewalls
- Purple = users / actors
- Gray  = infrastructure / background services
- Yellow = caches / temporary storage

Apply this consistently with node_styles in build_dag:
```
node_styles={
    "API Gateway": "GATEWAY",
    "PostgreSQL": "DATABASE",
    "Redis": "CACHE",
    "User": "USER",
    "Auth Service": "SERVICE"
}
```

## Automatic Quality Improvements

These happen transparently — you don't need to do anything:
- Nodes in the same rank are equalized to uniform height (TB/BT) or width (LR/RL).
- build_dag and build_full enforce page margins (content won't touch page edges).
- polish aligns rows and columns, equalizes sibling sizes, and centers content.
- compact removes whitespace AND aligns nearby shapes to clean baselines.
- All edge routing is automatic with obstacle avoidance.
- Edge labels are positioned to avoid collisions.
"""


# ===================================================================
# TOOL 1: diagram — lifecycle
# ===================================================================

@mcp.tool()
def diagram(
    action: str,
    name: str = "",
    file_path: str = "",
    xml_content: str = "",
    page_format: str = "A4_PORTRAIT",
    background: str = "none",
    grid: bool = True,
    grid_size: int = 10,
    page_name: str = "",
) -> str:
    """Diagram lifecycle management.

    Actions:
      create     — Create a new empty diagram. Params: name, page_format, background, grid, grid_size.
      save       — Save diagram to a .drawio file. Params: name, file_path.
      load       — Load a .drawio file from disk. Params: name, file_path.
      import_xml — Import draw.io XML string. Params: name, xml_content.
      list       — List all in-memory diagrams. No params needed.
      get_xml    — Get the raw XML of a diagram. Params: name.
      add_page   — Add a new page. Params: name, page_name.
      add_layer  — Add a new layer. Params: name, page_name (layer name).
                    Layers control visibility and z-ordering of shapes.
                    Use the returned layer_id as parent_id for shapes.

    Args:
        action: One of: create, save, load, import_xml, list, get_xml, add_page.
        name: Diagram name (used as key in memory and filename stem).
        file_path: Absolute path for save/load operations.
        xml_content: XML string for import_xml action.
        page_format: Page size for create — A4_PORTRAIT, A4_LANDSCAPE,
                     LETTER_PORTRAIT, LETTER_LANDSCAPE, INFINITE, etc.
        background: Background color (#RRGGBB) or "none".
        grid: Show grid (create only).
        grid_size: Grid spacing in pixels (create only).
        page_name: Name for add_page action.

    Returns:
        Result string or JSON depending on action.
    """
    try:
        action = validate_action(action, "diagram", _DIAGRAM_ACTIONS)
    except ValidationError as exc:
        return f"Error: {exc.message}"

    if action == "create":
        try:
            name = validate_non_empty_string(name, "name")
            page_format = validate_page_format(page_format)
            validate_color(background, "background", allow_none=True)
            validate_grid_size(grid_size)
        except ValidationError as exc:
            return f"Error: {exc.message}"
        fmt = PageFormat[page_format.upper()]
        df = DrawioFile()
        d = df.active_diagram
        d.name = name
        d.set_page_format(fmt)
        d.background = background
        d.grid = grid
        d.grid_size = grid_size
        with _diagrams_lock:
            _diagrams[name] = df
        return f"Diagram '{name}' created ({page_format})."

    elif action == "save":
        try:
            name = validate_non_empty_string(name, "name")
            validate_file_path(file_path, "file_path")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        df = _diagrams.get(name)
        if not df:
            return f"Error: diagram '{name}' not found."
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        xml = df.to_xml()
        path.write_text(xml, encoding="utf-8")
        return f"Diagram saved to {path.resolve()}"

    elif action == "load":
        try:
            name = validate_non_empty_string(name, "name")
            validate_file_path(file_path, "file_path")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        path = Path(file_path)
        if not path.exists():
            return f"Error: file '{file_path}' not found."
        xml = path.read_text(encoding="utf-8")
        return _import_xml_impl(name, xml)

    elif action == "import_xml":
        try:
            name = validate_non_empty_string(name, "name")
            validate_non_empty_string(xml_content, "xml_content")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        return _import_xml_impl(name, xml_content)

    elif action == "list":
        result: list[dict[str, Any]] = []
        for n, df in _diagrams.items():
            pages: list[dict[str, Any]] = []
            for i, d in enumerate(df.diagrams):
                vertex_count = sum(1 for c in d.cells if c.vertex)
                edge_count = sum(1 for c in d.cells if c.edge)
                pages.append({"index": i, "name": d.name,
                              "vertices": vertex_count, "edges": edge_count})
            result.append({"name": n, "pages": pages})
        return json.dumps(result, indent=2)

    elif action == "get_xml":
        try:
            name = validate_non_empty_string(name, "name")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        df = _diagrams.get(name)
        if not df:
            return f"Error: diagram '{name}' not found."
        return df.to_xml()

    elif action == "add_page":
        try:
            name = validate_non_empty_string(name, "name")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        df = _diagrams.get(name)
        if not df:
            return f"Error: diagram '{name}' not found."
        df.add_diagram(page_name or "Page-2")
        return f"Page '{page_name}' added to diagram '{name}'."

    elif action == "add_layer":
        try:
            name = validate_non_empty_string(name, "name")
            validate_non_empty_string(page_name, "page_name")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        df = _diagrams.get(name)
        if not df:
            return f"Error: diagram '{name}' not found."
        d = df.diagrams[0]
        layer_id = d.add_layer(page_name)
        return json.dumps({"layer_id": layer_id, "name": page_name})

    else:
        return f"Error: unknown diagram action '{action}'. Use: create, save, load, import_xml, list, get_xml, add_page, add_layer."


# ===================================================================
# TOOL 2: draw — content creation
# ===================================================================

@mcp.tool()
def draw(
    action: str,
    diagram_name: str = "",
    # -- vertices / edges / groups --
    vertices: list[dict[str, Any]] | None = None,
    edges: list[dict[str, Any]] | None = None,
    # -- update/delete --
    updates: list[dict[str, Any]] | None = None,
    cell_ids: list[str] | None = None,
    # -- title / legend --
    title: str = "",
    subtitle: str = "",
    legend_entries: list[dict[str, str]] | None = None,
    # -- group --
    group_label: str = "",
    group_x: float = 0,
    group_y: float = 0,
    group_width: float = 300,
    group_height: float = 200,
    group_style_preset: str = "SWIMLANE",
    group_custom_style: str = "",
    group_parent_id: str = "1",
    # -- build_dag specific --
    node_styles: dict[str, str] | None = None,
    edge_style_preset: str = "",
    direction: str = "TB",
    rank_spacing: float = 100,
    node_spacing: float = 60,
    # -- build_full / common --
    theme: str = "",
    page_index: int = 0,
    legend_x: float = 50,
    legend_y: float = 700,
    legend_title: str = "Legend",
) -> str:
    """Add, update, or delete diagram content.

    Actions:
      add_vertices — Add one or more vertices. Params: vertices (list of
                     {label, x, y, width?, height?, style_preset?, custom_style?,
                     parent_id?, cell_id?, tooltip?, link?, metadata?}).
      add_edges    — Add one or more edges. Params: edges (list of
                     {source_id, target_id, label?, style_preset?, custom_style?,
                     parent_id?, exit_port?, entry_port?}).
      add_group    — Add a container/group. Params: group_label, group_x, group_y,
                     group_width, group_height, group_style_preset, group_custom_style.
      update_cells — Update existing cells. Params: updates (list of
                     {cell_id, label?, style?, x?, y?, width?, height?}).
      delete_cells — Delete cells by ID (cascades). Params: cell_ids.
      add_title    — Add title/subtitle. Params: title, subtitle.
      add_legend   — Add color-coded legend. Params: legend_entries (list of
                     {label, fill_color, stroke_color}), legend_x, legend_y, legend_title.
      build_dag    — Build complete auto-laid-out directed graph in ONE call.
                     Params: edges (list of {source, target, label?}),
                     node_styles?, edge_style_preset?, theme?, title?, subtitle?,
                     direction?, rank_spacing?, node_spacing?.
      build_full   — Build complete manually-positioned diagram in ONE call.
                     Params: vertices, edges, theme?, title?, subtitle?.

    Args:
        action: One of the actions listed above.
        diagram_name: Target diagram name.
        vertices: List of vertex dicts for add_vertices / build_full.
        edges: List of edge dicts for add_edges / build_dag / build_full.
        updates: List of update dicts for update_cells.
        cell_ids: List of cell IDs for delete_cells.
        title: Title text for add_title / build_dag / build_full.
        subtitle: Subtitle text.
        legend_entries: Legend entries for add_legend.
        group_label: Label for add_group.
        group_x: X position for add_group.
        group_y: Y position for add_group.
        group_width: Width for add_group.
        group_height: Height for add_group.
        group_style_preset: Style preset for add_group.
        group_custom_style: Custom style for add_group.
        group_parent_id: Parent ID for add_group.
        node_styles: Dict mapping node labels to style presets (build_dag).
        edge_style_preset: Edge style preset name.
        direction: Layout direction — TB, BT, LR, RL.
        rank_spacing: Vertical spacing between layers (build_dag).
        node_spacing: Horizontal spacing between nodes (build_dag).
        theme: Color theme name (BLUE, GREEN, DARK, etc.).
        page_index: Page index (0-based).
        legend_x: X position for legend.
        legend_y: Y position for legend.
        legend_title: Title for legend box.

    Returns:
        JSON result with created cell IDs, or confirmation message.
    """
    try:
        action = validate_action(action, "draw", _DRAW_ACTIONS)
        validate_non_empty_string(diagram_name, "diagram_name")
    except ValidationError as exc:
        return f"Error: {exc.message}"
    df = _diagrams.get(diagram_name)
    if not df:
        return f"Error: diagram '{diagram_name}' not found."
    try:
        validate_page_index(page_index, len(df.diagrams))
    except ValidationError as exc:
        return f"Error: {exc.message}"
    d = df.diagrams[page_index]

    # ----- add_vertices -----
    if action == "add_vertices":
        verts = vertices or []
        try:
            validate_list(verts, "vertices", min_length=1)
            for i, v in enumerate(verts):
                validate_vertex_dict(v, i)
        except ValidationError as exc:
            return f"Error: {exc.message}"
        ids: list[str] = []
        for i, v in enumerate(verts):
            vstyle = v.get("custom_style") or _resolve_vertex_style(v.get("style_preset", ""))
            pid = v.get("parent_id", "1")
            vw, vh = _estimate_size(v["label"], v.get("width", 120), v.get("height", 60))
            gx = snap_to_grid(v["x"], d.grid_size)
            gy = snap_to_grid(v["y"], d.grid_size)
            rx, ry = _abs_to_relative(d, gx, gy, pid)
            cid = d.add_vertex(v["label"], rx, ry, vw, vh, vstyle, pid, v.get("cell_id") or None)
            # Apply metadata if provided
            cell = _find_cell(d, cid)
            if cell:
                if v.get("tooltip"):
                    cell.tooltip = v["tooltip"]
                if v.get("link"):
                    cell.link = v["link"]
                if v.get("metadata") and isinstance(v["metadata"], dict):
                    cell.metadata = v["metadata"]
            ids.append(cid)
        return json.dumps(ids)

    # ----- add_edges -----
    elif action == "add_edges":
        edge_list = edges or []
        try:
            validate_list(edge_list, "edges", min_length=1)
            for i, e in enumerate(edge_list):
                validate_edge_dict(e, i)
        except ValidationError as exc:
            return f"Error: {exc.message}"
        ids = []
        bounds = get_all_vertex_bounds(d)
        auto_pairs: list[tuple[str, str]] = []
        auto_indices: list[int] = []
        explicit_ports: dict[int, tuple[str, str]] = {}

        for i, e in enumerate(edge_list):
            ep_exit = e.get("exit_port", "")
            ep_entry = e.get("entry_port", "")
            if ep_exit or ep_entry:
                explicit_ports[i] = (ep_exit, ep_entry)
            else:
                auto_indices.append(i)
                auto_pairs.append((e["source_id"], e["target_id"]))

        batch_ports = distribute_ports_for_batch(auto_pairs, bounds) if auto_pairs else []

        for i, e in enumerate(edge_list):
            src_id = e["source_id"]
            tgt_id = e["target_id"]
            estyle = e.get("custom_style") or _resolve_edge_style(e.get("style_preset", ""))
            ep = e.get("parent_id", "")
            if not ep or ep == "1":
                ep = _find_common_parent(d, src_id, tgt_id)

            cid = d.add_edge(src_id, tgt_id, e.get("label", ""), estyle, ep)

            # Port resolution
            edge_cell = _find_cell(d, cid)
            if edge_cell:
                if i in explicit_ports:
                    exit_name, entry_name = explicit_ports[i]
                    ex, ey, enx, eny = _resolve_ports(d, src_id, tgt_id, exit_name, entry_name, False)
                else:
                    batch_idx = auto_indices.index(i) if i in auto_indices else -1
                    if batch_idx >= 0 and batch_idx < len(batch_ports):
                        (ex, ey), (enx, eny) = batch_ports[batch_idx]
                    else:
                        ex, ey, enx, eny = _resolve_ports(d, src_id, tgt_id, "", "", True)
                if ex is not None:
                    edge_cell.exit_x = ex
                    edge_cell.exit_y = ey
                if enx is not None:
                    edge_cell.entry_x = enx
                    edge_cell.entry_y = eny
            ids.append(cid)

        # Route edges around obstacles
        route_edges_around_obstacles(d, margin=15)
        return json.dumps(ids)

    # ----- add_group -----
    elif action == "add_group":
        try:
            validate_non_empty_string(group_label, "group_label")
            validate_number(group_x, "group_x")
            validate_number(group_y, "group_y")
            validate_positive_number(group_width, "group_width")
            validate_positive_number(group_height, "group_height")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        gstyle = group_custom_style or _resolve_vertex_style(group_style_preset)
        gx = snap_to_grid(group_x, d.grid_size)
        gy = snap_to_grid(group_y, d.grid_size)
        rx, ry = _abs_to_relative(d, gx, gy, group_parent_id)
        cid = d.add_group(group_label, rx, ry, group_width, group_height, gstyle, group_parent_id)
        return cid

    # ----- update_cells -----
    elif action == "update_cells":
        upd_list = updates or []
        try:
            validate_list(upd_list, "updates", min_length=1)
            for i, u in enumerate(upd_list):
                validate_update_dict(u, i)
        except ValidationError as exc:
            return f"Error: {exc.message}"
        results: list[str] = []
        for u in upd_list:
            cell = _find_cell(d, u["cell_id"])
            if not cell:
                results.append(f"not_found:{u['cell_id']}")
                continue
            if "label" in u:
                cell.value = u["label"]
            if "style" in u:
                cell.style = u["style"]
            if cell.geometry:
                if "x" in u:
                    cell.geometry.x = snap_to_grid(u["x"], d.grid_size)
                if "y" in u:
                    cell.geometry.y = snap_to_grid(u["y"], d.grid_size)
                if "width" in u:
                    cell.geometry.width = u["width"]
                if "height" in u:
                    cell.geometry.height = u["height"]
            results.append(f"ok:{u['cell_id']}")
        return json.dumps(results)

    # ----- delete_cells -----
    elif action == "delete_cells":
        try:
            validate_list(cell_ids or [], "cell_ids", min_length=1)
        except ValidationError as exc:
            return f"Error: {exc.message}"
        to_delete = set(cell_ids or [])
        changed = True
        while changed:
            changed = False
            for cell in d.cells:
                if cell.id in to_delete:
                    continue
                if cell.parent in to_delete:
                    to_delete.add(cell.id)
                    changed = True
                if cell.source in to_delete or cell.target in to_delete:
                    to_delete.add(cell.id)
                    changed = True
        original = len(d.cells)
        d.cells = [c for c in d.cells if c.id not in to_delete]
        return f"Removed {original - len(d.cells)} cell(s)."

    # ----- add_title -----
    elif action == "add_title":
        try:
            validate_non_empty_string(title, "title")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        title_style = _resolve_vertex_style("TITLE")
        ids = []
        tid = d.add_vertex(title, 50, 10, 400, 30, title_style)
        ids.append(tid)
        if subtitle:
            sub_style = _resolve_vertex_style("SUBTITLE")
            sid = d.add_vertex(subtitle, 50, 42, 400, 20, sub_style)
            ids.append(sid)
        return json.dumps(ids)

    # ----- add_legend -----
    elif action == "add_legend":
        entries = legend_entries or []
        try:
            validate_list(entries, "legend_entries", min_length=1)
            for i, entry in enumerate(entries):
                validate_legend_entry(entry, i)
            validate_number(legend_x, "legend_x")
            validate_number(legend_y, "legend_y")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        entry_h = 26
        legend_h = 26 + len(entries) * entry_h
        legend_style = (
            "swimlane;fontStyle=1;childLayout=stackLayout;horizontal=1;"
            "startSize=26;fillColor=#ffffff;horizontalStack=0;"
            "resizeParent=1;resizeParentMax=0;resizeLast=0;collapsible=0;"
            "marginBottom=0;strokeColor=#666666;html=1;"
        )
        lid = d.add_group(legend_title, legend_x, legend_y, 200, legend_h, legend_style)
        for i, entry in enumerate(entries):
            fill = entry.get("fill_color", "#f5f5f5")
            stroke = entry.get("stroke_color", "#666666")
            item_style = (
                f"text;align=left;verticalAlign=top;spacingLeft=4;spacingRight=4;"
                f"overflow=hidden;rotatable=0;points=[[0,0.5],[1,0.5]];"
                f"portConstraint=eastwest;fillColor={fill};strokeColor={stroke};html=1;"
            )
            cell = MxCell(
                id=d.next_id(), value=entry["label"], style=item_style,
                parent=lid, vertex=True,
                geometry=Geometry(x=0, y=26 + i * entry_h, width=200, height=entry_h),
            )
            d.cells.append(cell)
        return lid

    # ----- build_dag -----
    elif action == "build_dag":
        edge_list = edges or []
        try:
            validate_list(edge_list, "edges", min_length=1)
            for i, e in enumerate(edge_list):
                validate_dag_edge_dict(e, i)
            validate_direction(direction)
            validate_spacing(rank_spacing, "rank_spacing")
            validate_spacing(node_spacing, "node_spacing")
            if node_styles:
                validate_node_styles(node_styles)
        except ValidationError as exc:
            return f"Error: {exc.message}"
        edge_tuples = [(e["source"], e["target"], e.get("label", "")) for e in edge_list]

        resolved_styles: dict[str, str] | None = None
        if node_styles:
            resolved_styles = {lbl: _resolve_vertex_style(p) for lbl, p in node_styles.items()}

        e_style = _resolve_edge_style(edge_style_preset)
        cfg = LayoutEngineConfig(
            rank_spacing=rank_spacing, node_spacing=node_spacing,
            grid_size=d.grid_size, route_edges=True,
        )

        mapping = layout_sugiyama(d, edge_tuples, node_styles=resolved_styles,
                                  edge_style=e_style, config=cfg, direction=direction)

        # Auto-improve: ensure content respects page margins
        ensure_page_margins(d, margin=40)

        themed = _apply_theme_impl(d, theme)

        title_ids: list[str] = []
        if title:
            title_style = _resolve_vertex_style("TITLE")
            tid = d.add_vertex(title, 50, 10, 400, 30, title_style)
            title_ids.append(tid)
            if subtitle:
                sub_style = _resolve_vertex_style("SUBTITLE")
                sid = d.add_vertex(subtitle, 50, 42, 400, 20, sub_style)
                title_ids.append(sid)

        result_map = dict(mapping)
        result_map["__title_ids"] = title_ids
        result_map["__summary"] = (
            f"{len(mapping)} nodes, {len(edge_tuples)} edges, "
            f"direction={direction}, {themed} cells themed"
        )
        return json.dumps(result_map)

    # ----- build_full -----
    elif action == "build_full":
        verts = vertices or []
        edge_list = edges or []
        try:
            validate_list(verts, "vertices", min_length=1)
            for i, v in enumerate(verts):
                validate_vertex_dict(v, i)
            for i, e in enumerate(edge_list):
                validate_edge_dict(e, i)
        except ValidationError as exc:
            return f"Error: {exc.message}"

        # Create vertices
        vertex_ids: list[str] = []
        for v in verts:
            s = v.get("custom_style") or _resolve_vertex_style(v.get("style_preset", ""))
            pid = v.get("parent_id", "1")
            vw, vh = _estimate_size(v["label"], v.get("width", 120), v.get("height", 60))
            gx = snap_to_grid(v["x"], d.grid_size)
            gy = snap_to_grid(v["y"], d.grid_size)
            rx, ry = _abs_to_relative(d, gx, gy, pid)
            cid = d.add_vertex(v["label"], rx, ry, vw, vh, s, pid, v.get("cell_id") or None)
            vertex_ids.append(cid)

        # Create edges with smart ports
        edge_ids: list[str] = []
        bounds = get_all_vertex_bounds(d)
        for e in edge_list:
            src_id = e["source_id"]
            tgt_id = e["target_id"]
            s = _resolve_edge_style(e.get("style_preset", ""))
            ep = _find_common_parent(d, src_id, tgt_id)
            cid = d.add_edge(src_id, tgt_id, e.get("label", ""), s, ep)
            src_b = bounds.get(src_id)
            tgt_b = bounds.get(tgt_id)
            if src_b and tgt_b:
                (ex, ey), (enx, eny) = choose_best_ports(src_b, tgt_b)
                edge_cell = _find_cell(d, cid)
                if edge_cell:
                    edge_cell.exit_x = ex
                    edge_cell.exit_y = ey
                    edge_cell.entry_x = enx
                    edge_cell.entry_y = eny
            edge_ids.append(cid)

        route_edges_around_obstacles(d, margin=15)
        resolve_overlaps(d, margin=20)

        # Auto-improve: align baselines, equalize sizes, enforce margins
        align_rank_baselines(d, threshold=20)
        align_column_centers(d, threshold=20)
        equalize_connected_sizes(d, direction="TB")
        ensure_page_margins(d, margin=40)

        themed = _apply_theme_impl(d, theme)

        title_ids = []
        if title:
            title_style = _resolve_vertex_style("TITLE")
            tid = d.add_vertex(title, 50, 10, 400, 30, title_style)
            title_ids.append(tid)
            if subtitle:
                sub_style = _resolve_vertex_style("SUBTITLE")
                sid = d.add_vertex(subtitle, 50, 42, 400, 20, sub_style)
                title_ids.append(sid)

        return json.dumps({
            "vertex_ids": vertex_ids, "edge_ids": edge_ids,
            "title_ids": title_ids,
            "summary": f"{len(vertex_ids)} vertices, {len(edge_ids)} edges, {themed} themed",
        })

    else:
        return (
            f"Error: unknown draw action '{action}'. "
            "Use: add_vertices, add_edges, add_group, update_cells, delete_cells, "
            "add_title, add_legend, build_dag, build_full."
        )


# ===================================================================
# TOOL 3: style — appearance
# ===================================================================

@mcp.tool()
def style(
    action: str,
    diagram_name: str = "",
    # -- build --
    base: str = "",
    fill_color: str = "",
    stroke_color: str = "",
    stroke_width: float = 0,
    font_color: str = "",
    font_size: int = 0,
    font_family: str = "",
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    rounded: bool = False,
    dashed: bool = False,
    shadow: bool = False,
    opacity: int = 0,
    rotation: float = 0,
    theme: str = "",
    extra: dict[str, str] | None = None,
    # -- apply_theme --
    cell_ids: list[str] | None = None,
    skip_edges: bool = False,
    page_index: int = 0,
) -> str:
    """Style and appearance management.

    Actions:
      build              — Build a draw.io style string from parameters.
                           Returns the style string. Params: base, fill_color,
                           stroke_color, font_color, font_size, rounded, etc.
      apply_theme        — Apply a color theme to cells. Params: diagram_name,
                           theme (BLUE, GREEN, DARK, etc.), cell_ids? (all if omitted),
                           skip_edges?.
      list_vertex_presets — List all vertex style presets.
      list_edge_presets   — List all edge style presets.
      list_themes         — List all color themes.

    Args:
        action: One of: build, apply_theme, list_vertex_presets,
                list_edge_presets, list_themes.
        diagram_name: For apply_theme.
        base: Base style string for build.
        fill_color: Fill color (#RRGGBB) for build.
        stroke_color: Stroke color for build.
        stroke_width: Border width for build.
        font_color: Text color for build.
        font_size: Font size for build.
        font_family: Font family for build.
        bold: Bold text for build.
        italic: Italic text for build.
        underline: Underline for build.
        rounded: Rounded corners for build.
        dashed: Dashed border for build.
        shadow: Drop shadow for build.
        opacity: Opacity (0-100) for build.
        rotation: Rotation degrees for build.
        theme: Theme name for build or apply_theme.
        extra: Extra key=value pairs for build.
        cell_ids: Specific cells for apply_theme (omit for all).
        skip_edges: Don't theme edges for apply_theme.
        page_index: Page index for apply_theme.

    Returns:
        Style string, theme application count, or preset listing.
    """
    try:
        action = validate_action(action, "style", _STYLE_ACTIONS)
    except ValidationError as exc:
        return f"Error: {exc.message}"

    if action == "build":
        try:
            if fill_color:
                validate_color(fill_color, "fill_color")
            if stroke_color:
                validate_color(stroke_color, "stroke_color")
            if font_color:
                validate_color(font_color, "font_color")
            if font_size and font_size != 0:
                validate_font_size(font_size)
            if opacity and opacity != 0:
                validate_opacity(opacity)
            if extra:
                validate_extra_dict(extra)
        except ValidationError as exc:
            return f"Error: {exc.message}"
        sb = StyleBuilder(base)
        if theme:
            t = getattr(Themes, theme.upper(), None)
            if isinstance(t, ColorTheme):
                t.apply(sb)
        if fill_color:
            sb.fill_color(fill_color)
        if stroke_color:
            sb.stroke_color(stroke_color)
        if stroke_width:
            sb.stroke_width(stroke_width)
        if font_color:
            sb.font_color(font_color)
        if font_size:
            sb.font_size(font_size)
        if font_family:
            sb.font_family(font_family)
        if bold or italic or underline:
            sb.font_style(bold=bold, italic=italic, underline=underline)
        if rounded:
            sb.rounded(True)
        if dashed:
            sb.dashed(True)
        if shadow:
            sb.shadow(True)
        if opacity:
            sb.opacity(opacity)
        if rotation:
            sb.rotation(rotation)
        if extra:
            for k, v in extra.items():
                sb.set(k, v)
        return sb.build()

    elif action == "apply_theme":
        try:
            validate_non_empty_string(diagram_name, "diagram_name")
            validate_non_empty_string(theme, "theme")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        df = _diagrams.get(diagram_name)
        if not df:
            return f"Error: diagram '{diagram_name}' not found."
        try:
            validate_page_index(page_index, len(df.diagrams))
        except ValidationError as exc:
            return f"Error: {exc.message}"
        t = getattr(Themes, theme.upper(), None)
        if not isinstance(t, ColorTheme):
            return f"Error: unknown theme '{theme}'."
        d = df.diagrams[page_index]
        count = 0
        for cell in d.cells:
            if cell.id in ("0", "1"):
                continue
            if cell_ids and cell.id not in cell_ids:
                continue
            if skip_edges and cell.edge:
                continue
            if not cell.style:
                continue
            sb = StyleBuilder(cell.style)
            t.apply(sb)
            cell.style = sb.build()
            count += 1
        return f"Applied theme '{theme}' to {count} cell(s)."

    elif action == "list_vertex_presets":
        entries: list[str] = []
        for name in sorted(dir(VertexStyle)):
            if name.startswith("_"):
                continue
            val = getattr(VertexStyle, name)
            if isinstance(val, str):
                entries.append(f"  {name}: {val}")
        return "Vertex style presets:\n" + "\n".join(entries)

    elif action == "list_edge_presets":
        entries = []
        for name in sorted(dir(EdgeStylePreset)):
            if name.startswith("_"):
                continue
            val = getattr(EdgeStylePreset, name)
            if isinstance(val, str):
                entries.append(f"  {name}: {val}")
        return "Edge style presets:\n" + "\n".join(entries)

    elif action == "list_themes":
        entries = []
        for name in sorted(dir(Themes)):
            if name.startswith("_"):
                continue
            val = getattr(Themes, name)
            if isinstance(val, ColorTheme):
                entries.append(f"  {name}: fill={val.fill} stroke={val.stroke} font={val.font}")
        return "Color themes:\n" + "\n".join(entries)

    else:
        return (
            f"Error: unknown style action '{action}'. "
            "Use: build, apply_theme, list_vertex_presets, list_edge_presets, list_themes."
        )


# ===================================================================
# TOOL 4: layout — positioning
# ===================================================================

@mcp.tool()
def layout(
    action: str,
    diagram_name: str = "",
    # -- common --
    direction: str = "TB",
    page_index: int = 0,
    # -- sugiyama / tree --
    adjacency: dict[str, list[str]] | None = None,
    root: str = "",
    # -- sugiyama edge tuples --
    connections: list[dict[str, str]] | None = None,
    # -- horizontal / vertical / grid --
    labels: list[str] | None = None,
    columns: int = 3,
    style_preset: str = "ROUNDED_RECTANGLE",
    custom_style: str = "",
    edge_style_preset: str = "DEFAULT",
    custom_edge_style: str = "",
    edge_labels: list[str] | None = None,
    connect: bool = True,
    start_x: float = 50,
    start_y: float = 50,
    h_spacing: float = 60,
    v_spacing: float = 60,
    width: float = 120,
    height: float = 60,
    # -- flowchart --
    steps: list[dict[str, str]] | None = None,
    # -- align --
    cell_ids: list[str] | None = None,
    alignment: str = "center",
    # -- distribute --
    dist_direction: str = "horizontal",
    # -- resize_container --
    container_id: str = "",
    padding: float = 20,
    # -- polish / relayout / compact / reroute / overlaps --
    margin: float = 20,
    rank_spacing: float = 100,
    node_spacing: float = 60,
) -> str:
    """Layout and positioning operations.

    Actions:
      sugiyama          — Lay out a DAG from edges (same as PlantUML).
                          Use draw(action='build_dag') instead for the
                          all-in-one version with theme+title.
                          Params: connections (list of {source, target, label?}).
      tree              — Lay out a tree from adjacency list. Params:
                          adjacency, root, direction, style_preset, edge_style_preset,
                          h_spacing, v_spacing, width, height.
      horizontal        — Row of connected shapes. Params: labels, style_preset,
                          connect, edge_style_preset, edge_labels, start_x, start_y, etc.
      vertical          — Column of connected shapes. Same params as horizontal.
      grid              — Grid of shapes. Params: labels, columns, style_preset, etc.
      flowchart         — Create a flowchart from steps. Params: steps (list of
                          {label, type?}), direction.
      smart_connect     — Connect shapes with smart port distribution and
                          obstacle-aware routing. Params: connections (list of
                          {source_id, target_id, label?, exit_port?, entry_port?}),
                          edge_style_preset.
      align             — Align shapes. Params: cell_ids, alignment
                          (left/center/right/top/middle/bottom).
      distribute        — Distribute shapes evenly. Params: cell_ids,
                          dist_direction (horizontal/vertical).
      polish            — One-click cleanup: relayout + overlaps + compact +
                          route edges + fix labels. Params: direction.
      relayout          — Reorganize existing diagram. Params: direction,
                          rank_spacing, node_spacing.
      compact           — Remove excess whitespace. Params: margin.
      reroute_edges     — Reroute all edges around obstacles. Params: margin.
      resolve_overlaps  — Push apart overlapping shapes. Params: margin.
      fix_labels        — Fix edge label collisions. Params: margin.
      optimize_connections — Optimize all edge paths: remove redundant bends,
                          straighten near-collinear segments, shorten detours,
                          center edges in channels, separate overlapping edges.
                          Params: margin.
      resize_container  — Auto-size a container. Params: container_id, padding.

    Returns:
        JSON results or confirmation message.
    """
    try:
        action = validate_action(action, "layout", _LAYOUT_ACTIONS)
        validate_non_empty_string(diagram_name, "diagram_name")
    except ValidationError as exc:
        return f"Error: {exc.message}"
    df = _diagrams.get(diagram_name)
    if not df:
        return f"Error: diagram '{diagram_name}' not found."
    try:
        validate_page_index(page_index, len(df.diagrams))
    except ValidationError as exc:
        return f"Error: {exc.message}"
    d = df.diagrams[page_index]

    # ----- sugiyama -----
    if action == "sugiyama":
        conns = connections or []
        try:
            validate_list(conns, "connections", min_length=1)
            for i, c in enumerate(conns):
                validate_connection_dict(c, i)
            validate_direction(direction)
            validate_spacing(rank_spacing, "rank_spacing")
            validate_spacing(node_spacing, "node_spacing")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        edge_tuples = [(e.get("source", e.get("source_id", "")),
                        e.get("target", e.get("target_id", "")),
                        e.get("label", "")) for e in conns]
        e_style = _resolve_edge_style(edge_style_preset)
        cfg = LayoutEngineConfig(
            rank_spacing=rank_spacing, node_spacing=node_spacing,
            grid_size=d.grid_size, route_edges=True,
        )
        mapping = layout_sugiyama(d, edge_tuples, edge_style=e_style,
                                  config=cfg, direction=direction)
        return json.dumps(mapping)

    # ----- tree -----
    elif action == "tree":
        try:
            validate_adjacency(adjacency)
            validate_non_empty_string(root, "root")
            validate_direction(direction)
            validate_spacing(h_spacing, "h_spacing")
            validate_spacing(v_spacing, "v_spacing")
            validate_positive_number(width, "width")
            validate_positive_number(height, "height")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        adj = adjacency or {}
        vs = custom_style or _resolve_vertex_style(style_preset)
        es = custom_edge_style or _resolve_edge_style(edge_style_preset)
        cfg = LayoutConfig(h_spacing=h_spacing, v_spacing=v_spacing,
                           default_width=width, default_height=height)
        mapping = layout_tree(d, adj, root, vs, es, cfg, direction)
        return json.dumps(mapping)

    # ----- horizontal -----
    elif action == "horizontal":
        lbl_list = labels or []
        try:
            validate_list(lbl_list, "labels", min_length=1)
            validate_spacing(h_spacing, "h_spacing")
            validate_positive_number(width, "width")
            validate_positive_number(height, "height")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        vs = custom_style or _resolve_vertex_style(style_preset)
        cfg = LayoutConfig(start_x=start_x, start_y=start_y, h_spacing=h_spacing,
                           default_width=width, default_height=height)
        ids = layout_horizontal(d, lbl_list, vs, cfg)
        edge_ids: list[str] = []
        if connect and len(ids) > 1:
            es = _resolve_edge_style(edge_style_preset)
            edge_ids = connect_chain(d, ids, es, edge_labels)
        return json.dumps({"vertex_ids": ids, "edge_ids": edge_ids})

    # ----- vertical -----
    elif action == "vertical":
        lbl_list = labels or []
        try:
            validate_list(lbl_list, "labels", min_length=1)
            validate_spacing(v_spacing, "v_spacing")
            validate_positive_number(width, "width")
            validate_positive_number(height, "height")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        vs = custom_style or _resolve_vertex_style(style_preset)
        cfg = LayoutConfig(start_x=start_x, start_y=start_y, v_spacing=v_spacing,
                           default_width=width, default_height=height)
        ids = layout_vertical(d, lbl_list, vs, cfg)
        edge_ids = []
        if connect and len(ids) > 1:
            es = _resolve_edge_style(edge_style_preset)
            edge_ids = connect_chain(d, ids, es, edge_labels)
        return json.dumps({"vertex_ids": ids, "edge_ids": edge_ids})

    # ----- grid -----
    elif action == "grid":
        lbl_list = labels or []
        try:
            validate_list(lbl_list, "labels", min_length=1)
            validate_columns(columns)
            validate_spacing(h_spacing, "h_spacing")
            validate_spacing(v_spacing, "v_spacing")
            validate_positive_number(width, "width")
            validate_positive_number(height, "height")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        vs = custom_style or _resolve_vertex_style(style_preset)
        cfg = LayoutConfig(start_x=start_x, start_y=start_y,
                           h_spacing=h_spacing, v_spacing=v_spacing,
                           default_width=width, default_height=height)
        ids = layout_grid(d, lbl_list, columns, vs, cfg)
        return json.dumps(ids)

    # ----- flowchart -----
    elif action == "flowchart":
        step_list = steps or []
        try:
            validate_list(step_list, "steps", min_length=1)
            for i, step in enumerate(step_list):
                validate_flowchart_step(step, i)
            validate_direction(direction)
        except ValidationError as exc:
            return f"Error: {exc.message}"
        type_map = {
            "process": VertexStyle.FLOWCHART_PROCESS,
            "decision": VertexStyle.FLOWCHART_DECISION,
            "terminator": VertexStyle.FLOWCHART_TERMINATOR,
            "data": VertexStyle.FLOWCHART_DATA,
            "predefined": VertexStyle.FLOWCHART_PREDEFINED,
            "manual_input": VertexStyle.FLOWCHART_MANUAL_INPUT,
            "preparation": VertexStyle.FLOWCHART_PREPARATION,
            "delay": VertexStyle.FLOWCHART_DELAY,
            "display": VertexStyle.FLOWCHART_DISPLAY,
            "stored_data": VertexStyle.FLOWCHART_STORED_DATA,
        }
        spacing = 80
        ids = []
        for i, step in enumerate(step_list):
            stype = step.get("type", "process").lower()
            s = type_map.get(stype, VertexStyle.FLOWCHART_PROCESS)
            w = 160 if stype == "decision" else 120
            h = 80 if stype == "decision" else 60
            if direction == "LR":
                x, y = 50 + i * (w + spacing), 50
            else:
                x, y = 50, 50 + i * (h + spacing)
            cid = d.add_vertex(step["label"], x, y, w, h, s)
            ids.append(cid)
        edge_ids = connect_chain(
            d, ids,
            "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;"
            "jettySize=auto;html=1;endArrow=classic;",
        )
        return json.dumps({"vertex_ids": ids, "edge_ids": edge_ids})

    # ----- smart_connect -----
    elif action == "smart_connect":
        conns = connections or []
        try:
            validate_list(conns, "connections", min_length=1)
            for i, conn in enumerate(conns):
                validate_connection_dict(conn, i)
        except ValidationError as exc:
            return f"Error: {exc.message}"
        s = _resolve_edge_style(edge_style_preset if edge_style_preset and edge_style_preset != "DEFAULT" else "DEFAULT")
        bounds = get_all_vertex_bounds(d)
        auto_idx: list[int] = []
        auto_pairs: list[tuple[str, str]] = []
        explicit: dict[int, tuple[str, str]] = {}

        for i, conn in enumerate(conns):
            ep_exit = conn.get("exit_port", "")
            ep_entry = conn.get("entry_port", "")
            if ep_exit or ep_entry:
                explicit[i] = (ep_exit, ep_entry)
            else:
                auto_idx.append(i)
                auto_pairs.append((conn["source_id"], conn["target_id"]))

        bp = distribute_ports_for_batch(auto_pairs, bounds) if auto_pairs else []
        ids = []
        for i, conn in enumerate(conns):
            src_id = conn["source_id"]
            tgt_id = conn["target_id"]
            ep = _find_common_parent(d, src_id, tgt_id)

            if i in explicit:
                exit_name, entry_name = explicit[i]
                ex, ey, enx, eny = _resolve_ports(d, src_id, tgt_id, exit_name, entry_name, False)
            else:
                bidx = auto_idx.index(i)
                (ex, ey), (enx, eny) = bp[bidx]

            cid = d.add_edge(src_id, tgt_id, conn.get("label", ""), s, ep)
            edge_cell = _find_cell(d, cid)
            if edge_cell:
                if ex is not None:
                    edge_cell.exit_x = ex
                    edge_cell.exit_y = ey
                if enx is not None:
                    edge_cell.entry_x = enx
                    edge_cell.entry_y = eny
            ids.append(cid)

        route_edges_around_obstacles(d, margin=15)
        return json.dumps(ids)

    # ----- align -----
    elif action == "align":
        try:
            validate_list(cell_ids or [], "cell_ids", min_length=2)
            validate_alignment(alignment)
        except ValidationError as exc:
            return f"Error: {exc.message}"
        cell_list = cell_ids or []
        cells = [_find_cell(d, cid) for cid in cell_list]
        cells = [c for c in cells if c and c.geometry and not c.geometry.relative]
        if len(cells) < 2:
            return "Need at least 2 cells to align."

        al = alignment.lower()
        if al == "left":
            t = min(c.geometry.x for c in cells)
            for c in cells:
                c.geometry.x = t
        elif al == "center":
            centers = [c.geometry.x + c.geometry.width / 2 for c in cells]
            t = sum(centers) / len(centers)
            for c in cells:
                c.geometry.x = snap_to_grid(t - c.geometry.width / 2, d.grid_size)
        elif al == "right":
            t = max(c.geometry.x + c.geometry.width for c in cells)
            for c in cells:
                c.geometry.x = snap_to_grid(t - c.geometry.width, d.grid_size)
        elif al == "top":
            t = min(c.geometry.y for c in cells)
            for c in cells:
                c.geometry.y = t
        elif al == "middle":
            centers = [c.geometry.y + c.geometry.height / 2 for c in cells]
            t = sum(centers) / len(centers)
            for c in cells:
                c.geometry.y = snap_to_grid(t - c.geometry.height / 2, d.grid_size)
        elif al == "bottom":
            t = max(c.geometry.y + c.geometry.height for c in cells)
            for c in cells:
                c.geometry.y = snap_to_grid(t - c.geometry.height, d.grid_size)
        else:
            return f"Error: unknown alignment '{al}'."
        return f"Aligned {len(cells)} cells to '{al}'."

    # ----- distribute -----
    elif action == "distribute":
        try:
            validate_list(cell_ids or [], "cell_ids", min_length=2)
            validate_string(dist_direction, "dist_direction")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        cell_list = cell_ids or []
        cells = [_find_cell(d, cid) for cid in cell_list]
        cells = [c for c in cells if c and c.geometry and not c.geometry.relative]
        if len(cells) < 2:
            return "Need at least 2 cells to distribute."
        dd = dist_direction.lower()
        if dd == "horizontal":
            cells.sort(key=lambda c: c.geometry.x)
            positions = [c.geometry.x for c in cells]
            sizes = [c.geometry.width for c in cells]
            start_pos = positions[0]
            end_pos = positions[-1] + sizes[-1]
            new_pos = distribute_evenly(positions, sizes, start_pos, end_pos)
            for cell, nx in zip(cells, new_pos):
                cell.geometry.x = snap_to_grid(nx, d.grid_size)
        else:
            cells.sort(key=lambda c: c.geometry.y)
            positions = [c.geometry.y for c in cells]
            sizes = [c.geometry.height for c in cells]
            start_pos = positions[0]
            end_pos = positions[-1] + sizes[-1]
            new_pos = distribute_evenly(positions, sizes, start_pos, end_pos)
            for cell, ny in zip(cells, new_pos):
                cell.geometry.y = snap_to_grid(ny, d.grid_size)
        return f"Distributed {len(cells)} cells {dd}ly."

    # ----- polish -----
    elif action == "polish":
        try:
            validate_direction(direction)
        except ValidationError as exc:
            return f"Error: {exc.message}"
        results: list[str] = []
        cfg = LayoutEngineConfig(grid_size=d.grid_size)
        moved = relayout_diagram(d, direction=direction, config=cfg)
        results.append(f"Relayout: {len(moved)} shapes")
        om = resolve_overlaps(d, margin=20)
        results.append(f"Overlaps: {om} fixes")
        cm = compact_diagram(d, margin=40)
        results.append(f"Compact: {cm} adjusted")
        # Auto-alignment pass
        bl = align_rank_baselines(d, threshold=20)
        cl = align_column_centers(d, threshold=20)
        eq = equalize_connected_sizes(d, direction=direction)
        results.append(f"Aligned: {bl} rows, {cl} cols, {eq} equalized")
        routed = route_edges_around_obstacles(d, margin=15)
        results.append(f"Routing: {routed} edges")
        opt = optimize_edge_paths(d, margin=15)
        results.append(f"Optimized: {opt} edges")
        lf = position_edge_labels(d, margin=8)
        results.append(f"Labels: {lf} fixed")
        # Final pass: center on page and enforce margins
        cp = center_diagram_on_page(d, margin=50)
        pm = ensure_page_margins(d, margin=40)
        results.append(f"Centered: {cp}, Margins: {pm}")
        return "Polished! " + " | ".join(results)

    # ----- relayout -----
    elif action == "relayout":
        try:
            validate_direction(direction)
            validate_spacing(rank_spacing, "rank_spacing")
            validate_spacing(node_spacing, "node_spacing")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        cfg = LayoutEngineConfig(rank_spacing=rank_spacing, node_spacing=node_spacing,
                                 grid_size=d.grid_size)
        moved = relayout_diagram(d, direction=direction, config=cfg)
        ensure_page_margins(d, margin=40)
        return f"Repositioned {len(moved)} shape(s)."

    # ----- compact -----
    elif action == "compact":
        try:
            validate_non_negative_number(margin, "margin")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        count = compact_diagram(d, margin=margin)
        return f"Compacted: {count} shape(s) adjusted."

    # ----- reroute_edges -----
    elif action == "reroute_edges":
        try:
            validate_non_negative_number(margin, "margin")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        count = route_edges_around_obstacles(d, margin=margin)
        return f"Rerouted {count} edge(s)."

    # ----- resolve_overlaps -----
    elif action == "resolve_overlaps":
        try:
            validate_non_negative_number(margin, "margin")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        before = find_overlapping_cells(d, margin=0)
        if not before:
            return "No overlaps found. Diagram is clean!"
        moves = resolve_overlaps(d, margin=margin)
        after = find_overlapping_cells(d, margin=0)
        return f"Found {len(before)} overlaps. {moves} adjustments. Remaining: {len(after)}."

    # ----- fix_labels -----
    elif action == "fix_labels":
        try:
            validate_non_negative_number(margin, "margin")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        count = position_edge_labels(d, margin=margin)
        return f"Repositioned {count} edge label(s)."

    # ----- optimize_connections -----
    elif action == "optimize_connections":
        try:
            validate_non_negative_number(margin, "margin")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        count = optimize_edge_paths(d, margin=margin)
        return f"Optimized {count} edge path(s): simplified bends, straightened segments, shortened detours, centered channels, separated parallels."

    # ----- resize_container -----
    elif action == "resize_container":
        try:
            validate_non_empty_string(container_id, "container_id")
            validate_non_negative_number(padding, "padding")
        except ValidationError as exc:
            return f"Error: {exc.message}"
        container = _find_cell(d, container_id)
        if not container or not container.geometry:
            return f"Error: container '{container_id}' not found."
        children = [c for c in d.cells if c.parent == container_id
                    and c.geometry and not c.geometry.relative and c.id != container_id]
        if not children:
            return "No children found."
        header_h = 23
        if container.style:
            m = re.search(r"startSize=(\d+)", container.style)
            if m:
                header_h = int(m.group(1))
        min_x = min(c.geometry.x for c in children)
        min_y = min(c.geometry.y for c in children)
        max_x = max(c.geometry.x + c.geometry.width for c in children)
        max_y = max(c.geometry.y + c.geometry.height for c in children)
        if min_x < padding:
            shift = padding - min_x
            for c in children:
                c.geometry.x += shift
            max_x += shift
        if min_y < header_h + padding:
            shift = header_h + padding - min_y
            for c in children:
                c.geometry.y += shift
            max_y += shift
        new_w = snap_to_grid(max_x + padding, d.grid_size)
        new_h = snap_to_grid(max_y + padding, d.grid_size)
        container.geometry.width = new_w
        container.geometry.height = new_h
        return f"Container resized to {new_w}x{new_h}."

    else:
        return (
            f"Error: unknown layout action '{action}'. "
            "Use: sugiyama, tree, horizontal, vertical, grid, flowchart, "
            "smart_connect, align, distribute, polish, relayout, compact, "
            "reroute_edges, resolve_overlaps, fix_labels, optimize_connections, "
            "resize_container."
        )


# ===================================================================
# TOOL 5: inspect — read-only queries
# ===================================================================

@mcp.tool()
def inspect(
    action: str,
    diagram_name: str = "",
    margin: float = 0,
    page_index: int = 0,
) -> str:
    """Read-only inspection of diagrams.

    Actions:
      cells     — List all cells with their IDs, types, labels, positions.
                  Params: diagram_name, page_index.
      overlaps  — Check for overlapping shapes. Params: diagram_name, margin.
      ports     — List available connection port positions.
      info      — Get diagram summary (page count, cell counts).
                  Params: diagram_name.

    Args:
        action: One of: cells, overlaps, ports, info.
        diagram_name: Target diagram name.
        margin: Minimum gap for overlap checks.
        page_index: Page index (0-based).

    Returns:
        JSON data or formatted text.
    """
    try:
        action = validate_action(action, "inspect", _INSPECT_ACTIONS)
    except ValidationError as exc:
        return f"Error: {exc.message}"

    if action == "ports":
        entries: list[str] = []
        for name in sorted(dir(Port)):
            if name.startswith("_"):
                continue
            val = getattr(Port, name)
            if isinstance(val, tuple):
                entries.append(f"  {name}: x={val[0]}, y={val[1]}")
        return "Connection ports:\n" + "\n".join(entries)

    # All other actions need a diagram
    try:
        validate_non_empty_string(diagram_name, "diagram_name")
    except ValidationError as exc:
        return f"Error: {exc.message}"
    df = _diagrams.get(diagram_name)
    if not df:
        return f"Error: diagram '{diagram_name}' not found."
    try:
        validate_page_index(page_index, len(df.diagrams))
    except ValidationError as exc:
        return f"Error: {exc.message}"
    d = df.diagrams[page_index]

    if action == "cells":
        cells_info: list[dict[str, Any]] = []
        for c in d.cells:
            info: dict[str, Any] = {"id": c.id}
            if c.value:
                info["label"] = c.value
            if c.vertex:
                info["type"] = "vertex"
            elif c.edge:
                info["type"] = "edge"
                if c.source:
                    info["source"] = c.source
                if c.target:
                    info["target"] = c.target
            elif c.parent == "0" and c.id != "0":
                info["type"] = "layer"
            else:
                info["type"] = "structural"
            # Include metadata if present
            if c.tooltip:
                info["tooltip"] = c.tooltip
            if c.link:
                info["link"] = c.link
            if c.metadata:
                info["metadata"] = c.metadata
            effective_style = c.style or ""
            if c.edge:
                port_parts: list[str] = []
                if c.exit_x is not None:
                    port_parts += [f"exitX={c.exit_x}", f"exitY={c.exit_y or 0}",
                                   f"exitDx={c.exit_dx}", f"exitDy={c.exit_dy}",
                                   "exitPerimeter=0"]
                if c.entry_x is not None:
                    port_parts += [f"entryX={c.entry_x}", f"entryY={c.entry_y or 0}",
                                   f"entryDx={c.entry_dx}", f"entryDy={c.entry_dy}",
                                   "entryPerimeter=0"]
                if port_parts:
                    effective_style = effective_style.rstrip(";") + ";" + ";".join(port_parts) + ";"
            if effective_style:
                info["style"] = effective_style
            if c.parent:
                info["parent"] = c.parent
            if c.geometry and not c.geometry.relative:
                info["position"] = {"x": c.geometry.x, "y": c.geometry.y,
                                    "width": c.geometry.width, "height": c.geometry.height}
            cells_info.append(info)
        return json.dumps(cells_info, indent=2)

    elif action == "overlaps":
        overlaps = find_overlapping_cells(d, margin=margin)
        if not overlaps:
            return "No overlaps found. Diagram is clean!"
        cell_labels: dict[str, str] = {}
        for cell in d.cells:
            if cell.value:
                cell_labels[cell.id] = cell.value
        report = [{"cell_a": a, "label_a": cell_labels.get(a, ""),
                    "cell_b": b, "label_b": cell_labels.get(b, "")}
                   for a, b in overlaps]
        return json.dumps(report, indent=2)

    elif action == "info":
        pages: list[dict[str, Any]] = []
        for i, pg in enumerate(df.diagrams):
            vc = sum(1 for c in pg.cells if c.vertex)
            ec = sum(1 for c in pg.cells if c.edge)
            lc = sum(1 for c in pg.cells if c.parent == "0" and c.id != "0")
            pages.append({"index": i, "name": pg.name, "vertices": vc, "edges": ec, "layers": lc})
        return json.dumps({"name": diagram_name, "pages": pages}, indent=2)

    else:
        return f"Error: unknown inspect action '{action}'. Use: cells, overlaps, ports, info."


# ===================================================================
# Internal helpers
# ===================================================================

_VERTEX_ALIAS_MAP: dict[str, str] | None = None
_EDGE_ALIAS_MAP: dict[str, str] | None = None


def _build_alias_map(cls: type) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for attr in dir(cls):
        if attr.startswith("_"):
            continue
        val = getattr(cls, attr)
        if not isinstance(val, str):
            continue
        key = attr.upper()
        mapping[key] = val
        for prefix in ("FLOWCHART_", "UML_", "BPMN_", "ER_", "C4_",
                        "STATE_", "MINDMAP_", "SEQUENCE_"):
            if key.startswith(prefix):
                suffix = key[len(prefix):]
                if suffix not in mapping:
                    mapping[suffix] = val
        no_us = key.replace("_", "")
        if no_us not in mapping:
            mapping[no_us] = val
    return mapping


def _resolve_vertex_style(preset_name: str) -> str:
    global _VERTEX_ALIAS_MAP
    if not preset_name:
        return VertexStyle.ROUNDED_RECTANGLE
    val = getattr(VertexStyle, preset_name.upper(), None)
    if val and isinstance(val, str):
        return val
    if _VERTEX_ALIAS_MAP is None:
        _VERTEX_ALIAS_MAP = _build_alias_map(VertexStyle)
    key = preset_name.upper().replace(" ", "_")
    if key in _VERTEX_ALIAS_MAP:
        return _VERTEX_ALIAS_MAP[key]
    no_us = key.replace("_", "")
    if no_us in _VERTEX_ALIAS_MAP:
        return _VERTEX_ALIAS_MAP[no_us]
    if "=" in preset_name or ";" in preset_name:
        return preset_name
    logger.warning("Unknown vertex preset '%s', using ROUNDED_RECTANGLE", preset_name)
    return VertexStyle.ROUNDED_RECTANGLE


def _resolve_edge_style(preset_name: str) -> str:
    global _EDGE_ALIAS_MAP
    if not preset_name:
        return EdgeStylePreset.DEFAULT
    val = getattr(EdgeStylePreset, preset_name.upper(), None)
    if val and isinstance(val, str):
        return val
    if _EDGE_ALIAS_MAP is None:
        _EDGE_ALIAS_MAP = _build_alias_map(EdgeStylePreset)
    key = preset_name.upper().replace(" ", "_")
    if key in _EDGE_ALIAS_MAP:
        return _EDGE_ALIAS_MAP[key]
    no_us = key.replace("_", "")
    if no_us in _EDGE_ALIAS_MAP:
        return _EDGE_ALIAS_MAP[no_us]
    if "=" in preset_name or ";" in preset_name:
        return preset_name
    logger.warning("Unknown edge preset '%s', using DEFAULT", preset_name)
    return EdgeStylePreset.DEFAULT


def _find_cell(d: Diagram, cell_id: str) -> MxCell | None:
    for cell in d.cells:
        if cell.id == cell_id:
            return cell
    return None


def _estimate_size(label: str, default_w: float, default_h: float) -> tuple[float, float]:
    if (default_w, default_h) != (120, 60):
        return default_w, default_h
    text = re.sub(r"<br\s*/?>", "\n", label, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        lines = [text.strip() or "X"]
    max_chars = max((len(l) for l in lines), default=10)
    n_lines = max(len(lines), 1)
    w = max(120, min(280, max_chars * 8 + 20))
    h = max(50, min(200, n_lines * 22 + 16))
    return float(w), float(h)


def _abs_to_relative(d: Diagram, x: float, y: float, parent_id: str) -> tuple[float, float]:
    if parent_id in ("1", "0", ""):
        return x, y
    offset_x, offset_y = 0.0, 0.0
    current_id = parent_id
    visited: set[str] = set()
    while current_id and current_id not in ("0", "1") and current_id not in visited:
        visited.add(current_id)
        parent_cell = _find_cell(d, current_id)
        if parent_cell and parent_cell.geometry and not parent_cell.geometry.relative:
            offset_x += parent_cell.geometry.x
            offset_y += parent_cell.geometry.y
        current_id = parent_cell.parent if parent_cell else ""
    return x - offset_x, y - offset_y


def _ancestor_chain(d: Diagram, cell_id: str) -> list[str]:
    chain: list[str] = []
    current = cell_id
    visited: set[str] = set()
    while current and current not in visited:
        visited.add(current)
        chain.append(current)
        cell = _find_cell(d, current)
        current = cell.parent if cell else ""
    return chain


def _find_common_parent(d: Diagram, source_id: str, target_id: str) -> str:
    src_chain = _ancestor_chain(d, source_id)
    tgt_set = set(_ancestor_chain(d, target_id))
    for ancestor in src_chain:
        if ancestor in tgt_set and ancestor not in (source_id, target_id):
            return ancestor
    return "1"


def _resolve_ports(
    d: Diagram, source_id: str, target_id: str,
    exit_port: str, entry_port: str, smart_ports: bool,
) -> tuple[float | None, float | None, float | None, float | None]:
    port_map: dict[str, tuple[float, float]] = {}
    for attr in dir(Port):
        if attr.startswith("_"):
            continue
        val = getattr(Port, attr)
        if isinstance(val, tuple) and len(val) == 2:
            port_map[attr.upper()] = val

    ex, ey = None, None
    enx, eny = None, None
    if exit_port:
        key = exit_port.upper().replace(" ", "_")
        if key in port_map:
            ex, ey = port_map[key]
    if entry_port:
        key = entry_port.upper().replace(" ", "_")
        if key in port_map:
            enx, eny = port_map[key]
    if ex is None and enx is None and smart_ports:
        bounds = get_all_vertex_bounds(d)
        src_b = bounds.get(source_id)
        tgt_b = bounds.get(target_id)
        if src_b and tgt_b:
            (ex, ey), (enx, eny) = choose_best_ports(src_b, tgt_b)
    return ex, ey, enx, eny


def _apply_theme_impl(d: Diagram, theme: str) -> int:
    if not theme:
        return 0
    t = getattr(Themes, theme.upper(), None)
    if not isinstance(t, ColorTheme):
        return 0
    count = 0
    for cell in d.cells:
        if cell.id in ("0", "1"):
            continue
        if not cell.style:
            continue
        sb = StyleBuilder(cell.style)
        t.apply(sb)
        cell.style = sb.build()
        count += 1
    return count


def _parse_style_float(style: str, key: str) -> float | None:
    """Extract a float value for a key from a draw.io style string, or None."""
    m = re.search(rf"(?:^|;){key}=([^;]+)", style)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def _import_xml_impl(name: str, xml_content: str) -> str:
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        return f"Error parsing XML: {exc}"

    parsed: list[Diagram] = []
    if root.tag == "mxfile":
        diagram_elements = root.findall("diagram")
    elif root.tag == "mxGraphModel":
        diag_el = ET.Element("diagram", attrib={"name": name, "id": "imported"})
        diag_el.append(root)
        diagram_elements = [diag_el]
    else:
        return "Error: unrecognized root element."

    for diag_el in diagram_elements:
        model_el = diag_el.find("mxGraphModel")
        if model_el is None:
            continue
        d_obj = Diagram(
            name=diag_el.get("name", "Page"),
            id=diag_el.get("id", "imported"),
            cells=[],
        )
        d_obj.grid = model_el.get("grid", "1") == "1"
        d_obj.grid_size = int(model_el.get("gridSize", "10"))
        d_obj.page_width = int(model_el.get("pageWidth", "827"))
        d_obj.page_height = int(model_el.get("pageHeight", "1169"))
        d_obj.background = model_el.get("background", "none")
        d_obj.shadow = model_el.get("shadow", "0") == "1"
        d_obj.math = model_el.get("math", "0") == "1"

        root_el = model_el.find("root")
        if root_el is None:
            continue
        max_id = 1

        def _parse_cell_element(
            cell_el: ET.Element,
            obj_tooltip: str = "",
            obj_link: str = "",
            obj_placeholders: bool = False,
            obj_metadata: dict[str, str] | None = None,
            obj_label: str = "",
            obj_id: str = "",
        ) -> MxCell:
            """Parse an mxCell element into an MxCell, with optional <object> metadata."""
            cid = obj_id or cell_el.get("id", "")
            label = obj_label or cell_el.get("value", "")
            geom_el = cell_el.find("mxGeometry")
            geometry = None
            if geom_el is not None:
                geometry = Geometry(
                    x=float(geom_el.get("x", "0")),
                    y=float(geom_el.get("y", "0")),
                    width=float(geom_el.get("width", "0")),
                    height=float(geom_el.get("height", "0")),
                    relative=geom_el.get("relative", "0") == "1",
                )
                # Parse waypoints from <Array as="points">
                arr_el = geom_el.find("Array[@as='points']")
                if arr_el is not None:
                    for pt_el in arr_el.findall("mxPoint"):
                        geometry.points.append(Point(
                            float(pt_el.get("x", "0")),
                            float(pt_el.get("y", "0")),
                        ))
                # Parse offset from <mxPoint as="offset">
                offset_el = geom_el.find("mxPoint[@as='offset']")
                if offset_el is not None:
                    geometry.offset = Point(
                        float(offset_el.get("x", "0")),
                        float(offset_el.get("y", "0")),
                    )
                # Parse source/target points
                src_pt_el = geom_el.find("mxPoint[@as='sourcePoint']")
                if src_pt_el is not None:
                    geometry.source_point = Point(
                        float(src_pt_el.get("x", "0")),
                        float(src_pt_el.get("y", "0")),
                    )
                tgt_pt_el = geom_el.find("mxPoint[@as='targetPoint']")
                if tgt_pt_el is not None:
                    geometry.target_point = Point(
                        float(tgt_pt_el.get("x", "0")),
                        float(tgt_pt_el.get("y", "0")),
                    )
                # Parse alternate bounds
                alt_el = geom_el.find("mxGeometry[@as='alternateBounds']")
                if alt_el is not None:
                    geometry.alternate_bounds = Geometry(
                        x=float(alt_el.get("x", "0")),
                        y=float(alt_el.get("y", "0")),
                        width=float(alt_el.get("width", "0")),
                        height=float(alt_el.get("height", "0")),
                    )

            # Parse edge port constraints from style string
            cell_style = cell_el.get("style", "")
            exit_x_val = _parse_style_float(cell_style, "exitX")
            exit_y_val = _parse_style_float(cell_style, "exitY")
            entry_x_val = _parse_style_float(cell_style, "entryX")
            entry_y_val = _parse_style_float(cell_style, "entryY")

            return MxCell(
                id=cid, value=label,
                style=cell_style,
                parent=cell_el.get("parent", ""),
                vertex=cell_el.get("vertex", "0") == "1",
                edge=cell_el.get("edge", "0") == "1",
                source=cell_el.get("source"),
                target=cell_el.get("target"),
                geometry=geometry,
                exit_x=exit_x_val,
                exit_y=exit_y_val,
                entry_x=entry_x_val,
                entry_y=entry_y_val,
                tooltip=obj_tooltip or None,
                link=obj_link or None,
                placeholders=obj_placeholders,
                metadata=obj_metadata or {},
            )

        for child_el in root_el:
            if child_el.tag == "mxCell":
                cell = _parse_cell_element(child_el)
                d_obj.cells.append(cell)
                try:
                    if int(cell.id) > max_id:
                        max_id = int(cell.id)
                except ValueError:
                    pass
            elif child_el.tag == "object" or child_el.tag == "UserObject":
                # <object> or <UserObject> wraps an <mxCell> with metadata
                obj_id = child_el.get("id", "")
                obj_label = child_el.get("label", "")
                obj_tooltip = child_el.get("tooltip", "")
                obj_link = child_el.get("link", "")
                obj_placeholders = child_el.get("placeholders", "0") == "1"
                # Collect custom metadata (all attributes except known ones)
                _KNOWN_OBJ_ATTRS = {"id", "label", "tooltip", "link", "placeholders"}
                obj_metadata = {
                    k: v for k, v in child_el.attrib.items()
                    if k not in _KNOWN_OBJ_ATTRS
                }
                inner_cell = child_el.find("mxCell")
                if inner_cell is not None:
                    cell = _parse_cell_element(
                        inner_cell,
                        obj_tooltip=obj_tooltip,
                        obj_link=obj_link,
                        obj_placeholders=obj_placeholders,
                        obj_metadata=obj_metadata,
                        obj_label=obj_label,
                        obj_id=obj_id,
                    )
                    d_obj.cells.append(cell)
                    try:
                        if int(obj_id) > max_id:
                            max_id = int(obj_id)
                    except ValueError:
                        pass
        d_obj._next_id = max_id + 1
        parsed.append(d_obj)

    if not parsed:
        return "Error: no valid diagram pages found."
    df_obj = DrawioFile(diagrams=parsed)
    with _diagrams_lock:
        _diagrams[name] = df_obj
    total = sum(len(d_obj.cells) for d_obj in df_obj.diagrams)
    return f"Imported '{name}' with {len(df_obj.diagrams)} page(s) and {total} cells."


def _get_all_bounds(d: Diagram) -> dict[str, CellBounds]:
    """Return bounding boxes for all vertex cells."""
    return get_all_vertex_bounds(d)


# ===================================================================
# Entry point
# ===================================================================

def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
