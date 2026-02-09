## 🎉 drawio-mcp v1.0.0 — Initial Release

An MCP (Model Context Protocol) server that creates draw.io / diagrams.net XML files programmatically. This lets AI agents (like GitHub Copilot in agent mode) generate draw.io diagrams directly — no browser needed.

### ✨ Highlights

- **5 MCP tools** with 40+ actions covering the full diagram lifecycle
- **310+ vertex style presets** — flowcharts, UML, C4, ER, BPMN, architecture, network, cloud/K8s, and more
- **44 edge style presets** and **21 color themes**
- **Auto-layout engines** — Sugiyama DAG, tree, horizontal, vertical, grid, flowchart
- **Smart edge routing** — obstacle-aware orthogonal routing with automatic port distribution
- **One-call builders** — `build_dag` and `build_full` create complete diagrams in a single tool call
- **Polish command** — one-click cleanup: relayout + overlap resolution + compaction + edge routing + label fixing
- **Multi-page, layers, metadata** — tooltips, links, custom properties, and visibility control
- **Import/export** — load and modify existing `.drawio` files
- **Valid XML** — opens in draw.io desktop, VS Code extension, or diagrams.net

### 📦 Install

```bash
# With uvx (recommended)
uvx drawio-mcp

# With pip
pip install drawio-mcp
```

### 🔧 VS Code / Copilot Integration

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "drawio": {
      "command": "uvx",
      "args": ["drawio-mcp"]
    }
  }
}
```

Then ask Copilot in agent mode to create diagrams!

### 📖 Full Documentation

See the [README](https://github.com/yohasacura/drawio-mcp#readme) for complete tool reference, style presets, and example prompts.
