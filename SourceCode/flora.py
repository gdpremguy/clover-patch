"""Procedural traits for Clover Patch's fictional flowers."""

import random
from dataclasses import asdict, dataclass


PATTERNS = ("plain", "veined", "speckled", "tipped")


@dataclass(frozen=True)
class Traits:
    color: tuple[int, int, int]
    center: tuple[int, int, int]
    petals: int
    layers: int
    length: int
    width: int
    point: int
    pattern: str


@dataclass(frozen=True)
class Hybrid:
    name: str
    traits: Traits

    def save(self):
        return {"name": self.name, "traits": asdict(self.traits)}

    @classmethod
    def read(cls, data):
        if not isinstance(data, dict) or not isinstance(data.get("traits"), dict):
            return None
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            return None
        raw = data["traits"]
        fields = {}
        for key in ("color", "center"):
            rgb = raw.get(key)
            if not isinstance(rgb, (list, tuple)) or len(rgb) != 3 or not all(type(v) is int and 0 <= v <= 255 for v in rgb):
                return None
            fields[key] = tuple(rgb)
        for key, low, high in (
            ("petals", 3, 16), ("layers", 1, 3), ("length", 45, 100), ("width", 16, 70), ("point", 0, 100),
        ):
            value = raw.get(key)
            if type(value) is not int or not low <= value <= high:
                return None
            fields[key] = value
        pattern = raw.get("pattern")
        if pattern not in PATTERNS:
            return None
        return cls(name[:24], Traits(**fields, pattern=pattern))


def traits_for_stock(key, hex_color):
    colors = {
        "daisy": (8, 1, 81, 30, 18, "plain"),
        "tulip": (4, 2, 72, 60, 35, "veined"),
        "lavender": (5, 2, 53, 23, 25, "veined"),
        "mushroom": (3, 1, 66, 70, 12, "speckled"),
        "orchid": (5, 2, 87, 49, 60, "veined"),
        "lily": (8, 2, 91, 33, 91, "tipped"),
        "speckle": (7, 1, 73, 35, 34, "speckled"),
        "velvet": (6, 2, 62, 51, 28, "veined"),
        "moonbell": (6, 2, 80, 34, 46, "tipped"),
        "sun_crown": (11, 2, 87, 31, 65, "tipped"),
        "moonlace": (13, 1, 94, 21, 81, "speckled"),
        "dewglass": (6, 2, 99, 42, 92, "veined"),
    }
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (1, 3, 5))
    return Traits(rgb, (219, 162, 89), *colors.get(key, (6, 1, 76, 44, 33, "plain")))


def cross(left, right, rng=None):
    rng = random if rng is None else rng

    def inherit(lo, hi, minimum, maximum, noise):
        blend = rng.uniform(.16, .84)
        return max(minimum, min(maximum, round(lo * blend + hi * (1 - blend) + rng.uniform(-noise, noise))))

    return Traits(
        tuple(inherit(a, b, 40, 255, 45) for a, b in zip(left.color, right.color)),
        tuple(inherit(a, b, 35, 252, 61) for a, b in zip(left.center, right.center)),
        inherit(left.petals, right.petals, 3, 16, 3.2),
        inherit(left.layers, right.layers, 1, 3, 1.1),
        inherit(left.length, right.length, 45, 100, 26),
        inherit(left.width, right.width, 16, 70, 24),
        inherit(left.point, right.point, 0, 100, 40),
        rng.choice((left.pattern, right.pattern, rng.choice(PATTERNS))),
    )


def suggested_name(traits):
    colors = (
        ("Ivory", (245, 231, 202)), ("Blush", (236, 152, 170)), ("Coral", (224, 115, 107)),
        ("Gold", (225, 177, 104)), ("Mauve", (159, 123, 188)), ("Lilac", (195, 172, 224)),
        ("Mist", (159, 183, 215)), ("Sage", (150, 188, 153)), ("Mulberry", (146, 91, 130)),
    )
    color, _ = min(colors, key=lambda option: sum((a - b)**2 for a, b in zip(option[1], traits.color)))
    form = ("Rosette" if traits.layers > 1 else "Star" if traits.point >= 65 else
            "Daisy" if traits.petals >= 8 else "Bloom")
    return f"{color} {form}"
