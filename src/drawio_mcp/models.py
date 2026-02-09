"""
Core XML model classes for draw.io diagrams.

Provides a typed, composable API to build draw.io-compatible XML documents
that adhere to the mxGraph/mxGraphModel schema.
"""

from __future__ import annotations

import html as _html
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PageFormat(Enum):
    """Standard page sizes (width × height in draw.io units ≈ px)."""
    A4_PORTRAIT = (827, 1169)
    A4_LANDSCAPE = (1169, 827)
    LETTER_PORTRAIT = (850, 1100)
    LETTER_LANDSCAPE = (1100, 850)
    A3_PORTRAIT = (1169, 1654)
    A3_LANDSCAPE = (1654, 1169)
    INFINITE = (0, 0)  # page="0" mode


class ArrowType(Enum):
    CLASSIC = "classic"
    CLASSIC_THIN = "classicThin"
    BLOCK = "block"
    BLOCK_THIN = "blockThin"
    OPEN = "open"
    OPEN_THIN = "openThin"
    OVAL = "oval"
    DIAMOND = "diamond"
    DIAMOND_THIN = "diamondThin"
    NONE = "none"


class EdgeStyle(Enum):
    ORTHOGONAL = "orthogonalEdgeStyle"
    ELBOW = "elbowEdgeStyle"
    ENTITY_RELATION = "entityRelationEdgeStyle"
    SEGMENT = "segmentEdgeStyle"
    STRAIGHT = "none"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Point:
    """A 2-D coordinate."""
    x: float
    y: float

    def to_element(self, role: Optional[str] = None) -> ET.Element:
        el = ET.Element("mxPoint", attrib={"x": str(self.x), "y": str(self.y)})
        if role:
            el.set("as", role)
        return el


@dataclass
class Geometry:
    """Geometry of an mxCell (position + size for vertices, relative for edges)."""
    x: float = 0
    y: float = 0
    width: float = 120
    height: float = 60
    relative: bool = False
    source_point: Optional[Point] = None
    target_point: Optional[Point] = None
    offset: Optional[Point] = None
    points: list[Point] = field(default_factory=list)
    # Alternate bounds used when a container is collapsed
    alternate_bounds: Optional['Geometry'] = None

    def to_element(self) -> ET.Element:
        attrib: dict[str, str] = {"as": "geometry"}
        if self.relative:
            attrib["relative"] = "1"
        else:
            attrib["x"] = str(self.x)
            attrib["y"] = str(self.y)
            attrib["width"] = str(self.width)
            attrib["height"] = str(self.height)
        el = ET.Element("mxGeometry", attrib=attrib)
        if self.source_point:
            el.append(self.source_point.to_element("sourcePoint"))
        if self.target_point:
            el.append(self.target_point.to_element("targetPoint"))
        if self.points:
            arr = ET.SubElement(el, "Array", attrib={"as": "points"})
            for pt in self.points:
                arr.append(pt.to_element())
        if self.offset:
            el.append(self.offset.to_element("offset"))
        if self.alternate_bounds:
            ab_attrib: dict[str, str] = {
                "as": "alternateBounds",
                "x": str(self.alternate_bounds.x),
                "y": str(self.alternate_bounds.y),
                "width": str(self.alternate_bounds.width),
                "height": str(self.alternate_bounds.height),
            }
            ET.SubElement(el, "mxGeometry", attrib=ab_attrib)
        return el


@dataclass
class MxCell:
    """A single mxCell element — vertex, edge, or structural cell."""
    id: str
    value: str = ""
    style: str = ""
    parent: str = "1"
    vertex: bool = False
    edge: bool = False
    source: Optional[str] = None
    target: Optional[str] = None
    connectable: Optional[bool] = None
    collapsed: bool = False
    visible: bool = True
    geometry: Optional[Geometry] = None
    # Connection port constraints (0..1 relative to shape, e.g. 0.5,0=top-center)
    exit_x: Optional[float] = None
    exit_y: Optional[float] = None
    exit_dx: float = 0
    exit_dy: float = 0
    entry_x: Optional[float] = None
    entry_y: Optional[float] = None
    entry_dx: float = 0
    entry_dy: float = 0
    # Metadata — rendered via <object> wrapper when any are set
    tooltip: Optional[str] = None
    link: Optional[str] = None
    placeholders: bool = False
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def _has_object_wrapper(self) -> bool:
        """Whether this cell needs an <object> wrapper for metadata."""
        return bool(
            self.tooltip or self.link or self.placeholders or self.metadata
        )

    def to_element(self) -> ET.Element:
        attrib: dict[str, str] = {"id": self.id}
        if self.value:
            # Unescape pre-escaped HTML (e.g. &lt;b&gt; → <b>) so that
            # ET.tostring produces correct single-level escaping.
            attrib["value"] = _html.unescape(self.value)
        # Inject connection port constraints into style
        style = self.style or ""
        if self.edge:
            port_parts: list[str] = []
            if self.exit_x is not None:
                port_parts.append(f"exitX={self.exit_x}")
                port_parts.append(f"exitY={self.exit_y if self.exit_y is not None else 0}")
                port_parts.append(f"exitDx={self.exit_dx}")
                port_parts.append(f"exitDy={self.exit_dy}")
                port_parts.append("exitPerimeter=0")
            if self.entry_x is not None:
                port_parts.append(f"entryX={self.entry_x}")
                port_parts.append(f"entryY={self.entry_y if self.entry_y is not None else 0}")
                port_parts.append(f"entryDx={self.entry_dx}")
                port_parts.append(f"entryDy={self.entry_dy}")
                port_parts.append("entryPerimeter=0")
            if port_parts:
                style = style.rstrip(";") + ";" + ";".join(port_parts) + ";"
        if style:
            attrib["style"] = style
        if self.parent:
            attrib["parent"] = self.parent
        if self.vertex:
            attrib["vertex"] = "1"
        if self.edge:
            attrib["edge"] = "1"
        if self.source:
            attrib["source"] = self.source
        if self.target:
            attrib["target"] = self.target
        if self.connectable is not None and not self.connectable:
            attrib["connectable"] = "0"
        if self.collapsed:
            attrib["collapsed"] = "1"
        if not self.visible:
            attrib["visible"] = "0"
        el = ET.Element("mxCell", attrib=attrib)
        if self.geometry:
            el.append(self.geometry.to_element())

        # Wrap in <object> if metadata fields are set
        if self._has_object_wrapper:
            obj_attrib: dict[str, str] = {
                "label": attrib.pop("value", ""),
                "id": self.id,
            }
            if self.tooltip:
                obj_attrib["tooltip"] = self.tooltip
            if self.link:
                obj_attrib["link"] = self.link
            if self.placeholders:
                obj_attrib["placeholders"] = "1"
            for k, v in self.metadata.items():
                obj_attrib[k] = v
            # Remove id and value from inner mxCell — they move to <object>
            el.attrib.pop("id", None)
            el.attrib.pop("value", None)
            wrapper = ET.Element("object", attrib=obj_attrib)
            wrapper.append(el)
            return wrapper

        return el


@dataclass
class Diagram:
    """A single diagram page inside an mxfile."""
    name: str = "Page-1"
    id: str = field(default_factory=lambda: _uid())
    cells: list[MxCell] | None = None
    # mxGraphModel settings
    dx: int = 1354
    dy: int = 981
    grid: bool = True
    grid_size: int = 10
    guides: bool = True
    tooltips: bool = True
    connect: bool = True
    arrows: bool = True
    fold: bool = True
    page: bool = True
    page_scale: int = 1
    page_width: int = 827
    page_height: int = 1169
    background: str = "none"
    math: bool = False
    shadow: bool = False

    # internal counter
    _next_id: int = field(default=2, init=False, repr=False)

    def __post_init__(self) -> None:
        # Ensure structural cells 0 and 1 always exist
        if self.cells is None:
            self.cells = [
                MxCell(id="0", parent=""),
                MxCell(id="1", parent="0"),
            ]

    def set_page_format(self, fmt: PageFormat) -> None:
        w, h = fmt.value
        if fmt == PageFormat.INFINITE:
            self.page = False
        else:
            self.page = True
            self.page_width = w
            self.page_height = h

    def next_id(self) -> str:
        """Generate a sequential cell ID."""
        cid = str(self._next_id)
        self._next_id += 1
        return cid

    # ----- builder helpers -----

    def add_vertex(
        self,
        value: str,
        x: float,
        y: float,
        width: float = 120,
        height: float = 60,
        style: str = "rounded=1;whiteSpace=wrap;html=1;",
        parent: str = "1",
        cell_id: Optional[str] = None,
    ) -> str:
        cid = cell_id or self.next_id()
        cell = MxCell(
            id=cid,
            value=value,
            style=style,
            parent=parent,
            vertex=True,
            geometry=Geometry(x=x, y=y, width=width, height=height),
        )
        self.cells.append(cell)
        return cid

    def add_edge(
        self,
        source: str,
        target: str,
        value: str = "",
        style: str = "endArrow=classic;html=1;",
        parent: str = "1",
        cell_id: Optional[str] = None,
        waypoints: Optional[list[Point]] = None,
    ) -> str:
        cid = cell_id or self.next_id()
        geom = Geometry(relative=True)
        if waypoints:
            geom.points = waypoints
        cell = MxCell(
            id=cid,
            value=value,
            style=style,
            parent=parent,
            edge=True,
            source=source,
            target=target,
            geometry=geom,
        )
        self.cells.append(cell)
        return cid

    def add_layer(
        self,
        name: str,
        visible: bool = True,
        cell_id: Optional[str] = None,
    ) -> str:
        """Add a new layer to the diagram.

        A layer is an mxCell whose parent is the root cell (id='0').
        All content cells can be parented to a layer to control
        visibility and z-ordering.

        Returns the layer cell ID.
        """
        cid = cell_id or self.next_id()
        cell = MxCell(
            id=cid,
            value=name,
            parent="0",
            visible=visible,
        )
        self.cells.append(cell)
        return cid

    def get_layers(self) -> list[MxCell]:
        """Return all layer cells (cells with parent='0', excluding root)."""
        return [
            c for c in self.cells
            if c.parent == "0" and c.id != "0"
        ]

    def add_group(
        self,
        value: str,
        x: float,
        y: float,
        width: float = 300,
        height: float = 200,
        style: str = "swimlane;startSize=23;fontStyle=1;html=1;",
        parent: str = "1",
        cell_id: Optional[str] = None,
    ) -> str:
        """Add a container/group (swimlane by default)."""
        cid = cell_id or self.next_id()
        cell = MxCell(
            id=cid,
            value=value,
            style=style,
            parent=parent,
            vertex=True,
            geometry=Geometry(x=x, y=y, width=width, height=height),
        )
        self.cells.append(cell)
        return cid

    def add_edge_label(
        self,
        edge_id: str,
        value: str,
        position: float = 0.0,
        offset_x: float = 0,
        offset_y: float = -10,
        style: str = "text;html=1;resizable=0;points=[];align=center;verticalAlign=middle;labelBackgroundColor=none;",
    ) -> str:
        """Add a label positioned along an edge."""
        cid = self.next_id()
        geom = Geometry(x=position, relative=True)
        geom.offset = Point(offset_x, offset_y)
        cell = MxCell(
            id=cid,
            value=value,
            style=style,
            parent=edge_id,
            vertex=True,
            connectable=False,
            geometry=geom,
        )
        self.cells.append(cell)
        return cid

    def to_element(self) -> ET.Element:
        graph_attrs: dict[str, str] = {
            "dx": str(self.dx),
            "dy": str(self.dy),
            "grid": "1" if self.grid else "0",
            "gridSize": str(self.grid_size),
            "guides": "1" if self.guides else "0",
            "tooltips": "1" if self.tooltips else "0",
            "connect": "1" if self.connect else "0",
            "arrows": "1" if self.arrows else "0",
            "fold": "1" if self.fold else "0",
            "page": "1" if self.page else "0",
            "pageScale": str(self.page_scale),
            "pageWidth": str(self.page_width),
            "pageHeight": str(self.page_height),
            "background": self.background,
            "math": "1" if self.math else "0",
            "shadow": "1" if self.shadow else "0",
        }
        model = ET.Element("mxGraphModel", attrib=graph_attrs)
        root = ET.SubElement(model, "root")
        for cell in self.cells:
            root.append(cell.to_element())

        diagram = ET.Element("diagram", attrib={"name": self.name, "id": self.id})
        diagram.append(model)
        return diagram


@dataclass
class DrawioFile:
    """Top-level mxfile container — holds one or more diagram pages."""
    diagrams: list[Diagram] | None = None
    host: str = "drawio-mcp"
    type: str = "device"
    agent: str = "drawio-mcp/1.0"
    version: str = "24.7.17"

    def __post_init__(self) -> None:
        if self.diagrams is None:
            self.diagrams = [Diagram()]

    @property
    def active_diagram(self) -> Diagram:
        return self.diagrams[0]

    def add_diagram(self, name: str = "Page-2") -> Diagram:
        d = Diagram(name=name)
        self.diagrams.append(d)
        return d

    def to_xml(self, pretty: bool = True) -> str:
        import datetime
        mxfile = ET.Element(
            "mxfile",
            attrib={
                "host": self.host,
                "modified": datetime.datetime.now(datetime.timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%S.000Z"
                ),
                "agent": self.agent,
                "version": self.version,
                "type": self.type,
                "compressed": "false",
            },
        )
        for d in self.diagrams:
            mxfile.append(d.to_element())
        if pretty:
            ET.indent(mxfile, space="  ")
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
            mxfile, encoding="unicode"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid() -> str:
    return uuid.uuid4().hex[:12]


def snap_to_grid(value: float, grid_size: int = 10) -> float:
    """Snap a coordinate to the nearest grid point."""
    return round(value / grid_size) * grid_size


@dataclass
class CellBounds:
    """Axis-aligned bounding box for a cell."""
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def cx(self) -> float:
        return self.x + self.width / 2

    @property
    def cy(self) -> float:
        return self.y + self.height / 2

    def intersects(self, other: 'CellBounds', margin: float = 0) -> bool:
        """Check if two bounding boxes overlap (with optional margin)."""
        return not (
            self.right + margin <= other.x
            or other.right + margin <= self.x
            or self.bottom + margin <= other.y
            or other.bottom + margin <= self.y
        )

    def contains_point(self, px: float, py: float, margin: float = 0) -> bool:
        """Check if a point is inside this bounding box (with margin)."""
        return (
            self.x - margin <= px <= self.right + margin
            and self.y - margin <= py <= self.bottom + margin
        )
