"""JSON output helpers: undefined metrics are written as null, never as NaN/Infinity (which are not valid JSON)."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np


def clean(obj: Any) -> Any:
    """Recursively convert numpy scalars/arrays to Python and non-finite floats to None."""
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return clean(obj.tolist())
    if isinstance(obj, (np.floating, float)):
        return None if not math.isfinite(float(obj)) else float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def dumps(obj: Any, indent: int | None = 1) -> str:
    return json.dumps(clean(obj), indent=indent, allow_nan=False)


def dump_json(path: Path, obj: Any) -> None:
    Path(path).write_text(dumps(obj), encoding="utf-8")
