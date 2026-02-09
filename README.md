# Draw.io MCP Server

An MCP (Model Context Protocol) server that creates draw.io / diagrams.net XML files programmatically. This lets AI agents (like GitHub Copilot in agent mode) generate draw.io diagrams directly — no browser needed.

## Features

- **Create diagrams** — flowcharts, UML, ER, C4, BPMN, mindmaps, architecture, network, and freeform diagrams
- **Rich style system** — 310+ vertex presets, 44 edge presets, 21 color themes, and a fluent style builder
- **Auto-layout** — Sugiyama DAG, tree, horizontal, vertical, grid, and flowchart layout engines
- **Smart edge routing** — obstacle-aware orthogonal routing with automatic port distribution
- **Full editing** — add/move/resize/delete/restyle cells after creation
- **Multi-page & layers** — multiple diagram pages and layers for visibility control
- **Metadata** — tooltips, clickable links, and custom properties via `<object>` wrappers
- **Import/export** — load existing `.drawio` files (including `<object>`/`<UserObject>` elements), modify, and save back
- **One-click cleanup** — polish command: relayout + overlap resolution + compaction + edge routing + label fixing
- **Valid XML** — output adheres to the mxGraph/mxGraphModel schema and opens in draw.io desktop, VS Code draw.io extension, or diagrams.net

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Install & Run

```bash
cd drawio-mcp
uv sync
uv run drawio-mcp
```

### VS Code Integration

The `.vscode/mcp.json` file is already configured. After installing, just start the MCP server from the VS Code MCP panel. Then ask Copilot in agent mode to create diagrams.

## Tool Architecture

The server exposes **5 tools**, each with an `action` parameter that selects the operation:

### 1. `diagram` — Lifecycle Management

| Action | Description |
|--------|-------------|
| `create` | Create a new empty diagram with page format, background, and grid settings |
| `save` | Save diagram to a `.drawio` file on disk |
| `load` | Load an existing `.drawio` file for editing |
| `import_xml` | Import a raw XML string (supports `<object>` and `<UserObject>` wrappers) |
| `list` | List all in-memory diagrams |
| `get_xml` | Get the raw XML output |
| `add_page` | Add a page to a multi-page diagram |
| `add_layer` | Add a named layer for visibility control and z-ordering |

### 2. `draw` — Content Creation & Editing

| Action | Description |
|--------|-------------|
| `add_vertices` | Add one or more shapes with optional tooltip, link, and custom metadata |
| `add_edges` | Add connections between shapes with automatic port distribution |
| `add_group` | Add a container/swimlane |
| `update_cells` | Update label, style, position, or size of existing cells |
| `delete_cells` | Delete cells by ID (cascades to children and connected edges) |
| `add_title` | Add title and optional subtitle |
| `add_legend` | Add a color-coded legend box |
| `build_dag` | Build a complete auto-laid-out directed graph in ONE call (layout + routing + theme + title) |
| `build_full` | Build a complete manually-positioned diagram in ONE call (vertices + edges + theme + title) |

### 3. `style` — Appearance

| Action | Description |
|--------|-------------|
| `build` | Build a draw.io style string from named parameters (colors, font, rounded, dashed, etc.) |
| `apply_theme` | Apply a color theme to all or selected cells |
| `list_vertex_presets` | List all 310+ vertex style presets |
| `list_edge_presets` | List all 44 edge style presets |
| `list_themes` | List all 21 color themes |

### 4. `layout` — Positioning & Cleanup

| Action | Description |
|--------|-------------|
| `sugiyama` | Lay out a DAG using the Sugiyama algorithm |
| `tree` | Lay out a tree from an adjacency list |
| `horizontal` | Arrange shapes in a connected row |
| `vertical` | Arrange shapes in a connected column |
| `grid` | Arrange shapes in a grid |
| `flowchart` | Create a flowchart from step definitions |
| `smart_connect` | Connect shapes with smart port distribution and obstacle-aware routing |
| `align` | Align shapes (left/center/right/top/middle/bottom) |
| `distribute` | Distribute shapes evenly (horizontal/vertical) |
| `polish` | One-click cleanup: relayout + overlaps + compact + route edges + fix labels + center |
| `relayout` | Reorganize existing diagram layout |
| `compact` | Remove excess whitespace |
| `reroute_edges` | Reroute all edges around obstacles |
| `resolve_overlaps` | Push apart overlapping shapes |
| `fix_labels` | Fix edge label collisions |
| `optimize_connections` | Simplify bends, straighten segments, shorten detours, separate parallels |
| `resize_container` | Auto-size a container to fit its children |

### 5. `inspect` — Read-Only Queries

| Action | Description |
|--------|-------------|
| `cells` | List all cells with IDs, types, labels, positions, metadata, and layer info |
| `overlaps` | Check for overlapping shapes |
| `ports` | List available connection port positions |
| `info` | Get diagram summary (page count, cell counts, layer counts) |

## Style Presets

### Vertex Styles (use as `style_preset`)

**Basic shapes:** `RECTANGLE`, `ROUNDED_RECTANGLE`, `ELLIPSE`, `CIRCLE`, `DIAMOND`, `TRIANGLE`, `HEXAGON`, `CYLINDER`, `CLOUD`, `PARALLELOGRAM`, `ACTOR`, `PROCESS`, `DOCUMENT`, `DATA_STORE`, `NOTE`, `CARD`, `CALLOUT`, `TEXT`, `DOUBLE_ELLIPSE`, `PENTAGON`, `TRAPEZOID`, `STAR`, `CUBE`, `STEP`, `TAPE`, `PLUS`, `CROSS`, `LINE`, `LABEL`, `LINK`, `FOLDER`, `CORNER`, `TEE`, `LOLLIPOP`, `IMAGE`

**Arrows:** `ARROW_RIGHT`, `ARROW_LEFT`, `ARROW_UP`, `ARROW_DOWN`, `ARROW_DOUBLE`

**Themed boxes:** `BLUE_BOX`, `GREEN_BOX`, `ORANGE_BOX`, `RED_BOX`, `YELLOW_BOX`, `PURPLE_BOX`, `GRAY_BOX`, `DARK_BLUE_BOX`, `DARK_BOX`, `PINK_BOX`, `TEAL_BOX`, `WHITE_BOX`

**Flowchart:** `FLOWCHART_PROCESS`, `FLOWCHART_DECISION`, `FLOWCHART_TERMINATOR`, `FLOWCHART_DATA`, `FLOWCHART_PREDEFINED`, `FLOWCHART_MANUAL_INPUT`, `FLOWCHART_PREPARATION`, `FLOWCHART_DELAY`, `FLOWCHART_DISPLAY`, `FLOWCHART_STORED_DATA`, `FLOWCHART_DOCUMENT`, `FLOWCHART_MULTI_DOCUMENT`, `FLOWCHART_DATABASE`, `FLOWCHART_DIRECT_DATA`, `FLOWCHART_INTERNAL_STORAGE`, `FLOWCHART_PAPER_TAPE`, `FLOWCHART_MANUAL_OPERATION`, `FLOWCHART_LOOP_LIMIT`, `FLOWCHART_COLLATE`, `FLOWCHART_SORT`, `FLOWCHART_MERGE`, `FLOWCHART_EXTRACT`, `FLOWCHART_OR`, `FLOWCHART_SUMMING`, `FLOWCHART_CARD`, `FLOWCHART_ON_PAGE_REF`, `FLOWCHART_OFF_PAGE_REF`, `FLOWCHART_ANNOTATION`, `FLOWCHART_START`, `FLOWCHART_END`, `FLOWCHART_TRANSFER`, `FLOWCHART_SEQUENTIAL_DATA`, `FLOWCHART_PARALLEL_MODE`

**UML:** `UML_CLASS`, `UML_INTERFACE`, `UML_ACTOR`, `UML_COMPONENT`, `UML_PACKAGE`, `UML_NODE`, `UML_LIFELINE`, `UML_FRAME`

**C4 Architecture:** `C4_SYSTEM`, `C4_CONTAINER`, `C4_COMPONENT`, `C4_PERSON`, `C4_EXTERNAL`, `C4_DATABASE`, `C4_WEB_BROWSER`

**ER Diagram:** `ER_ENTITY`, `ER_WEAK_ENTITY`, `ER_ATTRIBUTE`, `ER_KEY_ATTRIBUTE`, `ER_DERIVED_ATTRIBUTE`, `ER_MULTI_VALUED`, `ER_RELATIONSHIP`

**BPMN:** `BPMN_TASK`, `BPMN_START_EVENT`, `BPMN_END_EVENT`, `BPMN_INTERMEDIATE_EVENT`, `BPMN_GATEWAY`, `BPMN_EXCLUSIVE_GATEWAY`, `BPMN_PARALLEL_GATEWAY`, `BPMN_POOL`, `BPMN_LANE`, `BPMN_SUB_PROCESS`, `BPMN_DATA_OBJECT`, `BPMN_TIMER_EVENT`, `BPMN_MESSAGE_EVENT`, `BPMN_ERROR_EVENT`

**State Machine:** `STATE`, `STATE_INITIAL`, `STATE_FINAL`, `STATE_CHOICE`, `STATE_HISTORY`, `STATE_FORK_JOIN`

**Mindmap:** `MINDMAP_ROOT`, `MINDMAP_BRANCH`, `MINDMAP_LEAF`

**Sequence Diagram:** `SEQUENCE_LIFELINE`, `SEQUENCE_ACTIVATION`, `SEQUENCE_FRAME`

**Containers:** `SWIMLANE`, `SWIMLANE_HORIZONTAL`, `SWIMLANE_VERTICAL`, `GROUP`, `GROUP_TRANSPARENT`, `GROUP_DASHED`

**Architecture (themed):** `ARCH_SERVICE`, `ARCH_DATABASE`, `ARCH_QUEUE`, `ARCH_CLOUD`, `ARCH_USER`, `ARCH_PERSON`, `ARCH_COMPONENT`, `ARCH_EXTERNAL`, `ARCH_API`, `ARCH_GATEWAY`, `ARCH_STORAGE`, `ARCH_CACHE`, `ARCH_CONTAINER`, `ARCH_ZONE`, `ARCH_LOAD_BALANCER`, `ARCH_FIREWALL`, `ARCH_SERVER`, `ARCH_WEB_SERVER`, `ARCH_ROUTER`, `ARCH_SWITCH`, `ARCH_RACK`, `ARCH_MOBILE`, `ARCH_LAPTOP`, `ARCH_MONITOR`, `ARCH_DESKTOP`, `ARCH_PRINTER`, `ARCH_HUB`, `ARCH_MAINFRAME`, `ARCH_VIRTUAL_SERVER`, `ARCH_TABLET`, `ARCH_SATELLITE`, `ARCH_RADIO_TOWER`

**Network (plain):** `NETWORK_SERVER`, `NETWORK_WEB_SERVER`, `NETWORK_MAIL_SERVER`, `NETWORK_ROUTER`, `NETWORK_SWITCH`, `NETWORK_HUB`, `NETWORK_FIREWALL`, `NETWORK_LOAD_BALANCER`, `NETWORK_CLOUD`, `NETWORK_STORAGE`, `NETWORK_LAPTOP`, `NETWORK_DESKTOP`, `NETWORK_MOBILE`, `NETWORK_TABLET`, `NETWORK_PRINTER`, and 40+ more

**Cloud / K8s:** `AWS_CLOUD`, `AWS_LAMBDA`, `AWS_S3`, `AWS_EC2`, `AWS_RDS`, `AWS_SQS`, `K8S_POD`, `K8S_SERVICE`, `K8S_DEPLOYMENT`, `K8S_NODE`, `K8S_INGRESS`, `K8S_NAMESPACE`, and more

**Additional:** DFD, SysML, ArchiMate, Cisco, Mockup/Wireframe, Infographic, Lean Mapping, Electrical, and basic decorative shapes (star, heart, moon, sun, etc.)

### Edge Styles (use as `style_preset`)

**General:** `DEFAULT`, `ORTHOGONAL`, `STRAIGHT`, `CURVED`, `ENTITY_RELATION`, `DASHED`, `DOTTED`, `BIDIRECTIONAL`, `NO_ARROW`, `OPEN_ARROW`, `DIAMOND_ARROW`, `DIAMOND_EMPTY`

**Styled:** `ROUNDED`, `ROUNDED_DASHED`, `THICK`, `THICK_ROUNDED`

**Colored:** `COLORED_BLUE`, `COLORED_GREEN`, `COLORED_RED`, `COLORED_ORANGE`, `COLORED_PURPLE`, `COLORED_YELLOW`, `COLORED_GRAY`

**UML:** `UML_ASSOCIATION`, `UML_DIRECTED_ASSOCIATION`, `UML_INHERITANCE`, `UML_IMPLEMENTATION`, `UML_DEPENDENCY`, `UML_AGGREGATION`, `UML_COMPOSITION`

**ER:** `ER_ONE_TO_ONE`, `ER_ONE_TO_MANY`, `ER_MANY_TO_MANY`, `ER_ZERO_TO_ONE`, `ER_ZERO_TO_MANY`

**Sequence:** `SEQUENCE_SYNC`, `SEQUENCE_ASYNC`, `SEQUENCE_RETURN`

**BPMN:** `BPMN_FLOW`, `BPMN_MESSAGE_FLOW`

**Flow:** `DATA_FLOW`, `CONTROL_FLOW`, `ASYNC`, `SYNC`

### Color Themes (use with `style build` or `style apply_theme`)

`BLUE`, `GREEN`, `YELLOW`, `ORANGE`, `RED`, `PURPLE`, `GRAY`, `PINK`, `TURQUOISE`, `TEAL`, `DARK_BLUE`, `DARK_GREEN`, `DARK_RED`, `DARK_ORANGE`, `DARK_PURPLE`, `DARK`, `WHITE`, `C4_BLUE`, `C4_LIGHT_BLUE`, `C4_SKY`, `C4_GRAY`

### Connection Ports (use as `exit_port` / `entry_port`)

`TOP`, `BOTTOM`, `LEFT`, `RIGHT`, `TOP_LEFT`, `TOP_RIGHT`, `BOTTOM_LEFT`, `BOTTOM_RIGHT`, `TOP_LEFT_THIRD`, `TOP_RIGHT_THIRD`, `BOTTOM_LEFT_THIRD`, `BOTTOM_RIGHT_THIRD`, `LEFT_TOP_THIRD`, `LEFT_BOTTOM_THIRD`, `RIGHT_TOP_THIRD`, `RIGHT_BOTTOM_THIRD`

## Example Prompts for Copilot

Once the MCP server is running, try these prompts in Copilot agent mode:

- *"Create a flowchart for a user login process and save it as login-flow.drawio"*
- *"Create a C4 context diagram for an e-commerce system"*
- *"Make a UML class diagram with User, Order, and Product classes"*
- *"Create an ER diagram for a blog database with Users, Posts, and Comments tables"*
- *"Build a tree diagram showing a company org chart"*
- *"Create an AWS architecture diagram with API Gateway, Lambda, and DynamoDB"*
- *"Make a Kubernetes deployment diagram with pods, services, and ingress"*
- *"Draw a network topology with servers, switches, and firewalls"*

## Development

```bash
# Run tests
cd drawio-mcp
uv run pytest tests/ -v

# Run the server in dev mode
uv run drawio-mcp
```

## Project Structure

```
drawio-mcp/
├── pyproject.toml              # Project config & dependencies
├── README.md                   # This file
├── src/
│   └── drawio_mcp/
│       ├── __init__.py         # Package init
│       ├── models.py           # Core XML model (DrawioFile, Diagram, MxCell, Geometry, layers, metadata)
│       ├── styles.py           # Style builder, 310+ vertex presets, 44 edge presets, 21 color themes
│       ├── layout.py           # Layout helpers (horizontal, vertical, grid, tree, port distribution)
│       ├── layout_engine.py    # Advanced layout (Sugiyama DAG, overlap resolution, edge routing, polish)
│       ├── validation.py       # Input validation for all tool parameters
│       └── server.py           # MCP server with 5 tools (diagram, draw, style, layout, inspect)
└── tests/
    ├── test_models.py          # Model unit tests
    ├── test_styles.py          # Style system tests
    ├── test_layout.py          # Layout algorithm tests
    ├── test_layout_engine.py   # Layout engine tests
    ├── test_validation.py      # Validation tests
    └── test_server.py          # Integration tests for MCP tools
```

## License

MIT
