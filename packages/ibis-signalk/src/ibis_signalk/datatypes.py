from __future__ import annotations

import ibis.expr.datatypes as dt

# SignalK uses SI units throughout — speeds in m/s, angles in radians, etc.
# Paths not listed here fall back to float64, which covers the vast majority
# of numeric sensor readings.
_PREFIX_TYPES: dict[str, dt.DataType] = {
    "navigation.position": dt.json(),  # {lat, lon} object
}


def path_to_ibis_type(path: str) -> dt.DataType:
    return _PREFIX_TYPES.get(path, dt.float64())


def path_to_column_name(path: str) -> str:
    """navigation.speedOverGround -> navigation__speedOverGround"""
    return path.replace(".", "__")


def column_name_to_path(col: str) -> str:
    return col.replace("__", ".")
