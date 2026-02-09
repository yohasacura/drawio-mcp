"""Tests for the draw.io XML model classes."""

from drawio_mcp.models import (
    Diagram,
    DrawioFile,
    Geometry,
    MxCell,
    PageFormat,
    Point,
)


def test_minimal_file() -> None:
    """A minimal DrawioFile produces valid XML with structural cells."""
    df = DrawioFile()
    xml = df.to_xml()
    assert '<?xml version="1.0"' in xml
    assert "<mxfile" in xml
    assert '<mxCell id="0"' in xml
    assert '<mxCell id="1" parent="0"' in xml


def test_add_vertex() -> None:
    df = DrawioFile()
    d = df.active_diagram
    cid = d.add_vertex("Hello", 100, 200, 120, 60)
    xml = df.to_xml()
    assert f'id="{cid}"' in xml
    assert 'value="Hello"' in xml
    assert 'vertex="1"' in xml
    assert 'x="100"' in xml
    assert 'y="200"' in xml


def test_add_edge() -> None:
    df = DrawioFile()
    d = df.active_diagram
    v1 = d.add_vertex("A", 0, 0)
    v2 = d.add_vertex("B", 200, 0)
    eid = d.add_edge(v1, v2, "connects")
    xml = df.to_xml()
    assert f'id="{eid}"' in xml
    assert 'edge="1"' in xml
    assert f'source="{v1}"' in xml
    assert f'target="{v2}"' in xml


def test_add_group_with_children() -> None:
    df = DrawioFile()
    d = df.active_diagram
    gid = d.add_group("Container", 50, 50, 300, 200)
    cid = d.add_vertex("Inside", 20, 40, 100, 40, parent=gid)
    xml = df.to_xml()
    assert f'id="{gid}"' in xml
    assert f'parent="{gid}"' in xml


def test_page_format() -> None:
    df = DrawioFile()
    d = df.active_diagram
    d.set_page_format(PageFormat.A4_LANDSCAPE)
    xml = df.to_xml()
    assert 'pageWidth="1169"' in xml
    assert 'pageHeight="827"' in xml


def test_infinite_canvas() -> None:
    df = DrawioFile()
    d = df.active_diagram
    d.set_page_format(PageFormat.INFINITE)
    xml = df.to_xml()
    assert 'page="0"' in xml


def test_multi_page() -> None:
    df = DrawioFile()
    df.add_diagram("Page-2")
    xml = df.to_xml()
    assert 'name="Page-2"' in xml
    assert xml.count("<diagram") == 2


def test_edge_with_waypoints() -> None:
    df = DrawioFile()
    d = df.active_diagram
    v1 = d.add_vertex("A", 0, 0)
    v2 = d.add_vertex("B", 300, 300)
    pts = [Point(150, 0), Point(150, 300)]
    d.add_edge(v1, v2, waypoints=pts)
    xml = df.to_xml()
    assert "Array" in xml
    assert 'x="150"' in xml


def test_geometry_element() -> None:
    g = Geometry(x=10, y=20, width=100, height=50)
    el = g.to_element()
    assert el.get("x") == "10"
    assert el.get("as") == "geometry"


def test_point_element() -> None:
    p = Point(42, 99)
    el = p.to_element("sourcePoint")
    assert el.get("x") == "42"
    assert el.get("as") == "sourcePoint"


def test_edge_label() -> None:
    df = DrawioFile()
    d = df.active_diagram
    v1 = d.add_vertex("A", 0, 0)
    v2 = d.add_vertex("B", 200, 0)
    eid = d.add_edge(v1, v2)
    lid = d.add_edge_label(eid, "my label")
    xml = df.to_xml()
    assert 'value="my label"' in xml
    assert f'parent="{eid}"' in xml
    assert 'connectable="0"' in xml


# ---- Layers ----

def test_add_layer() -> None:
    """Adding a layer creates a cell with parent='0'."""
    df = DrawioFile()
    d = df.active_diagram
    lid = d.add_layer("Background")
    xml = df.to_xml()
    assert f'id="{lid}"' in xml
    assert f'value="Background"' in xml
    # Layer's parent must be root cell "0"
    cell = next(c for c in d.cells if c.id == lid)
    assert cell.parent == "0"


def test_get_layers() -> None:
    """get_layers returns only layer cells (parent='0', id!='0')."""
    df = DrawioFile()
    d = df.active_diagram
    # Default layer "1" should be returned
    layers = d.get_layers()
    assert len(layers) == 1
    assert layers[0].id == "1"
    # Add another layer
    d.add_layer("Overlay")
    layers = d.get_layers()
    assert len(layers) == 2


def test_layer_visibility() -> None:
    """Layers can be created hidden."""
    df = DrawioFile()
    d = df.active_diagram
    lid = d.add_layer("Hidden Layer", visible=False)
    xml = df.to_xml()
    assert f'visible="0"' in xml


def test_vertex_on_layer() -> None:
    """A vertex can be parented to a specific layer."""
    df = DrawioFile()
    d = df.active_diagram
    lid = d.add_layer("Layer 2")
    vid = d.add_vertex("On Layer 2", 100, 100, parent=lid)
    cell = next(c for c in d.cells if c.id == vid)
    assert cell.parent == lid


# ---- Metadata / <object> wrapper ----

def test_metadata_tooltip() -> None:
    """Cell with tooltip gets an <object> wrapper."""
    df = DrawioFile()
    d = df.active_diagram
    cid = d.add_vertex("Node", 0, 0)
    cell = next(c for c in d.cells if c.id == cid)
    cell.tooltip = "This is a tooltip"
    xml = df.to_xml()
    assert '<object' in xml
    assert 'tooltip="This is a tooltip"' in xml


def test_metadata_link() -> None:
    """Cell with link gets an <object> wrapper with link attribute."""
    df = DrawioFile()
    d = df.active_diagram
    cid = d.add_vertex("Clickable", 0, 0)
    cell = next(c for c in d.cells if c.id == cid)
    cell.link = "https://example.com"
    xml = df.to_xml()
    assert '<object' in xml
    assert 'link="https://example.com"' in xml


def test_metadata_custom_properties() -> None:
    """Cell with custom metadata gets an <object> wrapper."""
    df = DrawioFile()
    d = df.active_diagram
    cid = d.add_vertex("Subnet", 0, 0)
    cell = next(c for c in d.cells if c.id == cid)
    cell.metadata = {"subnet": "192.168.0", "region": "us-east-1"}
    xml = df.to_xml()
    assert '<object' in xml
    assert 'subnet="192.168.0"' in xml
    assert 'region="us-east-1"' in xml


def test_metadata_placeholders() -> None:
    """Cell with placeholders=True gets placeholders='1' on <object>."""
    df = DrawioFile()
    d = df.active_diagram
    cid = d.add_vertex("Host %ip%", 0, 0)
    cell = next(c for c in d.cells if c.id == cid)
    cell.placeholders = True
    cell.metadata = {"ip": "10.0.0.1"}
    xml = df.to_xml()
    assert 'placeholders="1"' in xml
    assert 'ip="10.0.0.1"' in xml


def test_no_object_wrapper_without_metadata() -> None:
    """A plain cell without metadata does NOT get an <object> wrapper."""
    df = DrawioFile()
    d = df.active_diagram
    d.add_vertex("Plain", 0, 0)
    xml = df.to_xml()
    assert '<object' not in xml


# ---- Alternate bounds (collapsed containers) ----

def test_alternate_bounds() -> None:
    """Geometry with alternate_bounds serializes correctly."""
    g = Geometry(x=50, y=50, width=300, height=200)
    g.alternate_bounds = Geometry(x=50, y=50, width=300, height=30)
    el = g.to_element()
    alt = el.find("mxGeometry[@as='alternateBounds']")
    assert alt is not None
    assert alt.get("width") == "300"
    assert alt.get("height") == "30"


# ---- mxfile attributes ----

def test_mxfile_attributes() -> None:
    """DrawioFile includes modified, agent, version in XML."""
    df = DrawioFile()
    xml = df.to_xml()
    assert 'agent="drawio-mcp/1.0"' in xml
    assert 'version=' in xml
    assert 'modified=' in xml
    assert 'host="drawio-mcp"' in xml
