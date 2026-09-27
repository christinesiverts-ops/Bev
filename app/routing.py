"""Route ordering for store visits.

Straight-line (haversine) distances, nearest-neighbour start, then 2-opt improvement.
Good for the 5-25 stops a rep covers in a day; drive times are estimates (road factor x avg speed).
"""
import math
from dataclasses import dataclass

from . import config


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _path_len(points, order, start):
    total, prev = 0.0, start
    for i in order:
        if prev is not None:
            total += haversine_km(prev, points[i])
        prev = points[i]
    return total


def optimize(points: list[tuple[float, float]], start: tuple[float, float] | None = None) -> list[int]:
    """Return an order (indices into points) for an open path, starting near `start` if given."""
    n = len(points)
    if n <= 1:
        return list(range(n))
    # nearest neighbour from the start (or from the stop farthest from the centroid)
    if start is None:
        cy, cx = sum(p[0] for p in points) / n, sum(p[1] for p in points) / n
        first = max(range(n), key=lambda i: haversine_km((cy, cx), points[i]))
        order, cur = [first], points[first]
    else:
        order, cur = [], start
    left = set(range(n)) - set(order)
    while left:
        nxt = min(left, key=lambda i: haversine_km(cur, points[i]))
        order.append(nxt)
        left.remove(nxt)
        cur = points[nxt]
    # 2-opt on the open path
    best = _path_len(points, order, start)
    improved = True
    while improved:
        improved = False
        for i in range(0, n - 1):
            for k in range(i + 1, n):
                cand = order[:i] + order[i:k + 1][::-1] + order[k + 1:]
                length = _path_len(points, cand, start)
                if length + 1e-9 < best:
                    order, best, improved = cand, length, True
    return order


@dataclass
class Leg:
    km: float
    minutes: int


def legs(points: list[tuple[float, float]], start: tuple[float, float] | None = None) -> list[Leg]:
    """Estimated road distance and drive time into each stop (first leg is from start, if any)."""
    out, prev = [], start
    for p in points:
        if prev is None:
            out.append(Leg(0.0, 0))
        else:
            km = haversine_km(prev, p) * config.ROAD_FACTOR
            out.append(Leg(round(km, 1), round(km / config.AVG_SPEED_KMH * 60)))
        prev = p
    return out


def summary(leg_list: list[Leg], stops: int) -> dict:
    km = round(sum(l.km for l in leg_list), 1)
    drive = sum(l.minutes for l in leg_list)
    total = drive + stops * config.STOP_MINUTES
    return {"km": km, "miles": round(km * 0.621371, 1), "drive_min": drive, "total_min": total,
            "stop_min": config.STOP_MINUTES}


def google_maps_links(points: list[tuple[float, float]], origin: tuple[float, float] | None = None,
                      chunk: int = 9) -> list[str]:
    """Google Maps directions URLs; split into chunks (the app allows ~9 waypoints per trip)."""
    links, i = [], 0
    pts = list(points)
    cur_origin = origin
    while i < len(pts):
        seg = pts[i:i + chunk + 1]
        dest = seg[-1]
        way = seg[:-1]
        url = "https://www.google.com/maps/dir/?api=1&travelmode=driving"
        if cur_origin:
            url += f"&origin={cur_origin[0]:.6f},{cur_origin[1]:.6f}"
        url += f"&destination={dest[0]:.6f},{dest[1]:.6f}"
        if way:
            url += "&waypoints=" + "%7C".join(f"{p[0]:.6f},{p[1]:.6f}" for p in way)
        links.append(url)
        cur_origin = dest
        i += len(seg)
    return links
