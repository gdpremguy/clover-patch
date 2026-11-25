import math
import re
from collections import Counter
from uuid import uuid4

from flora import Hybrid, cross, suggested_name, traits_for_stock
from yard_extras import Estate


FLOWERS = {
    "daisy": ("Daisies", "#fff1ca"), "tulip": ("Tulips", "#ed9c9c"),
    "lavender": ("Lavender", "#b69cd8"), "peach": ("Peach Daisy", "#f4ac79"),
    "speckle": ("Speckled Aster", "#aa9bd6"), "velvet": ("Velvet Bells", "#be739e"),
    "mushroom": ("Button Mushrooms", "#d88b74"), "orchid": ("Glasshouse Orchids", "#ee97bc"),
    "lily": ("Pond Lilies", "#f5bad3"),
    "sunset": ("Sunset Poppy", "#ed9271"), "moonbell": ("Moonbell", "#a2b8df"),
    "mint": ("Mint Blossom", "#9dcaa4"),
    "sun_crown": ("Sun Crown", "#efbb63"),
    "moonlace": ("Moonlace", "#bfb2ed"),
    "dewglass": ("Dewglass", "#8ad6c1"),
}
CROP_KEYS = ("daisy", "tulip", "lavender")
LEGACY_HYBRIDS = ("peach", "speckle", "velvet", "sunset", "moonbell", "mint")
SUN_CROWN_HARVESTS = 12
MOONLACE_VISITS = 4
RARE_SEEDS = {
    "sun_crown": f"Harvest {SUN_CROWN_HARVESTS} plants",
    "moonlace": f"Greet {MOONLACE_VISITS} lantern moths in the fog",
    "dewglass": "Clear Mushroom Hop on Hard",
}
PEARL_HINT = "Land 3 perfect casts in one Hard fishing round"
ZONES = {
    "shade": ("Mushroom Nook", "mushroom", 110, 10, 23, 55),
    "glass": ("Greenhouse", "orchid", 190, 18, 35, 85),
    "pond": ("Lily Pond", "lily", 150, 15, 30, 70),
}
DECOR = {
    "print": ("Pressed Flower Print", "wall", 4),
    "flag": ("Star Garland", "wall", 7),
    "mushroom": ("Felt Mushroom", "shelf", 5),
    "cup": ("Golden Cup", "shelf", 12),
    "rug": ("Patchwork Rug", "floor", 8),
}
HATS = {"leaf": ("Leaf Hat", 4), "bow": ("Pink Bow", 6)}
WEATHER = {
    "Sun": "Bee Boxes earn an extra clover per second.",
    "Rain": "Rain waters planted flower pots for you.",
    "Fog": "Lantern moths visit while it’s foggy.",
}
WEATHER_SECONDS = 70
SNAIL_SECONDS = 45
STICKERS = {
    **{key: (name, "Harvest one", color) for key, (name, color) in FLOWERS.items()},
    "butterfly": ("Butterfly", "Click a daytime visitor", "#f3a8c5"),
    "moth": ("Lantern Moth", "Watch for a visitor in the fog", "#f4da9e"),
    "rainbow": ("Rainbow Clover", "Look closely on every 36th pick", "#a5c98c"),
    "snail": ("Garden Snail", "Adopt a little helper", "#c99a76"),
    "fish": ("Sunfish", "Catch a fish at the pond", "#e3ad6d"),
    "button": ("Lost Button", "Try fishing at the edge of the bite zone", "#aeb7d5"),
    "lily_seed": ("Lucky Lily Seed", "Make a perfect catch at the pond", "#bbc987"),
    "silver_pearl": ("Silver Pearl", PEARL_HINT, "#d2d7ed"),
}
ORDERS = (
    ("Juniper the Rabbit", {"daisy": 2, "tulip": 1}, 75),
    ("Bramble the Fox", {"tulip": 2, "lavender": 1}, 130),
    ("Hazel the Mouse", {"daisy": 2, "lavender": 1}, 100),
    ("Clover the Deer", {"lavender": 2, "tulip": 2}, 190),
    ("Pip the Squirrel", {"daisy": 3}, 60),
    ("Fern the Badger", {"daisy": 1, "tulip": 1, "lavender": 1}, 110),
)


class Yard:
    def __init__(self, garden, now):
        self.garden = garden
        self.weather_origin = now
        self.stickers = set()
        self.sticker_claims = 0
        self.flowers = {}
        self.hybrids = {}
        self.seeds = {}
        self.rare_seeds_found = set()
        self.pending_plants = {}
        self.zones = set()
        self.decor = set()
        self.room = {}
        self.snail = ""
        self.snail_due = 0
        self.snail_gifts = 0
        self.hats = set()
        self.hat = ""
        self.market_day = -1
        self.orders_filled = set()
        self.bouquets = []
        self.estate = Estate(self)

    def changed(self):
        self.garden.dirty = True

    def load(self, data, now):
        if not isinstance(data, dict):
            return

        def integer(key, default=0):
            value = data.get(key)
            return value if type(value) is int and value >= 0 else default

        def number(value, default=0):
            return value if type(value) in (int, float) and 0 <= value < 10**12 else default

        def known(key, choices):
            values = data.get(key)
            return {v for v in values if isinstance(v, str) and v in choices} if isinstance(values, list) else set()

        saved_hybrids = data.get("hybrids")
        if isinstance(saved_hybrids, dict):
            for key, value in saved_hybrids.items():
                hybrid = Hybrid.read(value)
                if hybrid is not None and re.fullmatch(r"h_[0-9a-f]{32}", key):
                    self.hybrids[key] = hybrid

        def amounts(key):
            table = data.get(key)
            return {k: v for k, v in table.items() if self.is_flower(k) and type(v) is int and v > 0} if isinstance(table, dict) else {}

        self.weather_origin = min(now, number(data.get("weather_origin"), now))
        self.flowers = amounts("flowers")
        self.seeds = amounts("seeds")
        self.stickers = known("stickers", STICKERS.keys() | self.hybrids.keys()) | set(self.flowers)
        self.rare_seeds_found = known("rare_seeds_found", RARE_SEEDS) | (RARE_SEEDS.keys() & (self.stickers | self.seeds.keys()))
        self.sticker_claims = integer("sticker_claims")
        self.zones = known("zones", ZONES)
        self.decor = known("decor", DECOR)
        self.hats = known("hats", HATS)
        self.snail = data.get("snail", "")[:18] if isinstance(data.get("snail"), str) else ""
        self.snail_due = number(data.get("snail_due"))
        self.snail_gifts = integer("snail_gifts")
        hat = data.get("hat")
        self.hat = hat if isinstance(hat, str) and hat in self.hats else ""
        crossing = data.get("crossing")
        if (isinstance(crossing, list) and len(crossing) == 2 and isinstance(crossing[0], str)
                and crossing[0] in LEGACY_HYBRIDS and number(crossing[1])):
            self.give_seed(crossing[0])
        plots = data.get("zone_plots")
        if isinstance(plots, dict):
            self.pending_plants = {k: v for k, v in plots.items() if k in self.zones and number(v)}
        room = data.get("room")
        if isinstance(room, dict):
            self.room = {k: v for k, v in room.items() if isinstance(v, str) and v in self.decor and DECOR[v][1] == k}
        self.market_day = integer("market_day", -1)
        orders = data.get("orders_filled")
        if isinstance(orders, list):
            self.orders_filled = {i for i in orders if type(i) is int and 0 <= i < len(ORDERS)}
        gallery = data.get("bouquets")
        if isinstance(gallery, list):
            self.bouquets = [tuple(v) for v in gallery[:12] if isinstance(v, list) and len(v) == 3
                             and all(isinstance(k, str) and (self.is_flower(k) or not k) for k in v) and any(v)]
        self.estate.load(data.get("estate"))

    def save(self):
        return {
            "weather_origin": self.weather_origin, "flowers": self.flowers, "seeds": self.seeds,
            "hybrids": {key: value.save() for key, value in self.hybrids.items()},
            "rare_seeds_found": sorted(self.rare_seeds_found),
            "stickers": sorted(self.stickers), "sticker_claims": self.sticker_claims,
            "zones": sorted(self.zones), "zone_plots": self.pending_plants,
            "decor": sorted(self.decor), "room": self.room, "hat": self.hat, "hats": sorted(self.hats),
            "snail": self.snail, "snail_due": self.snail_due, "snail_gifts": self.snail_gifts,
            "market_day": self.market_day, "orders_filled": sorted(self.orders_filled), "bouquets": self.bouquets,
            "estate": self.estate.save(),
        }

    def weather(self, now):
        elapsed = max(0, now - self.weather_origin)
        cycle, remaining = divmod(elapsed, WEATHER_SECONDS)
        return tuple(WEATHER)[int(cycle) % len(WEATHER)], math.ceil(WEATHER_SECONDS - remaining)

    def discover(self, key):
        if key not in self.stickers:
            self.stickers.add(key)
            self.changed()

    def collect_flower(self, key):
        self.flowers[key] = self.flowers.get(key, 0) + 1
        self.discover(key)
        self.changed()

    def take_seed(self, key):
        amount = self.seeds.get(key, 0)
        if amount < 1:
            return False
        if amount == 1:
            del self.seeds[key]
        else:
            self.seeds[key] -= 1
        self.changed()
        return True

    def give_seed(self, key):
        self.seeds[key] = self.seeds.get(key, 0) + 1
        self.changed()

    def grant_rare_seed(self, key):
        if key in self.rare_seeds_found:
            return False
        self.rare_seeds_found.add(key)
        self.give_seed(key)
        return True

    def aurora_ready(self):
        return RARE_SEEDS.keys() <= self.stickers

    def rare_finds(self):
        finds = set(self.rare_seeds_found)
        if "silver_pearl" in self.stickers:
            finds.add("silver_pearl")
        if self.aurora_ready():
            finds.add("aurora")
        if self.estate.moon:
            finds.add("moon_garden")
        return finds

    def have_flowers(self, needs):
        return all(self.flowers.get(key, 0) >= count for key, count in needs.items())

    def use_flowers(self, needs):
        for key, count in needs.items():
            if self.flowers[key] == count:
                del self.flowers[key]
            else:
                self.flowers[key] -= count
        self.changed()

    def is_flower(self, key):
        return key in FLOWERS or key in self.hybrids

    def flower_keys(self):
        yield from FLOWERS
        yield from self.hybrids

    def flower_info(self, key):
        hybrid = self.hybrids.get(key)
        return (hybrid.name, hybrid.traits.color) if hybrid is not None else FLOWERS[key]

    def sticker_entries(self):
        yield from ((key, entry) for key, entry in STICKERS.items()
                    if key not in LEGACY_HYBRIDS or key in self.stickers or key in self.seeds)
        for key, hybrid in self.hybrids.items():
            if key in self.stickers:
                yield key, (hybrid.name, "Harvest one", hybrid.traits.color)

    def can_breed(self, parents):
        return len(parents) == 2 and len(set(parents)) == 2 and self.have_flowers(Counter(parents))

    def preview_hybrid(self, parents, rng=None):
        if not self.can_breed(parents):
            return None
        genes = [self.hybrids[key].traits if key in self.hybrids else traits_for_stock(key, FLOWERS[key][1])
                 for key in sorted(parents)]
        traits = cross(*genes, rng=rng)
        return Hybrid(suggested_name(traits), traits)

    def breed(self, parents, preview):
        if not isinstance(preview, Hybrid) or not self.can_breed(parents):
            return None
        used = {self.flower_info(key)[0].casefold() for key in self.flower_keys()}
        name = preview.name
        index = 2
        while name.casefold() in used:
            suffix = f" {index}"
            name = preview.name[:24 - len(suffix)].rstrip() + suffix
            index += 1
        key = f"h_{uuid4().hex}"
        self.hybrids[key] = Hybrid(name, preview.traits)
        self.estate.lineage[key] = tuple(parents)
        self.use_flowers(Counter(parents))
        self.give_seed(key)
        return key

    def unlock_zone(self, key):
        name, _, unlock, *_ = ZONES[key]
        if key in self.zones or not self.garden.spend(unlock):
            return None
        self.zones.add(key)
        self.changed()
        return f"{name} unlocked!"

    def buy_decor(self, key):
        name, slot, price = DECOR[key]
        if key not in self.decor:
            if self.garden.tickets < price:
                return None
            self.garden.tickets -= price
            self.decor.add(key)
        if self.room.get(slot) == key:
            del self.room[slot]
            status = "Put away"
        else:
            self.room[slot] = key
            status = f"Placed {name}"
        self.changed()
        return status

    def set_snail(self, name, now):
        name = "".join(c for c in name.strip() if c.isprintable())[:18]
        if not name:
            return False
        if not self.snail:
            self.snail_due = now + SNAIL_SECONDS
            self.discover("snail")
        self.snail = name
        self.changed()
        return True

    def gift(self, now):
        if not self.snail or now < self.snail_due:
            return None
        key = CROP_KEYS[self.snail_gifts % len(CROP_KEYS)]
        self.snail_gifts += 1
        self.snail_due = now + SNAIL_SECONDS
        self.give_seed(key)
        if self.snail_gifts % 2 == 0:
            return "Found a seed and a treasure map!"
        return f"Found a {FLOWERS[key][0].lower()} seed"

    def buy_hat(self, key):
        _, price = HATS[key]
        if not self.snail or (key not in self.hats and self.garden.tickets < price):
            return False
        if key not in self.hats:
            self.garden.tickets -= price
            self.hats.add(key)
        self.hat = "" if self.hat == key else key
        self.changed()
        return True

    def active_orders(self, now):
        day = int(now // 86400)
        return day, [(day * 3 + index) % len(ORDERS) for index in range(3)]

    def sell_order(self, index, now):
        day, today = self.active_orders(now)
        _, needs, reward = ORDERS[index]
        if index not in today or (day == self.market_day and index in self.orders_filled) or not self.have_flowers(needs):
            return 0
        if day != self.market_day:
            self.market_day = day
            self.orders_filled.clear()
        self.orders_filled.add(index)
        self.use_flowers(needs)
        self.garden.credit(reward)
        return reward

    def save_bouquet(self, flowers):
        entry = tuple(flowers)
        if not any(entry) or entry in self.bouquets or any(key and key not in self.stickers for key in entry):
            return False
        self.bouquets = [entry, *self.bouquets[:11]]
        self.changed()
        return True

    def sticker_reward(self):
        return 45 * (self.sticker_claims + 1) if len(self.stickers) >= 4 * (self.sticker_claims + 1) else 0

    def claim_stickers(self):
        reward = self.sticker_reward()
        if reward:
            self.sticker_claims += 1
            self.garden.credit(reward)
        return reward

    def catch(self, kind):
        self.discover(kind)
        if kind == "lily_seed":
            self.give_seed("lily")
        elif kind == "fish":
            self.garden.credit(8)
