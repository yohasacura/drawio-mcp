# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.2] - 2026-02-09

### Fixed

- Fixed MCP Registry server.json description length (must be <= 100 chars)

## [1.0.1] - 2026-02-09

### Fixed

- Fixed MCP Registry publish workflow (download binary from GitHub Releases)
- Fixed `server.json` schema to match official MCP Registry format
- Merged publish pipeline into release workflow to avoid GITHUB_TOKEN event limitation

## [1.0.0] - 2026-02-09

### Added

- **5 MCP tools** — `diagram`, `draw`, `style`, `layout`, `inspect` — each with an `action` parameter
- **Diagram lifecycle** — create, save, load, import XML, list, get XML, add page, add layer
- **Drawing** — add vertices, edges, groups; update/delete cells; add title, legend
- **One-call builders** — `build_dag` (auto-laid-out DAG) and `build_full` (manual positioning) for complete diagrams in a single call
- **310+ vertex style presets** — basic shapes, flowchart, UML, C4, ER, BPMN, state machine, mindmap, sequence, architecture, network, cloud/K8s, DFD, SysML, ArchiMate, mockup/wireframe, and more
- **44 edge style presets** — general, styled, colored, UML, ER, sequence, BPMN, data/control flow
- **21 color themes** — BLUE, GREEN, DARK, C4_BLUE, etc. with `apply_theme` action
- **Fluent style builder** — construct draw.io style strings from named parameters (colors, fonts, rounded, dashed, shadow, opacity, rotation)
- **Layout engines** — Sugiyama DAG, tree, horizontal, vertical, grid, flowchart
- **Smart edge routing** — obstacle-aware orthogonal routing with automatic port distribution
- **Polish command** — one-click cleanup: relayout + overlap resolution + compaction + edge routing + label fixing
- **Multi-page & layers** — multiple diagram pages and named layers for visibility control
- **Metadata support** — tooltips, clickable links, and custom properties via `<object>` wrappers
- **Import/export** — load existing `.drawio` files (including `<object>`/`<UserObject>` elements), modify, and save back
- **Connection ports** — 16 named port positions (TOP, BOTTOM_LEFT_THIRD, etc.) for precise edge placement
- **Input validation** — comprehensive parameter validation for all tool actions
- **Valid XML output** — adheres to the mxGraph/mxGraphModel schema; opens in draw.io desktop, VS Code draw.io extension, and diagrams.net

[1.0.2]: https://github.com/yohasacura/drawio-mcp/releases/tag/v1.0.2
[1.0.1]: https://github.com/yohasacura/drawio-mcp/releases/tag/v1.0.1
[1.0.0]: https://github.com/yohasacura/drawio-mcp/releases/tag/v1.0.0
