# 🎨 Draw.io MCP Server

[![CI](https://github.com/yohasacura/drawio-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/yohasacura/drawio-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/drawio-mcp)](https://pypi.org/project/drawio-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/drawio-mcp)](https://pypi.org/project/drawio-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Let your AI assistant create beautiful draw.io diagrams — just describe what you want.

An [MCP](https://modelcontextprotocol.io/) server that generates [draw.io](https://www.drawio.com/) / [diagrams.net](https://app.diagrams.net/) XML files programmatically. Works with **GitHub Copilot (agent mode)**, **Claude Desktop**, **Cursor**, and any MCP-compatible client.

<!-- mcp-name: io.github.yohasacura/drawio-mcp -->

---

## ✨ What Can It Do?

| Capability | Details |
|---|---|
| 🏗️ **Diagram types** | Flowcharts, UML, ER, C4, BPMN, mindmaps, architecture, network, Kubernetes, and more |
| 🎨 **Styling** | 310+ shape presets, 44 edge styles, 21 color themes |
| 📐 **Auto-layout** | Sugiyama DAG, tree, horizontal, vertical, grid, flowchart engines |
| 🔀 **Smart routing** | Obstacle-aware orthogonal edge routing with automatic port distribution |
| ✏️ **Full editing** | Add, move, resize, delete, restyle any element after creation |
| 📄 **Multi-page** | Multiple pages and layers for complex diagrams |
| 📥 **Import/Export** | Load existing `.drawio` files, modify, and save back |
| 🧹 **One-click cleanup** | Polish command that auto-fixes layout, overlaps, edges, and labels |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- [**uv**](https://docs.astral.sh/uv/) (recommended) or pip

### Install from PyPI

```bash
pip install drawio-mcp
```

Or with uv:

```bash
uvx drawio-mcp
```

### Install from source

```bash
git clone https://github.com/yohasacura/drawio-mcp.git
cd drawio-mcp
uv sync
uv run drawio-mcp
```

---

## 🔌 Setup with Your AI Client

### VS Code (GitHub Copilot)

Add to your VS Code settings or `.vscode/mcp.json`:

```json
{
  "servers": {
    "drawio-mcp": {
      "command": "uvx",
      "args": ["drawio-mcp"]
    }
  }
}
```

Then use **Copilot in Agent mode** and ask it to create diagrams.

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "drawio-mcp": {
      "command": "uvx",
      "args": ["drawio-mcp"]
    }
  }
}
```

### Cursor

Add to your Cursor MCP settings:

```json
{
  "mcpServers": {
    "drawio-mcp": {
      "command": "uvx",
      "args": ["drawio-mcp"]
    }
  }
}
```

---

## 💬 Example Prompts

Once connected, try these in your AI chat:

| Prompt | What you get |
|---|---|
| *"Create a flowchart for a user login process"* | Login flow with decision nodes and error paths |
| *"Create a C4 context diagram for an e-commerce system"* | System context with actors and external systems |
| *"Make a UML class diagram with User, Order, and Product"* | Class diagram with relationships |
| *"Create an ER diagram for a blog database"* | Entity-relationship diagram with tables |
| *"Build an org chart for a startup"* | Tree layout with roles and hierarchy |
| *"Draw an AWS architecture with API Gateway, Lambda, DynamoDB"* | Cloud architecture diagram |
| *"Create a Kubernetes deployment diagram"* | K8s diagram with pods, services, ingress |
| *"Make a network topology with servers and firewalls"* | Network diagram with device icons |

> 💡 **Tip:** Always end with *"...and save it as `filename.drawio`"* to get a file you can open in draw.io.

---

## 🛠️ Tool Reference

The server exposes **5 tools**, each with an `action` parameter:

### `diagram` — Lifecycle

`create` · `save` · `load` · `import_xml` · `list` · `get_xml` · `add_page` · `add_layer`

### `draw` — Content

`add_vertices` · `add_edges` · `add_group` · `update_cells` · `delete_cells` · `add_title` · `add_legend` · `build_dag` · `build_full`

### `style` — Appearance

`build` · `apply_theme` · `list_vertex_presets` · `list_edge_presets` · `list_themes`

### `layout` — Positioning

`sugiyama` · `tree` · `horizontal` · `vertical` · `grid` · `flowchart` · `smart_connect` · `align` · `distribute` · `polish` · `relayout` · `compact` · `reroute_edges` · `resolve_overlaps` · `fix_labels` · `optimize_connections` · `resize_container`

### `inspect` — Read-only

`cells` · `overlaps` · `ports` · `info`

---

## 🎨 Style Reference

<details>
<summary><b>310+ Vertex Presets</b> (click to expand)</summary>

**Basic shapes:** `RECTANGLE` `ROUNDED_RECTANGLE` `ELLIPSE` `CIRCLE` `DIAMOND` `TRIANGLE` `HEXAGON` `CYLINDER` `CLOUD` `PARALLELOGRAM` `ACTOR` `PROCESS` `DOCUMENT` `DATA_STORE` `NOTE` `CARD` `CALLOUT` `TEXT` `CUBE` `STAR` `FOLDER` and more

**Themed boxes:** `BLUE_BOX` `GREEN_BOX` `ORANGE_BOX` `RED_BOX` `YELLOW_BOX` `PURPLE_BOX` `GRAY_BOX` `DARK_BOX` `TEAL_BOX` `WHITE_BOX`

**Flowchart:** `FLOWCHART_PROCESS` `FLOWCHART_DECISION` `FLOWCHART_TERMINATOR` `FLOWCHART_DATA` `FLOWCHART_DOCUMENT` `FLOWCHART_DATABASE` `FLOWCHART_START` `FLOWCHART_END` and 25+ more

**UML:** `UML_CLASS` `UML_INTERFACE` `UML_ACTOR` `UML_COMPONENT` `UML_PACKAGE` `UML_NODE` `UML_LIFELINE` `UML_FRAME`

**C4:** `C4_SYSTEM` `C4_CONTAINER` `C4_COMPONENT` `C4_PERSON` `C4_EXTERNAL` `C4_DATABASE` `C4_WEB_BROWSER`

**ER:** `ER_ENTITY` `ER_WEAK_ENTITY` `ER_ATTRIBUTE` `ER_KEY_ATTRIBUTE` `ER_RELATIONSHIP` and more

**BPMN:** `BPMN_TASK` `BPMN_START_EVENT` `BPMN_END_EVENT` `BPMN_GATEWAY` `BPMN_POOL` `BPMN_LANE` and more

**Architecture:** `ARCH_SERVICE` `ARCH_DATABASE` `ARCH_QUEUE` `ARCH_CLOUD` `ARCH_API` `ARCH_GATEWAY` `ARCH_CONTAINER` `ARCH_FIREWALL` `ARCH_SERVER` `ARCH_LOAD_BALANCER` and 20+ more

**Network:** `NETWORK_SERVER` `NETWORK_ROUTER` `NETWORK_SWITCH` `NETWORK_FIREWALL` `NETWORK_CLOUD` `NETWORK_STORAGE` and 40+ more

**Cloud/K8s:** `AWS_CLOUD` `AWS_LAMBDA` `AWS_S3` `AWS_EC2` `AWS_RDS` `AWS_SQS` `K8S_POD` `K8S_SERVICE` `K8S_DEPLOYMENT` `K8S_INGRESS` and more

**Containers:** `SWIMLANE` `GROUP` `GROUP_TRANSPARENT` `GROUP_DASHED`

**Plus:** State machine, Sequence diagram, Mindmap, DFD, SysML, ArchiMate, Cisco, Mockup/Wireframe, Infographic, and more

</details>

<details>
<summary><b>44 Edge Presets</b> (click to expand)</summary>

**General:** `DEFAULT` `ORTHOGONAL` `STRAIGHT` `CURVED` `ENTITY_RELATION` `DASHED` `DOTTED` `BIDIRECTIONAL` `NO_ARROW`

**Styled:** `ROUNDED` `ROUNDED_DASHED` `THICK` `THICK_ROUNDED`

**Colored:** `COLORED_BLUE` `COLORED_GREEN` `COLORED_RED` `COLORED_ORANGE` `COLORED_PURPLE` `COLORED_YELLOW` `COLORED_GRAY`

**UML:** `UML_ASSOCIATION` `UML_INHERITANCE` `UML_IMPLEMENTATION` `UML_DEPENDENCY` `UML_AGGREGATION` `UML_COMPOSITION`

**ER:** `ER_ONE_TO_ONE` `ER_ONE_TO_MANY` `ER_MANY_TO_MANY` `ER_ZERO_TO_ONE` `ER_ZERO_TO_MANY`

**Flow:** `DATA_FLOW` `CONTROL_FLOW` `ASYNC` `SYNC` `BPMN_FLOW` `BPMN_MESSAGE_FLOW`

</details>

<details>
<summary><b>21 Color Themes</b> (click to expand)</summary>

`BLUE` `GREEN` `YELLOW` `ORANGE` `RED` `PURPLE` `GRAY` `PINK` `TURQUOISE` `TEAL` `DARK_BLUE` `DARK_GREEN` `DARK_RED` `DARK_ORANGE` `DARK_PURPLE` `DARK` `WHITE` `C4_BLUE` `C4_LIGHT_BLUE` `C4_SKY` `C4_GRAY`

</details>

<details>
<summary><b>Connection Ports</b> (click to expand)</summary>

`TOP` `BOTTOM` `LEFT` `RIGHT` `TOP_LEFT` `TOP_RIGHT` `BOTTOM_LEFT` `BOTTOM_RIGHT` `TOP_LEFT_THIRD` `TOP_RIGHT_THIRD` `BOTTOM_LEFT_THIRD` `BOTTOM_RIGHT_THIRD` `LEFT_TOP_THIRD` `LEFT_BOTTOM_THIRD` `RIGHT_TOP_THIRD` `RIGHT_BOTTOM_THIRD`

</details>

---

## 🧑‍💻 Development

```bash
git clone https://github.com/yohasacura/drawio-mcp.git
cd drawio-mcp
uv sync

# Run tests
uv run pytest tests/ -v

# Run the server locally
uv run drawio-mcp
```

### Project Structure

```
src/drawio_mcp/
├── server.py           # MCP server — 5 tools with 40+ actions
├── models.py           # Core XML model (DrawioFile, Diagram, MxCell)
├── styles.py           # Style builder, presets, and themes
├── layout.py           # Layout helpers (tree, grid, port distribution)
├── layout_engine.py    # Advanced layout (Sugiyama, edge routing, polish)
└── validation.py       # Input validation
```

---

## 📝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on bug reports, feature requests, and pull requests.

## 📄 License

[MIT](LICENSE) © [yohasacura](https://github.com/yohasacura)
