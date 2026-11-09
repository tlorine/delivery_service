"""Point-in-polygon for delivery zones. GeoJSON order is [lon, lat]. Zones are a few km wide, so
planar ray casting is accurate enough; no PostGIS dependency for the MVP."""

from collections.abc import Sequence
from typing import Any

Ring = Sequence[Sequence[float]]


def _in_ring(lon: float, lat: float, ring: Ring) -> bool:
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def polygon_contains(polygon: dict[str, Any], lat: float, lon: float) -> bool:
    if polygon.get("type") != "Polygon":
        raise ValueError("only GeoJSON Polygon is supported")
    rings = polygon["coordinates"]
    if not rings or not _in_ring(lon, lat, rings[0]):
        return False
    return not any(_in_ring(lon, lat, hole) for hole in rings[1:])


def validate_polygon(polygon: dict[str, Any]) -> None:
    if polygon.get("type") != "Polygon" or not isinstance(polygon.get("coordinates"), list):
        raise ValueError("expected a GeoJSON Polygon")
    for ring in polygon["coordinates"]:
        if len(ring) < 4 or ring[0] != ring[-1]:
            raise ValueError("each ring needs >= 4 positions and must be closed")
        for pos in ring:
            lon, lat = pos[0], pos[1]
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise ValueError("coordinates out of range")
