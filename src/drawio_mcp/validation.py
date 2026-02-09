"""
Input validation for draw.io MCP server tool parameters.

Provides reusable validators that produce clear error messages for all
parameters received from Copilot / LLM callers.
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Raised when input validation fails."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


# ---------------------------------------------------------------------------
# Primitive validators
# ---------------------------------------------------------------------------

def validate_non_empty_string(value: Any, field_name: str) -> str:
    """Ensure *value* is a non-empty string after stripping whitespace."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"'{field_name}' must be a non-empty string.")
    return value.strip()


def validate_string(value: Any, field_name: str, *, allow_empty: bool = True) -> str:
    """Ensure *value* is a string (optionally non-empty)."""
    if not isinstance(value, str):
        raise ValidationError(f"'{field_name}' must be a string, got {type(value).__name__}.")
    if not allow_empty and not value.strip():
        raise ValidationError(f"'{field_name}' must not be empty.")
    return value


def validate_color(value: Any, field_name: str, *, allow_none: bool = False) -> str:
    """Validate a CSS-style hex color (#RGB, #RRGGBB, #RRGGBBAA) or 'none'."""
    if allow_none and (value == "none" or value == ""):
        return value
    if not isinstance(value, str):
        raise ValidationError(f"'{field_name}' must be a color string, got {type(value).__name__}.")
    value = value.strip()
    if value == "none" or value == "":
        return value
    if not re.match(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$", value):
        raise ValidationError(
            f"'{field_name}' must be a valid hex color (#RGB, #RRGGBB, or #RRGGBBAA), got '{value}'."
        )
    return value


def validate_number(
    value: Any,
    field_name: str,
    *,
    min_val: float | None = None,
    max_val: float | None = None,
) -> float:
    """Validate a numeric value and optional range."""
    if not isinstance(value, (int, float)):
        raise ValidationError(
            f"'{field_name}' must be a number, got {type(value).__name__}."
        )
    val = float(value)
    if min_val is not None and val < min_val:
        raise ValidationError(
            f"'{field_name}' must be >= {min_val}, got {val}."
        )
    if max_val is not None and val > max_val:
        raise ValidationError(
            f"'{field_name}' must be <= {max_val}, got {val}."
        )
    return val


def validate_int(
    value: Any,
    field_name: str,
    *,
    min_val: int | None = None,
    max_val: int | None = None,
) -> int:
    """Validate an integer value and optional range."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(
            f"'{field_name}' must be an integer, got {type(value).__name__}."
        )
    if min_val is not None and value < min_val:
        raise ValidationError(
            f"'{field_name}' must be >= {min_val}, got {value}."
        )
    if max_val is not None and value > max_val:
        raise ValidationError(
            f"'{field_name}' must be <= {max_val}, got {value}."
        )
    return value


def validate_bool(value: Any, field_name: str) -> bool:
    """Ensure *value* is a boolean."""
    if not isinstance(value, bool):
        raise ValidationError(
            f"'{field_name}' must be a boolean, got {type(value).__name__}."
        )
    return value


def validate_enum(value: Any, field_name: str, allowed: set[str]) -> str:
    """Validate that a string value is one of the allowed choices (case-insensitive)."""
    if not isinstance(value, str):
        raise ValidationError(
            f"'{field_name}' must be a string, got {type(value).__name__}."
        )
    normalized = value.strip().upper()
    if normalized not in {a.upper() for a in allowed}:
        choices = ", ".join(sorted(allowed))
        raise ValidationError(
            f"'{field_name}' must be one of [{choices}], got '{value}'."
        )
    return normalized


def validate_list(value: Any, field_name: str, *, min_length: int = 0) -> list:
    """Ensure *value* is a list with at least *min_length* items."""
    if not isinstance(value, list):
        raise ValidationError(
            f"'{field_name}' must be a list, got {type(value).__name__}."
        )
    if len(value) < min_length:
        raise ValidationError(
            f"'{field_name}' must have at least {min_length} item(s), got {len(value)}."
        )
    return value


def validate_dict(value: Any, field_name: str) -> dict:
    """Ensure *value* is a dict."""
    if not isinstance(value, dict):
        raise ValidationError(
            f"'{field_name}' must be a dict/object, got {type(value).__name__}."
        )
    return value


def validate_file_path(value: Any, field_name: str) -> str:
    """Validate that a file path is a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"'{field_name}' must be a non-empty file path string.")
    return value.strip()


# ---------------------------------------------------------------------------
# Composite / domain validators
# ---------------------------------------------------------------------------

_VALID_DIRECTIONS = {"TB", "BT", "LR", "RL"}
_VALID_ALIGNMENTS = {"LEFT", "CENTER", "RIGHT", "TOP", "MIDDLE", "BOTTOM"}
_VALID_DIST_DIRECTIONS = {"HORIZONTAL", "VERTICAL"}

_DIAGRAM_ACTIONS = {"CREATE", "SAVE", "LOAD", "IMPORT_XML", "LIST", "GET_XML", "ADD_PAGE", "ADD_LAYER"}
_DRAW_ACTIONS = {
    "ADD_VERTICES", "ADD_EDGES", "ADD_GROUP", "UPDATE_CELLS",
    "DELETE_CELLS", "ADD_TITLE", "ADD_LEGEND", "BUILD_DAG", "BUILD_FULL",
}
_STYLE_ACTIONS = {
    "BUILD", "APPLY_THEME", "LIST_VERTEX_PRESETS",
    "LIST_EDGE_PRESETS", "LIST_THEMES",
}
_LAYOUT_ACTIONS = {
    "SUGIYAMA", "TREE", "HORIZONTAL", "VERTICAL", "GRID",
    "FLOWCHART", "SMART_CONNECT", "ALIGN", "DISTRIBUTE",
    "POLISH", "RELAYOUT", "COMPACT", "REROUTE_EDGES",
    "RESOLVE_OVERLAPS", "FIX_LABELS", "OPTIMIZE_CONNECTIONS",
    "RESIZE_CONTAINER",
}
_INSPECT_ACTIONS = {"CELLS", "OVERLAPS", "PORTS", "INFO"}

_PAGE_FORMATS = {
    "A4_PORTRAIT", "A4_LANDSCAPE", "LETTER_PORTRAIT",
    "LETTER_LANDSCAPE", "A3_PORTRAIT", "A3_LANDSCAPE", "INFINITE",
}

_FLOWCHART_TYPES = {
    "PROCESS", "DECISION", "TERMINATOR", "DATA",
    "PREDEFINED", "MANUAL_INPUT", "PREPARATION",
    "DELAY", "DISPLAY", "STORED_DATA",
}


def validate_action(value: Any, tool_name: str, allowed: set[str]) -> str:
    """Validate the action parameter for a tool."""
    if not isinstance(value, str) or not value.strip():
        choices = ", ".join(sorted(a.lower() for a in allowed))
        raise ValidationError(
            f"'{tool_name}' requires an 'action' parameter. Valid actions: {choices}."
        )
    normalized = value.strip().upper()
    if normalized not in allowed:
        choices = ", ".join(sorted(a.lower() for a in allowed))
        raise ValidationError(
            f"Unknown {tool_name} action '{value}'. Valid actions: {choices}."
        )
    return value.strip().lower()


def validate_page_index(value: Any, num_pages: int) -> int:
    """Validate a page index is within range."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(
            f"'page_index' must be an integer, got {type(value).__name__}."
        )
    if value < 0 or value >= num_pages:
        raise ValidationError(
            f"'page_index' {value} out of range (0..{num_pages - 1})."
        )
    return value


def validate_direction(value: Any) -> str:
    """Validate a layout direction (TB, BT, LR, RL)."""
    return validate_enum(value, "direction", _VALID_DIRECTIONS)


def validate_alignment(value: Any) -> str:
    """Validate an alignment value."""
    return validate_enum(value, "alignment", _VALID_ALIGNMENTS)


def validate_page_format(value: Any) -> str:
    """Validate a page format name."""
    return validate_enum(value, "page_format", _PAGE_FORMATS)


# ---------------------------------------------------------------------------
# Vertex / edge / update dict validators
# ---------------------------------------------------------------------------

def validate_vertex_dict(v: dict, index: int) -> None:
    """Validate a single vertex dict from the vertices list."""
    if not isinstance(v, dict):
        raise ValidationError(f"Vertex at index {index} must be a dict/object.")
    if "label" not in v:
        raise ValidationError(f"Vertex at index {index} missing required key 'label'.")
    if not isinstance(v["label"], str):
        raise ValidationError(f"Vertex at index {index}: 'label' must be a string.")
    if "x" not in v:
        raise ValidationError(f"Vertex at index {index} missing required key 'x'.")
    if "y" not in v:
        raise ValidationError(f"Vertex at index {index} missing required key 'y'.")
    if not isinstance(v["x"], (int, float)):
        raise ValidationError(f"Vertex at index {index}: 'x' must be a number.")
    if not isinstance(v["y"], (int, float)):
        raise ValidationError(f"Vertex at index {index}: 'y' must be a number.")
    if "width" in v and not isinstance(v["width"], (int, float)):
        raise ValidationError(f"Vertex at index {index}: 'width' must be a number.")
    if "width" in v and v["width"] <= 0:
        raise ValidationError(f"Vertex at index {index}: 'width' must be > 0.")
    if "height" in v and not isinstance(v["height"], (int, float)):
        raise ValidationError(f"Vertex at index {index}: 'height' must be a number.")
    if "height" in v and v["height"] <= 0:
        raise ValidationError(f"Vertex at index {index}: 'height' must be > 0.")
    if "style_preset" in v and not isinstance(v["style_preset"], str):
        raise ValidationError(f"Vertex at index {index}: 'style_preset' must be a string.")
    if "custom_style" in v and not isinstance(v["custom_style"], str):
        raise ValidationError(f"Vertex at index {index}: 'custom_style' must be a string.")
    if "parent_id" in v and not isinstance(v["parent_id"], str):
        raise ValidationError(f"Vertex at index {index}: 'parent_id' must be a string.")
    if "cell_id" in v and not isinstance(v["cell_id"], str):
        raise ValidationError(f"Vertex at index {index}: 'cell_id' must be a string.")


def validate_edge_dict(e: dict, index: int) -> None:
    """Validate a single edge dict from the edges list (add_edges / build_full)."""
    if not isinstance(e, dict):
        raise ValidationError(f"Edge at index {index} must be a dict/object.")
    if "source_id" not in e:
        raise ValidationError(f"Edge at index {index} missing required key 'source_id'.")
    if "target_id" not in e:
        raise ValidationError(f"Edge at index {index} missing required key 'target_id'.")
    if not isinstance(e["source_id"], str) or not e["source_id"].strip():
        raise ValidationError(f"Edge at index {index}: 'source_id' must be a non-empty string.")
    if not isinstance(e["target_id"], str) or not e["target_id"].strip():
        raise ValidationError(f"Edge at index {index}: 'target_id' must be a non-empty string.")
    if e["source_id"] == e["target_id"]:
        raise ValidationError(f"Edge at index {index}: 'source_id' and 'target_id' must be different (self-loops not supported).")
    if "label" in e and not isinstance(e["label"], str):
        raise ValidationError(f"Edge at index {index}: 'label' must be a string.")
    if "style_preset" in e and not isinstance(e["style_preset"], str):
        raise ValidationError(f"Edge at index {index}: 'style_preset' must be a string.")
    if "custom_style" in e and not isinstance(e["custom_style"], str):
        raise ValidationError(f"Edge at index {index}: 'custom_style' must be a string.")
    if "exit_port" in e and not isinstance(e["exit_port"], str):
        raise ValidationError(f"Edge at index {index}: 'exit_port' must be a string.")
    if "entry_port" in e and not isinstance(e["entry_port"], str):
        raise ValidationError(f"Edge at index {index}: 'entry_port' must be a string.")
    if "parent_id" in e and not isinstance(e["parent_id"], str):
        raise ValidationError(f"Edge at index {index}: 'parent_id' must be a string.")


def validate_dag_edge_dict(e: dict, index: int) -> None:
    """Validate a single edge dict for build_dag (uses labels, not IDs)."""
    if not isinstance(e, dict):
        raise ValidationError(f"Edge at index {index} must be a dict/object.")
    if "source" not in e:
        raise ValidationError(f"Edge at index {index} missing required key 'source'.")
    if "target" not in e:
        raise ValidationError(f"Edge at index {index} missing required key 'target'.")
    if not isinstance(e["source"], str) or not e["source"].strip():
        raise ValidationError(f"Edge at index {index}: 'source' must be a non-empty string.")
    if not isinstance(e["target"], str) or not e["target"].strip():
        raise ValidationError(f"Edge at index {index}: 'target' must be a non-empty string.")
    if "label" in e and not isinstance(e["label"], str):
        raise ValidationError(f"Edge at index {index}: 'label' must be a string.")


def validate_update_dict(u: dict, index: int) -> None:
    """Validate a single update dict from the updates list."""
    if not isinstance(u, dict):
        raise ValidationError(f"Update at index {index} must be a dict/object.")
    if "cell_id" not in u:
        raise ValidationError(f"Update at index {index} missing required key 'cell_id'.")
    if not isinstance(u["cell_id"], str) or not u["cell_id"].strip():
        raise ValidationError(f"Update at index {index}: 'cell_id' must be a non-empty string.")
    if "label" in u and not isinstance(u["label"], str):
        raise ValidationError(f"Update at index {index}: 'label' must be a string.")
    if "style" in u and not isinstance(u["style"], str):
        raise ValidationError(f"Update at index {index}: 'style' must be a string.")
    if "x" in u and not isinstance(u["x"], (int, float)):
        raise ValidationError(f"Update at index {index}: 'x' must be a number.")
    if "y" in u and not isinstance(u["y"], (int, float)):
        raise ValidationError(f"Update at index {index}: 'y' must be a number.")
    if "width" in u and not isinstance(u["width"], (int, float)):
        raise ValidationError(f"Update at index {index}: 'width' must be a number.")
    if "width" in u and u["width"] <= 0:
        raise ValidationError(f"Update at index {index}: 'width' must be > 0.")
    if "height" in u and not isinstance(u["height"], (int, float)):
        raise ValidationError(f"Update at index {index}: 'height' must be a number.")
    if "height" in u and u["height"] <= 0:
        raise ValidationError(f"Update at index {index}: 'height' must be > 0.")


def validate_legend_entry(entry: dict, index: int) -> None:
    """Validate a single legend entry dict."""
    if not isinstance(entry, dict):
        raise ValidationError(f"Legend entry at index {index} must be a dict/object.")
    if "label" not in entry:
        raise ValidationError(f"Legend entry at index {index} missing required key 'label'.")
    if not isinstance(entry["label"], str):
        raise ValidationError(f"Legend entry at index {index}: 'label' must be a string.")
    if "fill_color" in entry:
        validate_color(entry["fill_color"], f"legend_entries[{index}].fill_color")
    if "stroke_color" in entry:
        validate_color(entry["stroke_color"], f"legend_entries[{index}].stroke_color")


def validate_connection_dict(c: dict, index: int) -> None:
    """Validate a single connection dict for smart_connect / sugiyama."""
    if not isinstance(c, dict):
        raise ValidationError(f"Connection at index {index} must be a dict/object.")
    # Accept both source/target (labels) and source_id/target_id (IDs)
    has_label_keys = "source" in c and "target" in c
    has_id_keys = "source_id" in c and "target_id" in c
    if not has_label_keys and not has_id_keys:
        raise ValidationError(
            f"Connection at index {index} must have either "
            "'source'+'target' or 'source_id'+'target_id'."
        )
    if "label" in c and not isinstance(c["label"], str):
        raise ValidationError(f"Connection at index {index}: 'label' must be a string.")
    if "exit_port" in c and not isinstance(c["exit_port"], str):
        raise ValidationError(f"Connection at index {index}: 'exit_port' must be a string.")
    if "entry_port" in c and not isinstance(c["entry_port"], str):
        raise ValidationError(f"Connection at index {index}: 'entry_port' must be a string.")


def validate_flowchart_step(step: dict, index: int) -> None:
    """Validate a single flowchart step dict."""
    if not isinstance(step, dict):
        raise ValidationError(f"Step at index {index} must be a dict/object.")
    if "label" not in step:
        raise ValidationError(f"Step at index {index} missing required key 'label'.")
    if not isinstance(step["label"], str):
        raise ValidationError(f"Step at index {index}: 'label' must be a string.")
    if "type" in step:
        if not isinstance(step["type"], str):
            raise ValidationError(f"Step at index {index}: 'type' must be a string.")
        step_type = step["type"].upper()
        if step_type not in _FLOWCHART_TYPES:
            choices = ", ".join(sorted(t.lower() for t in _FLOWCHART_TYPES))
            raise ValidationError(
                f"Step at index {index}: unknown type '{step['type']}'. "
                f"Valid types: {choices}."
            )


def validate_node_styles(value: Any) -> dict[str, str]:
    """Validate the node_styles mapping (label -> style preset)."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError(
            f"'node_styles' must be a dict mapping labels to style presets, "
            f"got {type(value).__name__}."
        )
    for k, v in value.items():
        if not isinstance(k, str):
            raise ValidationError(f"'node_styles' keys must be strings, got {type(k).__name__}.")
        if not isinstance(v, str):
            raise ValidationError(
                f"'node_styles' value for '{k}' must be a string, got {type(v).__name__}."
            )
    return value


def validate_adjacency(value: Any) -> dict[str, list[str]]:
    """Validate an adjacency dict (parent -> list of children)."""
    if value is None or (isinstance(value, dict) and len(value) == 0):
        raise ValidationError("'adjacency' must be a non-empty dict.")
    if not isinstance(value, dict):
        raise ValidationError(
            f"'adjacency' must be a dict, got {type(value).__name__}."
        )
    for k, v in value.items():
        if not isinstance(k, str):
            raise ValidationError(f"'adjacency' keys must be strings, got {type(k).__name__}.")
        if not isinstance(v, list):
            raise ValidationError(
                f"'adjacency' value for '{k}' must be a list, got {type(v).__name__}."
            )
        for i, child in enumerate(v):
            if not isinstance(child, str):
                raise ValidationError(
                    f"'adjacency[{k}][{i}]' must be a string, got {type(child).__name__}."
                )
    return value


def validate_extra_dict(value: Any) -> dict[str, str]:
    """Validate the 'extra' style key-value pairs dict."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError(
            f"'extra' must be a dict of string key-value pairs, "
            f"got {type(value).__name__}."
        )
    for k, v in value.items():
        if not isinstance(k, str):
            raise ValidationError(f"'extra' keys must be strings, got {type(k).__name__}.")
        if not isinstance(v, str):
            raise ValidationError(
                f"'extra' value for '{k}' must be a string, got {type(v).__name__}."
            )
    return value


# ---------------------------------------------------------------------------
# Composite tool-level validators
# ---------------------------------------------------------------------------

def validate_positive_number(value: Any, field_name: str) -> float:
    """Validate that a number is positive (> 0)."""
    return validate_number(value, field_name, min_val=0.001)


def validate_non_negative_number(value: Any, field_name: str) -> float:
    """Validate that a number is >= 0."""
    return validate_number(value, field_name, min_val=0)


def validate_spacing(value: Any, field_name: str) -> float:
    """Validate spacing parameters (must be > 0)."""
    return validate_number(value, field_name, min_val=1)


def validate_grid_size(value: Any) -> int:
    """Validate grid size (1..100)."""
    return validate_int(value, "grid_size", min_val=1, max_val=100)


def validate_opacity(value: Any) -> int:
    """Validate opacity (0..100)."""
    return validate_int(value, "opacity", min_val=0, max_val=100)


def validate_font_size(value: Any) -> int:
    """Validate font size (1..200)."""
    return validate_int(value, "font_size", min_val=1, max_val=200)


def validate_columns(value: Any) -> int:
    """Validate grid columns (>= 1)."""
    return validate_int(value, "columns", min_val=1)
