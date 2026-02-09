"""
Style builder and preset library for draw.io cells.

Provides a fluent API to compose style strings and a comprehensive catalog
of pre-built shape / edge / container styles that match draw.io defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Style builder
# ---------------------------------------------------------------------------

class StyleBuilder:
    """Fluent builder for semicolon-delimited draw.io style strings."""

    def __init__(self, base: str = "") -> None:
        self._parts: dict[str, str] = {}
        self._prefix: str = ""
        if base:
            self._parse(base)

    def _parse(self, raw: str) -> None:
        tokens = [t.strip() for t in raw.split(";") if t.strip()]
        for tok in tokens:
            if "=" in tok:
                k, v = tok.split("=", 1)
                self._parts[k] = v
            else:
                # Shape name prefix like "ellipse", "rhombus", etc.
                self._prefix = tok

    # -- appearance --

    def fill_color(self, color: str) -> StyleBuilder:
        self._parts["fillColor"] = color
        return self

    def stroke_color(self, color: str) -> StyleBuilder:
        self._parts["strokeColor"] = color
        return self

    def stroke_width(self, width: float) -> StyleBuilder:
        self._parts["strokeWidth"] = str(width)
        return self

    def font_color(self, color: str) -> StyleBuilder:
        self._parts["fontColor"] = color
        return self

    def font_size(self, size: int) -> StyleBuilder:
        self._parts["fontSize"] = str(size)
        return self

    def font_family(self, family: str) -> StyleBuilder:
        self._parts["fontFamily"] = family
        return self

    def font_style(self, bold: bool = False, italic: bool = False,
                   underline: bool = False, strikethrough: bool = False) -> StyleBuilder:
        val = 0
        if bold:
            val |= 1
        if italic:
            val |= 2
        if underline:
            val |= 4
        if strikethrough:
            val |= 8
        self._parts["fontStyle"] = str(val)
        return self

    def opacity(self, value: int) -> StyleBuilder:
        self._parts["opacity"] = str(value)
        return self

    def fill_opacity(self, value: int) -> StyleBuilder:
        self._parts["fillOpacity"] = str(value)
        return self

    def shadow(self, on: bool = True) -> StyleBuilder:
        self._parts["shadow"] = "1" if on else "0"
        return self

    def glass(self, on: bool = True) -> StyleBuilder:
        self._parts["glass"] = "1" if on else "0"
        return self

    def rounded(self, on: bool = True) -> StyleBuilder:
        self._parts["rounded"] = "1" if on else "0"
        return self

    def dashed(self, on: bool = True, pattern: str = "") -> StyleBuilder:
        self._parts["dashed"] = "1" if on else "0"
        if pattern:
            self._parts["dashPattern"] = pattern
        return self

    def gradient(self, color: str, direction: str = "south") -> StyleBuilder:
        self._parts["gradientColor"] = color
        self._parts["gradientDirection"] = direction
        return self

    def rotation(self, degrees: float) -> StyleBuilder:
        self._parts["rotation"] = str(degrees)
        return self

    # -- text / layout --

    def align(self, h: str = "center", v: str = "middle") -> StyleBuilder:
        self._parts["align"] = h
        self._parts["verticalAlign"] = v
        return self

    def white_space_wrap(self) -> StyleBuilder:
        self._parts["whiteSpace"] = "wrap"
        return self

    def html(self) -> StyleBuilder:
        self._parts["html"] = "1"
        return self

    def spacing(self, all_sides: Optional[int] = None, *,
                top: Optional[int] = None, bottom: Optional[int] = None,
                left: Optional[int] = None, right: Optional[int] = None) -> StyleBuilder:
        if all_sides is not None:
            self._parts["spacing"] = str(all_sides)
        if top is not None:
            self._parts["spacingTop"] = str(top)
        if bottom is not None:
            self._parts["spacingBottom"] = str(bottom)
        if left is not None:
            self._parts["spacingLeft"] = str(left)
        if right is not None:
            self._parts["spacingRight"] = str(right)
        return self

    # -- shape specifics --

    def shape(self, name: str) -> StyleBuilder:
        self._parts["shape"] = name
        return self

    def perimeter(self, name: str) -> StyleBuilder:
        self._parts["perimeter"] = name
        return self

    def image(self, url: str, w: int = 50, h: int = 50) -> StyleBuilder:
        self._parts["shape"] = "image"
        self._parts["image"] = url
        self._parts["imageWidth"] = str(w)
        self._parts["imageHeight"] = str(h)
        return self

    def aspect_fixed(self, on: bool = True) -> StyleBuilder:
        self._parts["aspect"] = "fixed" if on else ""
        return self

    # -- edge specifics --

    def edge_style(self, style: str) -> StyleBuilder:
        self._parts["edgeStyle"] = style
        return self

    def curved(self, on: bool = True) -> StyleBuilder:
        self._parts["curved"] = "1" if on else "0"
        return self

    def end_arrow(self, arrow: str) -> StyleBuilder:
        self._parts["endArrow"] = arrow
        return self

    def start_arrow(self, arrow: str) -> StyleBuilder:
        self._parts["startArrow"] = arrow
        return self

    def end_fill(self, on: bool = True) -> StyleBuilder:
        self._parts["endFill"] = "1" if on else "0"
        return self

    def start_fill(self, on: bool = True) -> StyleBuilder:
        self._parts["startFill"] = "1" if on else "0"
        return self

    def end_size(self, size: float) -> StyleBuilder:
        self._parts["endSize"] = str(size)
        return self

    def start_size(self, size: float) -> StyleBuilder:
        self._parts["startSize"] = str(size)
        return self

    def jetty_size(self, value: str = "auto") -> StyleBuilder:
        self._parts["jettySize"] = value
        return self

    # -- connection points --

    def exit_point(self, x: float, y: float) -> StyleBuilder:
        self._parts["exitX"] = str(x)
        self._parts["exitY"] = str(y)
        return self

    def entry_point(self, x: float, y: float) -> StyleBuilder:
        self._parts["entryX"] = str(x)
        self._parts["entryY"] = str(y)
        return self

    # -- container --

    def container(self, on: bool = True) -> StyleBuilder:
        self._parts["container"] = "1" if on else "0"
        return self

    def collapsible(self, on: bool = True) -> StyleBuilder:
        self._parts["collapsible"] = "1" if on else "0"
        return self

    # -- arbitrary key --

    def set(self, key: str, value: str) -> StyleBuilder:
        self._parts[key] = value
        return self

    # -- build --

    def build(self) -> str:
        parts: list[str] = []
        if self._prefix:
            parts.append(self._prefix)
        for k, v in self._parts.items():
            parts.append(f"{k}={v}")
        return ";".join(parts) + ";"


# ---------------------------------------------------------------------------
# Pre-built vertex style presets
# ---------------------------------------------------------------------------

class VertexStyle:
    """Common vertex style strings matching draw.io defaults."""

    RECTANGLE = "rounded=0;whiteSpace=wrap;html=1;"
    ROUNDED_RECTANGLE = "rounded=1;whiteSpace=wrap;html=1;"
    ELLIPSE = "ellipse;whiteSpace=wrap;html=1;"
    CIRCLE = "ellipse;whiteSpace=wrap;html=1;aspect=fixed;"
    DIAMOND = "rhombus;whiteSpace=wrap;html=1;"
    TRIANGLE = "shape=triangle;perimeter=trianglePerimeter;whiteSpace=wrap;html=1;"
    HEXAGON = "shape=hexagon;perimeter=hexagonPerimeter;whiteSpace=wrap;html=1;"
    CYLINDER = "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;"
    CLOUD = "shape=cloud;whiteSpace=wrap;html=1;"
    PARALLELOGRAM = "shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;"
    ACTOR = "shape=actor;whiteSpace=wrap;html=1;"
    PROCESS = "shape=process;whiteSpace=wrap;html=1;backgroundOutline=1;"
    DOCUMENT = "shape=document;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=0.27;"
    DATA_STORE = "shape=datastore;whiteSpace=wrap;html=1;"
    NOTE = "shape=note;whiteSpace=wrap;html=1;backgroundOutline=1;size=15;"
    CARD = "shape=card;whiteSpace=wrap;html=1;"
    CALLOUT = "shape=callout;whiteSpace=wrap;html=1;perimeter=calloutPerimeter;size=30;position=0.5;position2=0.5;base=20;"
    DOUBLE_ELLIPSE = "shape=doubleEllipse;whiteSpace=wrap;html=1;"
    TEXT = "text;html=1;align=center;verticalAlign=middle;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;"

    # UML
    UML_CLASS = "swimlane;fontStyle=1;align=center;startSize=26;html=1;"
    UML_INTERFACE = "swimlane;fontStyle=3;align=center;startSize=26;html=1;"
    UML_ACTOR = "shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;"
    UML_COMPONENT = "shape=component;align=left;spacingLeft=36;html=1;"
    UML_PACKAGE = "shape=folder;fontStyle=1;tabWidth=110;tabHeight=30;tabPosition=left;html=1;whiteSpace=wrap;"
    UML_NODE = "shape=cube;whiteSpace=wrap;html=1;"
    UML_LIFELINE = "shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;container=1;collapsible=0;recursiveResize=0;outlineConnect=0;"
    UML_FRAME = "shape=umlFrame;whiteSpace=wrap;html=1;width=110;height=30;"

    # Flowchart
    FLOWCHART_PROCESS = "rounded=1;whiteSpace=wrap;html=1;"
    FLOWCHART_DECISION = "rhombus;whiteSpace=wrap;html=1;"
    FLOWCHART_TERMINATOR = "rounded=1;whiteSpace=wrap;html=1;arcSize=50;"
    FLOWCHART_DATA = "shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;"
    FLOWCHART_PREDEFINED = "shape=process;whiteSpace=wrap;html=1;backgroundOutline=1;"
    FLOWCHART_MANUAL_INPUT = "shape=manualInput;whiteSpace=wrap;html=1;size=0.04;"
    FLOWCHART_PREPARATION = "shape=hexagon;perimeter=hexagonPerimeter;whiteSpace=wrap;html=1;"
    FLOWCHART_DELAY = "shape=delay;whiteSpace=wrap;html=1;"
    FLOWCHART_DISPLAY = "shape=display;whiteSpace=wrap;html=1;"
    FLOWCHART_STORED_DATA = "shape=dataStorage;whiteSpace=wrap;html=1;"

    # Network / Cloud
    SERVER = "shape=image;image=img/lib/active_directory/generic_server.svg;html=1;verticalLabelPosition=bottom;verticalAlign=top;"
    DATABASE = "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;"
    LAPTOP = "shape=image;image=img/lib/active_directory/laptop_client.svg;html=1;verticalLabelPosition=bottom;verticalAlign=top;"
    FIREWALL = "shape=mxgraph.cisco.firewalls.firewall;html=1;verticalLabelPosition=bottom;verticalAlign=top;"

    # Container / Group
    SWIMLANE = "swimlane;startSize=23;fontStyle=1;html=1;container=1;collapsible=0;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    SWIMLANE_HORIZONTAL = "swimlane;horizontal=1;startSize=23;fontStyle=1;html=1;container=1;collapsible=0;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    SWIMLANE_VERTICAL = "swimlane;horizontal=0;startSize=23;fontStyle=1;html=1;container=1;collapsible=0;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    GROUP = "group;rounded=1;html=1;container=1;collapsible=0;"
    GROUP_TRANSPARENT = "group;fillColor=none;strokeColor=none;container=1;collapsible=0;"
    GROUP_DASHED = "rounded=1;whiteSpace=wrap;html=1;container=1;collapsible=0;dashed=1;fillColor=none;strokeColor=#666666;"

    # Additional basic shapes
    PENTAGON = "shape=mxgraph.basic.pentagon;whiteSpace=wrap;html=1;"
    TRAPEZOID = "shape=trapezoid;perimeter=trapezoidPerimeter;whiteSpace=wrap;html=1;"
    STAR = "shape=mxgraph.basic.star;whiteSpace=wrap;html=1;"
    ARROW_RIGHT = "shape=singleArrow;whiteSpace=wrap;html=1;"
    ARROW_LEFT = "shape=singleArrow;whiteSpace=wrap;html=1;direction=west;"
    ARROW_UP = "shape=singleArrow;whiteSpace=wrap;html=1;direction=north;"
    ARROW_DOWN = "shape=singleArrow;whiteSpace=wrap;html=1;direction=south;"
    ARROW_DOUBLE = "shape=doubleArrow;whiteSpace=wrap;html=1;"
    CROSS = "shape=cross;whiteSpace=wrap;html=1;"
    CUBE = "shape=cube;whiteSpace=wrap;html=1;"
    STEP = "shape=step;perimeter=stepPerimeter;whiteSpace=wrap;html=1;"
    TAPE = "shape=tape;whiteSpace=wrap;html=1;"
    PLUS = "shape=plus;whiteSpace=wrap;html=1;"
    OR = "shape=or;whiteSpace=wrap;html=1;"
    XOR = "shape=xor;whiteSpace=wrap;html=1;"
    LINE = "line;strokeWidth=4;html=1;"
    IMAGE = "shape=image;html=1;verticalLabelPosition=bottom;verticalAlign=top;"
    LABEL = "shape=label;whiteSpace=wrap;html=1;"
    LINK = "shape=link;whiteSpace=wrap;html=1;"
    FOLDER = "shape=folder;fontStyle=1;tabWidth=110;tabHeight=30;tabPosition=left;html=1;whiteSpace=wrap;"
    CORNER = "shape=corner;whiteSpace=wrap;html=1;"
    TEE = "shape=tee;whiteSpace=wrap;html=1;"
    LOLLIPOP = "shape=lollipop;whiteSpace=wrap;html=1;"
    OFFPAGE_CONNECTOR = "shape=offPageConnector;whiteSpace=wrap;html=1;"
    MANUAL_INPUT = "shape=manualInput;whiteSpace=wrap;html=1;"
    INTERNAL_STORAGE = "shape=internalStorage;whiteSpace=wrap;html=1;dx=15;dy=15;"

    # Cylinder / Database aliases (common naming patterns)
    CYLINDER_DATABASE = "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;"
    DB = "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;"

    # Module / Package / Component
    MODULE = "shape=module;whiteSpace=wrap;html=1;"
    COMPONENT = "shape=component;align=left;spacingLeft=36;html=1;"
    PACKAGE = "shape=folder;fontStyle=1;tabWidth=110;tabHeight=30;tabPosition=left;html=1;whiteSpace=wrap;"

    # I/O shapes
    OUTPUT = "shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;"
    INPUT = "shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;"
    INPUT_OUTPUT = "shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;"

    # Themed basic shapes — good-looking defaults with colors
    BLUE_BOX = "rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    GREEN_BOX = "rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;"
    ORANGE_BOX = "rounded=1;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;"
    RED_BOX = "rounded=1;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;"
    YELLOW_BOX = "rounded=1;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;"
    PURPLE_BOX = "rounded=1;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;"
    GRAY_BOX = "rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;fontColor=#333333;"
    DARK_BLUE_BOX = "rounded=1;whiteSpace=wrap;html=1;fillColor=#1ba1e2;strokeColor=#006eaf;fontColor=#ffffff;"
    DARK_BOX = "rounded=1;whiteSpace=wrap;html=1;fillColor=#333333;strokeColor=#000000;fontColor=#ffffff;"
    PINK_BOX = "rounded=1;whiteSpace=wrap;html=1;fillColor=#e6d0de;strokeColor=#996185;"
    TEAL_BOX = "rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#6a9153;"
    WHITE_BOX = "rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#000000;"

    # Architecture / infra icons
    ARCH_SERVICE = "rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;arcSize=10;"
    ARCH_DATABASE = "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    ARCH_QUEUE = "shape=delay;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;"
    ARCH_CLOUD = "shape=cloud;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;"
    ARCH_USER = "shape=actor;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;"
    ARCH_PERSON = "shape=actor;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;"
    ARCH_COMPONENT = "shape=component;align=left;spacingLeft=36;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    ARCH_EXTERNAL = "rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;dashed=1;"
    ARCH_API = "rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontStyle=1;"
    ARCH_GATEWAY = "shape=hexagon;perimeter=hexagonPerimeter;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;"
    ARCH_STORAGE = "shape=dataStorage;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    ARCH_CACHE = "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#fff2cc;strokeColor=#d6b656;"
    ARCH_CONTAINER = "swimlane;startSize=30;fontStyle=1;html=1;container=1;collapsible=0;fillColor=#f5f5f5;strokeColor=#666666;rounded=1;arcSize=6;swimlaneLine=0;"
    ARCH_ZONE = "swimlane;startSize=30;fontStyle=1;html=1;container=1;collapsible=0;fillColor=none;strokeColor=#666666;dashed=1;rounded=1;arcSize=6;swimlaneLine=0;"
    ARCH_LOAD_BALANCER = "shape=mxgraph.networks.load_balancer;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;"
    ARCH_FIREWALL = "shape=mxgraph.networks.firewall;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;"
    ARCH_SERVER = "shape=mxgraph.networks.server;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    ARCH_WEB_SERVER = "shape=mxgraph.networks.web_server;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;"
    ARCH_ROUTER = "shape=mxgraph.networks.router;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    ARCH_SWITCH = "shape=mxgraph.networks.switch;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    ARCH_RACK = "shape=mxgraph.networks.rack;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    ARCH_MOBILE = "shape=mxgraph.networks.mobile;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;"
    ARCH_LAPTOP = "shape=mxgraph.networks.laptop;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;"
    ARCH_MONITOR = "shape=mxgraph.networks.monitor;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    ARCH_DESKTOP = "shape=mxgraph.networks.desktop_pc;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    ARCH_PRINTER = "shape=mxgraph.networks.printer;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;"
    ARCH_HUB = "shape=mxgraph.networks.hub;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    ARCH_MAINFRAME = "shape=mxgraph.networks.mainframe;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    ARCH_VIRTUAL_SERVER = "shape=mxgraph.networks.virtual_server;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    ARCH_TABLET = "shape=mxgraph.networks.tablet;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;"
    ARCH_SATELLITE = "shape=mxgraph.networks.satellite;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    ARCH_RADIO_TOWER = "shape=mxgraph.networks.radio_tower;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"

    # Network / Infrastructure (plain, without colors)
    NETWORK_SERVER = "shape=mxgraph.networks.server;whiteSpace=wrap;html=1;"
    NETWORK_WEB_SERVER = "shape=mxgraph.networks.web_server;whiteSpace=wrap;html=1;"
    NETWORK_MAIL_SERVER = "shape=mxgraph.networks.mail_server;whiteSpace=wrap;html=1;"
    NETWORK_PROXY_SERVER = "shape=mxgraph.networks.proxy_server;whiteSpace=wrap;html=1;"
    NETWORK_VIRTUAL_SERVER = "shape=mxgraph.networks.virtual_server;whiteSpace=wrap;html=1;"
    NETWORK_SERVER_STORAGE = "shape=mxgraph.networks.server_storage;whiteSpace=wrap;html=1;"
    NETWORK_ROUTER = "shape=mxgraph.networks.router;whiteSpace=wrap;html=1;"
    NETWORK_SWITCH = "shape=mxgraph.networks.switch;whiteSpace=wrap;html=1;"
    NETWORK_HUB = "shape=mxgraph.networks.hub;whiteSpace=wrap;html=1;"
    NETWORK_FIREWALL = "shape=mxgraph.networks.firewall;whiteSpace=wrap;html=1;"
    NETWORK_LOAD_BALANCER = "shape=mxgraph.networks.load_balancer;whiteSpace=wrap;html=1;"
    NETWORK_CLOUD = "shape=mxgraph.networks.cloud;whiteSpace=wrap;html=1;"
    NETWORK_STORAGE = "shape=mxgraph.networks.storage;whiteSpace=wrap;html=1;"
    NETWORK_EXTERNAL_STORAGE = "shape=mxgraph.networks.external_storage;whiteSpace=wrap;html=1;"
    NETWORK_TAPE_STORAGE = "shape=mxgraph.networks.tape_storage;whiteSpace=wrap;html=1;"
    NETWORK_NAS = "shape=mxgraph.networks.nas_filer;whiteSpace=wrap;html=1;"
    NETWORK_RACK = "shape=mxgraph.networks.rack;whiteSpace=wrap;html=1;"
    NETWORK_MAINFRAME = "shape=mxgraph.networks.mainframe;whiteSpace=wrap;html=1;"
    NETWORK_SUPERCOMPUTER = "shape=mxgraph.networks.supercomputer;whiteSpace=wrap;html=1;"
    NETWORK_LAPTOP = "shape=mxgraph.networks.laptop;whiteSpace=wrap;html=1;"
    NETWORK_DESKTOP = "shape=mxgraph.networks.desktop_pc;whiteSpace=wrap;html=1;"
    NETWORK_PC = "shape=mxgraph.networks.pc;whiteSpace=wrap;html=1;"
    NETWORK_VIRTUAL_PC = "shape=mxgraph.networks.virtual_pc;whiteSpace=wrap;html=1;"
    NETWORK_MONITOR = "shape=mxgraph.networks.monitor;whiteSpace=wrap;html=1;"
    NETWORK_TERMINAL = "shape=mxgraph.networks.terminal;whiteSpace=wrap;html=1;"
    NETWORK_TABLET = "shape=mxgraph.networks.tablet;whiteSpace=wrap;html=1;"
    NETWORK_MOBILE = "shape=mxgraph.networks.mobile;whiteSpace=wrap;html=1;"
    NETWORK_MODEM = "shape=mxgraph.networks.modem;whiteSpace=wrap;html=1;"
    NETWORK_WIRELESS_HUB = "shape=mxgraph.networks.wireless_hub;whiteSpace=wrap;html=1;"
    NETWORK_WIRELESS_MODEM = "shape=mxgraph.networks.wireless_modem;whiteSpace=wrap;html=1;"
    NETWORK_PRINTER = "shape=mxgraph.networks.printer;whiteSpace=wrap;html=1;"
    NETWORK_COPIER = "shape=mxgraph.networks.copier;whiteSpace=wrap;html=1;"
    NETWORK_SCANNER = "shape=mxgraph.networks.scanner;whiteSpace=wrap;html=1;"
    NETWORK_DVR = "shape=mxgraph.networks.dvr;whiteSpace=wrap;html=1;"
    NETWORK_SATELLITE = "shape=mxgraph.networks.satellite;whiteSpace=wrap;html=1;"
    NETWORK_SATELLITE_DISH = "shape=mxgraph.networks.satellite_dish;whiteSpace=wrap;html=1;"
    NETWORK_RADIO_TOWER = "shape=mxgraph.networks.radio_tower;whiteSpace=wrap;html=1;"
    NETWORK_SECURITY_CAMERA = "shape=mxgraph.networks.security_camera;whiteSpace=wrap;html=1;"
    NETWORK_PATCH_PANEL = "shape=mxgraph.networks.patch_panel;whiteSpace=wrap;html=1;"
    NETWORK_COMM_LINK = "shape=mxgraph.networks.comm_link;whiteSpace=wrap;html=1;"
    NETWORK_USB_STICK = "shape=mxgraph.networks.usb_stick;whiteSpace=wrap;html=1;"
    NETWORK_USERS = "shape=mxgraph.networks.users;whiteSpace=wrap;html=1;"
    NETWORK_USER_MALE = "shape=mxgraph.networks.user_male;whiteSpace=wrap;html=1;"
    NETWORK_USER_FEMALE = "shape=mxgraph.networks.user_female;whiteSpace=wrap;html=1;"
    NETWORK_SECURED = "shape=mxgraph.networks.secured;whiteSpace=wrap;html=1;"
    NETWORK_UNSECURE = "shape=mxgraph.networks.unsecure;whiteSpace=wrap;html=1;"
    NETWORK_UPS = "shape=mxgraph.networks.ups_enterprise;whiteSpace=wrap;html=1;"
    NETWORK_VIRUS = "shape=mxgraph.networks.virus;whiteSpace=wrap;html=1;"
    NETWORK_GAMEPAD = "shape=mxgraph.networks.gamepad;whiteSpace=wrap;html=1;"
    NETWORK_VIDEO_PROJECTOR = "shape=mxgraph.networks.video_projector;whiteSpace=wrap;html=1;"
    NETWORK_BIOMETRIC_READER = "shape=mxgraph.networks.biometric_reader;whiteSpace=wrap;html=1;"

    # Flowchart (additional)
    FLOWCHART_DOCUMENT = "shape=document;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=0.27;"
    FLOWCHART_MULTI_DOCUMENT = "shape=mxgraph.flowchart.multi-document;whiteSpace=wrap;html=1;"
    FLOWCHART_DATABASE = "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;"
    FLOWCHART_DIRECT_DATA = "shape=dataStorage;whiteSpace=wrap;html=1;"
    FLOWCHART_INTERNAL_STORAGE = "shape=internalStorage;whiteSpace=wrap;html=1;dx=15;dy=15;"
    FLOWCHART_PAPER_TAPE = "shape=mxgraph.flowchart.paper_tape;whiteSpace=wrap;html=1;"
    FLOWCHART_MANUAL_OPERATION = "shape=trapezoid;perimeter=trapezoidPerimeter;whiteSpace=wrap;html=1;"
    FLOWCHART_LOOP_LIMIT = "shape=mxgraph.flowchart.loop_limit;whiteSpace=wrap;html=1;"
    FLOWCHART_COLLATE = "shape=mxgraph.flowchart.collate;whiteSpace=wrap;html=1;"
    FLOWCHART_SORT = "shape=mxgraph.flowchart.sort;whiteSpace=wrap;html=1;"
    FLOWCHART_MERGE = "shape=mxgraph.flowchart.merge_or_storage;whiteSpace=wrap;html=1;"
    FLOWCHART_EXTRACT = "shape=mxgraph.flowchart.extract_or_measurement;whiteSpace=wrap;html=1;"
    FLOWCHART_OR = "shape=mxgraph.flowchart.or;whiteSpace=wrap;html=1;"
    FLOWCHART_SUMMING = "shape=mxgraph.flowchart.summing_function;whiteSpace=wrap;html=1;"
    FLOWCHART_CARD = "shape=card;whiteSpace=wrap;html=1;"
    FLOWCHART_ON_PAGE_REF = "shape=mxgraph.flowchart.on-page_reference;whiteSpace=wrap;html=1;"
    FLOWCHART_OFF_PAGE_REF = "shape=offPageConnector;whiteSpace=wrap;html=1;"
    FLOWCHART_ANNOTATION = "shape=mxgraph.flowchart.annotation_1;whiteSpace=wrap;html=1;"
    FLOWCHART_START = "rounded=1;whiteSpace=wrap;html=1;arcSize=50;"
    FLOWCHART_END = "rounded=1;whiteSpace=wrap;html=1;arcSize=50;"
    FLOWCHART_TRANSFER = "shape=mxgraph.flowchart.transfer;whiteSpace=wrap;html=1;"
    FLOWCHART_SEQUENTIAL_DATA = "shape=mxgraph.flowchart.sequential_data;whiteSpace=wrap;html=1;"
    FLOWCHART_PARALLEL_MODE = "shape=mxgraph.flowchart.parallel_mode;whiteSpace=wrap;html=1;"

    # Labels / Titles
    TITLE = "text;html=1;align=center;verticalAlign=middle;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;fontSize=20;fontStyle=1;"
    SUBTITLE = "text;html=1;align=center;verticalAlign=middle;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;fontSize=14;fontColor=#666666;"
    ANNOTATION = "text;html=1;align=center;verticalAlign=middle;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;fontSize=11;"
    BADGE = "rounded=1;whiteSpace=wrap;html=1;arcSize=50;fillColor=#e1d5e7;strokeColor=#9673a6;fontSize=10;"

    # Software Architecture / C4
    C4_SYSTEM = "rounded=1;whiteSpace=wrap;html=1;fillColor=#438DD5;fontColor=#ffffff;strokeColor=none;fontSize=14;arcSize=6;"
    C4_CONTAINER = "rounded=1;whiteSpace=wrap;html=1;fillColor=#23A2D9;fontColor=#ffffff;strokeColor=none;fontSize=14;arcSize=6;"
    C4_COMPONENT = "rounded=1;whiteSpace=wrap;html=1;fillColor=#85BBF0;fontColor=#000000;strokeColor=none;fontSize=14;arcSize=6;"
    C4_PERSON = "shape=actor;whiteSpace=wrap;html=1;fillColor=#08427B;fontColor=#ffffff;strokeColor=none;fontSize=14;"
    C4_EXTERNAL = "rounded=1;whiteSpace=wrap;html=1;fillColor=#999999;fontColor=#ffffff;strokeColor=none;fontSize=14;arcSize=6;"
    C4_DATABASE = "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#438DD5;fontColor=#ffffff;strokeColor=none;fontSize=14;"
    C4_WEB_BROWSER = "shape=mxgraph.c4.webBrowserContainer;whiteSpace=wrap;html=1;fillColor=#23A2D9;fontColor=#ffffff;strokeColor=none;fontSize=14;"

    # ER Diagram
    ER_ENTITY = "swimlane;fontStyle=1;align=center;startSize=26;html=1;whiteSpace=wrap;"
    ER_WEAK_ENTITY = "swimlane;fontStyle=1;align=center;startSize=26;html=1;whiteSpace=wrap;double=1;"
    ER_ATTRIBUTE = "ellipse;whiteSpace=wrap;html=1;"
    ER_KEY_ATTRIBUTE = "ellipse;whiteSpace=wrap;html=1;fontStyle=4;"
    ER_DERIVED_ATTRIBUTE = "ellipse;whiteSpace=wrap;html=1;dashed=1;"
    ER_MULTI_VALUED = "shape=doubleEllipse;whiteSpace=wrap;html=1;"
    ER_RELATIONSHIP = "rhombus;whiteSpace=wrap;html=1;"

    # State Machine
    STATE = "rounded=1;whiteSpace=wrap;html=1;"
    STATE_INITIAL = "ellipse;html=1;shape=doubleCircle;whiteSpace=wrap;aspect=fixed;fillColor=#000000;fontColor=#ffffff;"
    STATE_FINAL = "ellipse;html=1;shape=doubleCircle;whiteSpace=wrap;aspect=fixed;"
    STATE_CHOICE = "rhombus;whiteSpace=wrap;html=1;aspect=fixed;"
    STATE_HISTORY = "ellipse;whiteSpace=wrap;html=1;aspect=fixed;"
    STATE_FORK_JOIN = "line;strokeWidth=4;html=1;fillColor=#000000;"

    # BPMN
    BPMN_TASK = "rounded=1;whiteSpace=wrap;html=1;"
    BPMN_START_EVENT = "ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    BPMN_END_EVENT = "ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#f8cecc;strokeColor=#b85450;strokeWidth=3;"
    BPMN_INTERMEDIATE_EVENT = "ellipse;whiteSpace=wrap;html=1;aspect=fixed;strokeWidth=2;"
    BPMN_GATEWAY = "rhombus;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#fff2cc;strokeColor=#d6b656;"
    BPMN_EXCLUSIVE_GATEWAY = "rhombus;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#fff2cc;strokeColor=#d6b656;"
    BPMN_PARALLEL_GATEWAY = "rhombus;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#fff2cc;strokeColor=#d6b656;"
    BPMN_POOL = "swimlane;startSize=23;fontStyle=1;html=1;"
    BPMN_LANE = "swimlane;startSize=23;html=1;"
    BPMN_SUB_PROCESS = "rounded=1;whiteSpace=wrap;html=1;container=1;collapsible=0;"
    BPMN_DATA_OBJECT = "shape=note;whiteSpace=wrap;html=1;backgroundOutline=1;size=15;"

    # Mindmap
    MINDMAP_ROOT = "rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;arcSize=50;fontSize=16;fontStyle=1;"
    MINDMAP_BRANCH = "rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;arcSize=50;"
    MINDMAP_LEAF = "rounded=1;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;arcSize=50;"

    # Sequence Diagram
    SEQUENCE_LIFELINE = "shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;container=1;collapsible=0;recursiveResize=0;outlineConnect=0;"
    SEQUENCE_ACTIVATION = "rounded=0;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    SEQUENCE_FRAME = "shape=umlFrame;whiteSpace=wrap;html=1;width=110;height=30;"

    # DFD (Data Flow Diagram)
    DFD_PROCESS = "ellipse;whiteSpace=wrap;html=1;"
    DFD_EXTERNAL_ENTITY = "shape=mxgraph.dfd.externalEntity;whiteSpace=wrap;html=1;"
    DFD_DATA_STORE = "shape=mxgraph.dfd.dataStoreID;whiteSpace=wrap;html=1;"

    # AWS / Cloud shapes (simplified stencils)
    AWS_CLOUD = "shape=mxgraph.aws4.productIcon;whiteSpace=wrap;html=1;"
    AWS_LAMBDA = "shape=mxgraph.aws3d.lambda;whiteSpace=wrap;html=1;"
    AWS_S3 = "shape=mxgraph.aws3d.s3;whiteSpace=wrap;html=1;"
    AWS_EC2 = "shape=mxgraph.aws3d.instance;whiteSpace=wrap;html=1;"
    AWS_RDS = "shape=mxgraph.aws3d.rds;whiteSpace=wrap;html=1;"
    AWS_VPC = "shape=mxgraph.aws3d.vpcGateway;whiteSpace=wrap;html=1;"
    AWS_ELB = "shape=mxgraph.aws3d.elasticLoadBalancing;whiteSpace=wrap;html=1;"
    AWS_CLOUDFRONT = "shape=mxgraph.aws3d.cloudfront;whiteSpace=wrap;html=1;"
    AWS_ROUTE53 = "shape=mxgraph.aws3d.route53;whiteSpace=wrap;html=1;"
    AWS_SQS = "shape=mxgraph.aws3d.sqs;whiteSpace=wrap;html=1;"
    AWS_DYNAMODB = "shape=mxgraph.aws3d.dynamoDB;whiteSpace=wrap;html=1;"
    AWS_REDSHIFT = "shape=mxgraph.aws3d.redshift;whiteSpace=wrap;html=1;"

    # Azure shapes (stencils)
    AZURE = "shape=mxgraph.azure.cloud;whiteSpace=wrap;html=1;"

    # GCP shapes (stencils)
    GCP = "shape=mxgraph.gcp2.doubleRect;whiteSpace=wrap;html=1;"

    # Kubernetes
    K8S_POD = "shape=mxgraph.kubernetes.icon;whiteSpace=wrap;html=1;prIcon=pod;"
    K8S_SERVICE = "shape=mxgraph.kubernetes.icon;whiteSpace=wrap;html=1;prIcon=svc;"
    K8S_DEPLOYMENT = "shape=mxgraph.kubernetes.icon;whiteSpace=wrap;html=1;prIcon=deploy;"
    K8S_NODE = "shape=mxgraph.kubernetes.icon;whiteSpace=wrap;html=1;prIcon=node;"
    K8S_INGRESS = "shape=mxgraph.kubernetes.icon;whiteSpace=wrap;html=1;prIcon=ing;"
    K8S_NAMESPACE = "shape=mxgraph.kubernetes.icon2;whiteSpace=wrap;html=1;prIcon=ns;"
    K8S_CONFIGMAP = "shape=mxgraph.kubernetes.icon;whiteSpace=wrap;html=1;prIcon=cm;"
    K8S_SECRET = "shape=mxgraph.kubernetes.icon;whiteSpace=wrap;html=1;prIcon=secret;"
    K8S_VOLUME = "shape=mxgraph.kubernetes.icon;whiteSpace=wrap;html=1;prIcon=pv;"

    # Cisco / Network Infrastructure
    CISCO_ROUTER = "shape=mxgraph.cisco.routers.router;whiteSpace=wrap;html=1;"
    CISCO_SWITCH = "shape=mxgraph.cisco.switches.layer_2_switch;whiteSpace=wrap;html=1;"
    CISCO_FIREWALL = "shape=mxgraph.cisco.firewalls.firewall;whiteSpace=wrap;html=1;"

    # EIP (Enterprise Integration Patterns)
    EIP_MESSAGE_CHANNEL = "shape=mxgraph.eip.messageChannel;whiteSpace=wrap;html=1;"

    # Electrical / Electronics (basic)
    ELECTRICAL_RESISTOR = "shape=mxgraph.electrical.resistors.resistor_1;whiteSpace=wrap;html=1;"
    ELECTRICAL_CAPACITOR = "shape=mxgraph.electrical.capacitors.capacitor;whiteSpace=wrap;html=1;"
    ELECTRICAL_LOGIC_GATE = "shape=mxgraph.electrical.logic_gates.logic_gate;whiteSpace=wrap;html=1;"

    # SysML
    SYSML_BLOCK = "shape=mxgraph.sysml.package;whiteSpace=wrap;html=1;"
    SYSML_REQUIREMENT = "shape=mxgraph.sysml.composite;whiteSpace=wrap;html=1;"

    # Infographic shapes
    INFOGRAPHIC_BANNER = "shape=mxgraph.infographic.banner;whiteSpace=wrap;html=1;"
    INFOGRAPHIC_RIBBON = "shape=mxgraph.infographic.ribbonSimple;whiteSpace=wrap;html=1;"
    INFOGRAPHIC_FLAG = "shape=mxgraph.infographic.flag;whiteSpace=wrap;html=1;"
    INFOGRAPHIC_SHADED_CUBE = "shape=mxgraph.infographic.shadedCube;whiteSpace=wrap;html=1;"
    INFOGRAPHIC_CYLINDER = "shape=mxgraph.infographic.cylinder;whiteSpace=wrap;html=1;"
    INFOGRAPHIC_PYRAMID = "shape=mxgraph.infographic.shadedPyramid;whiteSpace=wrap;html=1;"

    # Lean Mapping
    LEAN_PROCESS = "rounded=1;whiteSpace=wrap;html=1;"
    LEAN_INVENTORY = "shape=triangle;perimeter=trianglePerimeter;whiteSpace=wrap;html=1;"
    LEAN_KAIZEN = "shape=mxgraph.lean_mapping.kaizen_lightening_burst;whiteSpace=wrap;html=1;"

    # Mockup / Wireframe
    MOCKUP_BROWSER = "shape=mxgraph.mockup.containers.browserWindow;whiteSpace=wrap;html=1;"
    MOCKUP_BUTTON = "shape=mxgraph.mockup.buttons.button;whiteSpace=wrap;html=1;"
    MOCKUP_TEXT_INPUT = "shape=mxgraph.mockup.text.textBox;whiteSpace=wrap;html=1;"

    # ArchiMate
    ARCHIMATE_APPLICATION = "shape=mxgraph.archimate3.application;whiteSpace=wrap;html=1;"
    ARCHIMATE_TECH = "shape=mxgraph.archimate3.tech;whiteSpace=wrap;html=1;"
    ARCHIMATE_BUSINESS = "shape=mxgraph.archimate.business;whiteSpace=wrap;html=1;"

    # Stencil-based basic shapes
    BASIC_STAR = "shape=mxgraph.basic.star;whiteSpace=wrap;html=1;"
    BASIC_HEART = "shape=mxgraph.basic.heart;whiteSpace=wrap;html=1;"
    BASIC_MOON = "shape=mxgraph.basic.moon;whiteSpace=wrap;html=1;"
    BASIC_SUN = "shape=mxgraph.basic.sun;whiteSpace=wrap;html=1;"
    BASIC_SMILEY = "shape=mxgraph.basic.smiley;whiteSpace=wrap;html=1;"
    BASIC_FLASH = "shape=mxgraph.basic.flash;whiteSpace=wrap;html=1;"
    BASIC_BANNER = "shape=mxgraph.basic.banner;whiteSpace=wrap;html=1;"
    BASIC_CONE = "shape=mxgraph.basic.cone;whiteSpace=wrap;html=1;"
    BASIC_TICK = "shape=mxgraph.basic.tick;whiteSpace=wrap;html=1;"
    BASIC_CROSS_SHAPE = "shape=mxgraph.basic.cross;whiteSpace=wrap;html=1;"
    BASIC_NO_SYMBOL = "shape=mxgraph.basic.no_symbol;whiteSpace=wrap;html=1;"
    BASIC_OCTAGON = "shape=mxgraph.basic.octagon;whiteSpace=wrap;html=1;"
    BASIC_DONUT = "shape=mxgraph.basic.donut;whiteSpace=wrap;html=1;"
    BASIC_ISO_CUBE = "shape=mxgraph.basic.isocube;whiteSpace=wrap;html=1;"
    BASIC_PYRAMID = "shape=mxgraph.basic.pyramid;whiteSpace=wrap;html=1;"
    BASIC_LAYERED_RECT = "shape=mxgraph.basic.layered_rect;whiteSpace=wrap;html=1;"
    BASIC_WAVE = "shape=mxgraph.basic.wave;whiteSpace=wrap;html=1;"
    BASIC_4_POINT_STAR = "shape=mxgraph.basic.4_point_star;whiteSpace=wrap;html=1;"
    BASIC_6_POINT_STAR = "shape=mxgraph.basic.6_point_star;whiteSpace=wrap;html=1;"
    BASIC_8_POINT_STAR = "shape=mxgraph.basic.8_point_star;whiteSpace=wrap;html=1;"

    # BPMN2 additional stencil shapes
    BPMN_TIMER_EVENT = "shape=mxgraph.bpmn.shape;perimeter=mxPerimeter.EllipsePerimeter;symbol=timer;whiteSpace=wrap;html=1;"
    BPMN_MESSAGE_EVENT = "shape=mxgraph.bpmn.shape;perimeter=mxPerimeter.EllipsePerimeter;symbol=message;whiteSpace=wrap;html=1;"
    BPMN_ERROR_EVENT = "shape=mxgraph.bpmn.shape;perimeter=mxPerimeter.EllipsePerimeter;symbol=error;whiteSpace=wrap;html=1;"


class EdgeStylePreset:
    """Common edge style strings matching draw.io defaults."""

    DEFAULT = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;"
    ORTHOGONAL = "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;"
    STRAIGHT = "endArrow=classic;html=1;"
    CURVED = "curved=1;endArrow=classic;html=1;"
    ENTITY_RELATION = "edgeStyle=entityRelationEdgeStyle;endArrow=ERmandOne;startArrow=ERmandOne;html=1;"
    DASHED = "endArrow=classic;html=1;dashed=1;"
    DOTTED = "endArrow=classic;html=1;dashed=1;dashPattern=1 4;"
    BIDIRECTIONAL = "endArrow=classic;startArrow=classic;html=1;"
    NO_ARROW = "endArrow=none;html=1;"
    OPEN_ARROW = "endArrow=open;endFill=0;html=1;"
    DIAMOND_ARROW = "endArrow=diamond;endFill=1;html=1;"
    DIAMOND_EMPTY = "endArrow=diamond;endFill=0;html=1;"

    # UML
    UML_ASSOCIATION = "endArrow=none;html=1;"
    UML_DIRECTED_ASSOCIATION = "endArrow=open;endFill=0;html=1;"
    UML_INHERITANCE = "endArrow=block;endFill=0;html=1;"
    UML_IMPLEMENTATION = "endArrow=block;endFill=0;dashed=1;html=1;"
    UML_DEPENDENCY = "endArrow=open;endFill=0;dashed=1;html=1;"
    UML_AGGREGATION = "endArrow=diamond;endFill=0;html=1;"
    UML_COMPOSITION = "endArrow=diamond;endFill=1;html=1;"

    # ER
    ER_ONE_TO_ONE = "edgeStyle=entityRelationEdgeStyle;endArrow=ERmandOne;startArrow=ERmandOne;html=1;"
    ER_ONE_TO_MANY = "edgeStyle=entityRelationEdgeStyle;endArrow=ERmany;startArrow=ERmandOne;html=1;"
    ER_MANY_TO_MANY = "edgeStyle=entityRelationEdgeStyle;endArrow=ERmany;startArrow=ERmany;html=1;"
    ER_ZERO_TO_ONE = "edgeStyle=entityRelationEdgeStyle;endArrow=ERmandOne;startArrow=ERzeroToOne;html=1;"
    ER_ZERO_TO_MANY = "edgeStyle=entityRelationEdgeStyle;endArrow=ERmany;startArrow=ERzeroToOne;html=1;"

    # Sequence
    SEQUENCE_SYNC = "endArrow=block;endFill=1;html=1;"
    SEQUENCE_ASYNC = "endArrow=open;endFill=0;html=1;"
    SEQUENCE_RETURN = "endArrow=open;endFill=0;dashed=1;html=1;"

    # BPMN
    BPMN_FLOW = "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;"
    BPMN_MESSAGE_FLOW = "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=open;endFill=0;dashed=1;"

    # Architecture / styled connectors
    ROUNDED = "rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;edgeStyle=orthogonalEdgeStyle;"
    ROUNDED_DASHED = "rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;edgeStyle=orthogonalEdgeStyle;dashed=1;"
    THICK = "endArrow=classic;html=1;strokeWidth=2;"
    THICK_ROUNDED = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;strokeWidth=2;"
    COLORED_BLUE = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;strokeColor=#6c8ebf;"
    COLORED_GREEN = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;strokeColor=#82b366;"
    COLORED_RED = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;strokeColor=#b85450;"
    COLORED_ORANGE = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;strokeColor=#d79b00;"
    COLORED_PURPLE = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;strokeColor=#9673a6;"
    COLORED_YELLOW = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;strokeColor=#d6b656;"
    COLORED_GRAY = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;strokeColor=#666666;"

    # Additional flow styles
    DATA_FLOW = "endArrow=classic;html=1;dashed=1;strokeColor=#6c8ebf;"
    CONTROL_FLOW = "endArrow=classic;html=1;strokeColor=#b85450;strokeWidth=2;"
    ASYNC = "endArrow=open;endFill=0;html=1;dashed=1;"
    SYNC = "endArrow=block;endFill=1;html=1;"


# ---------------------------------------------------------------------------
# Color themes
# ---------------------------------------------------------------------------

@dataclass
class ColorTheme:
    """A named color palette for consistent diagram styling."""
    fill: str
    stroke: str
    font: str
    gradient: str = ""

    def apply(self, builder: StyleBuilder) -> StyleBuilder:
        builder.fill_color(self.fill)
        builder.stroke_color(self.stroke)
        builder.font_color(self.font)
        if self.gradient:
            builder.gradient(self.gradient)
        return builder


# ---------------------------------------------------------------------------
# Connection point presets (port positions relative to shape 0..1)
# ---------------------------------------------------------------------------

class Port:
    """Named connection point positions (exitX/exitY or entryX/entryY).

    Values are (x, y) tuples where 0,0 = top-left, 1,1 = bottom-right.
    Use these to force edges to connect at specific positions on shapes.
    """
    TOP = (0.5, 0)
    BOTTOM = (0.5, 1)
    LEFT = (0, 0.5)
    RIGHT = (1, 0.5)
    TOP_LEFT = (0, 0)
    TOP_RIGHT = (1, 0)
    BOTTOM_LEFT = (0, 1)
    BOTTOM_RIGHT = (1, 1)
    # Thirds for better distribution on larger shapes
    TOP_LEFT_THIRD = (0.25, 0)
    TOP_RIGHT_THIRD = (0.75, 0)
    BOTTOM_LEFT_THIRD = (0.25, 1)
    BOTTOM_RIGHT_THIRD = (0.75, 1)
    LEFT_TOP_THIRD = (0, 0.25)
    LEFT_BOTTOM_THIRD = (0, 0.75)
    RIGHT_TOP_THIRD = (1, 0.25)
    RIGHT_BOTTOM_THIRD = (1, 0.75)


class Themes:
    """Pre-built color themes matching draw.io palettes."""
    BLUE = ColorTheme(fill="#dae8fc", stroke="#6c8ebf", font="#000000")
    GREEN = ColorTheme(fill="#d5e8d4", stroke="#82b366", font="#000000")
    YELLOW = ColorTheme(fill="#fff2cc", stroke="#d6b656", font="#000000")
    ORANGE = ColorTheme(fill="#ffe6cc", stroke="#d79b00", font="#000000")
    RED = ColorTheme(fill="#f8cecc", stroke="#b85450", font="#000000")
    PURPLE = ColorTheme(fill="#e1d5e7", stroke="#9673a6", font="#000000")
    GRAY = ColorTheme(fill="#f5f5f5", stroke="#666666", font="#333333")
    PINK = ColorTheme(fill="#e6d0de", stroke="#996185", font="#000000")
    TURQUOISE = ColorTheme(fill="#d5e8d4", stroke="#6a9153", font="#000000")
    TEAL = ColorTheme(fill="#d5e8d4", stroke="#6a9153", font="#000000")
    DARK_BLUE = ColorTheme(fill="#1ba1e2", stroke="#006eaf", font="#ffffff")
    DARK_GREEN = ColorTheme(fill="#008a00", stroke="#005700", font="#ffffff")
    DARK_RED = ColorTheme(fill="#a20025", stroke="#6F0000", font="#ffffff")
    DARK_ORANGE = ColorTheme(fill="#e3641e", stroke="#b0401e", font="#ffffff")
    DARK_PURPLE = ColorTheme(fill="#6f3b80", stroke="#4d2b5c", font="#ffffff")
    DARK = ColorTheme(fill="#333333", stroke="#000000", font="#ffffff")
    WHITE = ColorTheme(fill="#ffffff", stroke="#000000", font="#000000")
    # C4 model themes
    C4_BLUE = ColorTheme(fill="#438DD5", stroke="#3C7FC0", font="#ffffff")
    C4_LIGHT_BLUE = ColorTheme(fill="#23A2D9", stroke="#0E7FAD", font="#ffffff")
    C4_SKY = ColorTheme(fill="#85BBF0", stroke="#6FA8DC", font="#000000")
    C4_GRAY = ColorTheme(fill="#999999", stroke="#777777", font="#ffffff")
