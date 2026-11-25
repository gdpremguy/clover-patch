import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path

from arcade_modes import HARD_GOALS, MODES
from number_display import format_count
from yard import CROP_KEYS, LEGACY_HYBRIDS, MOONLACE_VISITS, RARE_SEEDS, SUN_CROWN_HARVESTS, ZONES, Yard


SAVE_FILE = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "CloverPatch" / "garden.json"
STREAK_LENGTH = 10
MAX_LEVEL = 200
POT_COUNT = 3
OFFLINE_LIMIT = 8 * 60 * 60
VISIT_TIME = 10
TICKET_COST = 10
CLOVER_EXCHANGE = 40
GAMES = {
    "petals": "Petal Catch", "fireflies": "Firefly Trail", "fishing": "Pond Fishing",
    "hopping": "Mushroom Hop", "pop": "Clover Pop",
}

UPGRADES = (
    ("Hand Trowel", "+1 per pick", 10),
    ("Bee Box", "+1 per second", 30),
    ("Lucky Charm", "+5 every 10 picks", 45),
    ("Watering Can", "+20% growth speed", 85),
    ("Compost Bin", "+20% flower yield", 115),
)


@dataclass(frozen=True)
class Style:
    name: str
    price: int
    sky: str
    glow: str
    hills: tuple
    shadow: str
    outline: str
    leaves: tuple
    shine: str
    currency: str = "clover"


STYLES = {
    "meadow": Style("Meadow", 0, "#f5e2bc", "#fbd89a", ("#d6dfb4", "#c7d5a3"),
                    "#acbd8a", "#41634a", ("#73965c", "#6e9057", "#83a66d"), "#d9ebbc"),
    "strawberry": Style("Strawberry", 25, "#f4cfc3", "#ffebbc", ("#e9b8ae", "#dcb4a2"),
                        "#c69686", "#873e53", ("#c9657c", "#bd536b", "#da8193"), "#ffd8cf"),
    "moonlight": Style("Moonlight", 90, "#2c304d", "#fcdfad", ("#494969", "#5a5378"),
                       "#3f3a5d", "#43365d", ("#8e80bb", "#a28dce", "#b5a1d7"), "#f0d8fc"),
    "maple": Style("Maple Hollow", 180, "#f6c895", "#ffe4a0", ("#d4a771", "#bf8559"),
                   "#a66d4f", "#784935", ("#ca7544", "#bc6247", "#dd9850"), "#ffe4a1"),
    "pond": Style("Rain Pond", 260, "#c4dcda", "#e7f0df", ("#a9c7b4", "#8ab4ac"),
                  "#6b9d96", "#335e62", ("#5b9c8f", "#5eada4", "#82c1ab"), "#e0f5e7"),
    "lantern": Style("Lantern Grove", 30, "#3e3249", "#f6b976", ("#66516a", "#524758"),
                     "#463849", "#704357", ("#af647d", "#c77983", "#e79788"), "#ffe8a4", "tickets"),
    "aurora": Style("Aurora Garden", 0, "#263953", "#d4f2de", ("#426769", "#394f64"),
                    "#293f53", "#345c64", ("#79c3aa", "#84b5db", "#bd9cdc"), "#e5fbe6", "discovery"),
}


@dataclass(frozen=True)
class Seed:
    price: int
    seconds: int
    reward: int


SEEDS = {
    "daisy": Seed(8, 16, 20),
    "tulip": Seed(24, 32, 62),
    "lavender": Seed(55, 55, 150),
    **{key: Seed(price, seconds, reward) for _, key, _, price, seconds, reward in ZONES.values()},
    "peach": Seed(18, 18, 48),
    "speckle": Seed(22, 22, 58),
    "velvet": Seed(28, 25, 72),
    "sunset": Seed(29, 27, 77),
    "moonbell": Seed(32, 30, 85),
    "mint": Seed(26, 24, 66),
    "sun_crown": Seed(90, 35, 180),
    "moonlace": Seed(105, 38, 215),
    "dewglass": Seed(125, 42, 255),
}
ZONE_SEEDS = {spec[1]: key for key, spec in ZONES.items()}

MILESTONES = {
    "first_picks": ("Getting Started", "picks", 25, 15),
    "first_flowers": ("In Bloom", "flowers", 3, 30),
    "first_visitors": ("Butterfly Friend", "visitors", 2, 35),
    "first_styles": ("A Change of Scenery", "styles", 3, 45),
    "more_picks": ("Green Thumb", "picks", 150, 65),
    "more_flowers": ("Fresh Bouquet", "flowers", 12, 80),
    "all_styles": ("All Seasons", "styles", sum(style.currency == "clover" for style in STYLES.values()), 150),
    "play_date": ("Play Date", "rounds", 5, 50),
}


class Garden:
    def __init__(self, save_file=SAVE_FILE, now=None):
        self.save_file = save_file
        self.clover = 0
        self.levels = [0] * len(UPGRADES)
        self.streak = 0
        self.unlocked = {"meadow"}
        self.style_key = "meadow"
        self.plots = [None] * POT_COUNT
        self.stats = {"picks": 0, "flowers": 0, "visitors": 0, "rounds": 0, "moths": 0}
        self.claimed = set()
        self.tickets = 0
        self.best_scores = dict.fromkeys(GAMES, 0)
        self.mode_scores = {key: dict.fromkeys(MODES, 0) for key in GAMES}
        self.offline_clover = 0
        self.fullscreen = True
        self.dirty = False
        self.bee_seconds = 0
        now = time.time() if now is None else now
        self.yard = Yard(self, now)
        self.load(now)

    def load(self, now):
        try:
            data = json.loads(self.save_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        self.yard.load(data.get("yard"), now)
        if self.yard.estate.moon:
            self.plots.append(None)
        clover = data.get("clover")
        if type(clover) is int and clover >= 0:
            self.clover = clover
        if type(data.get("fullscreen")) is bool:
            self.fullscreen = data["fullscreen"]
        levels = data.get("levels")
        if isinstance(levels, list):
            for index, level in enumerate(levels[:len(UPGRADES)]):
                if type(level) is int and 0 <= level <= MAX_LEVEL:
                    self.levels[index] = level
        unlocked = data.get("unlocked")
        if isinstance(unlocked, list):
            self.unlocked.update(key for key in unlocked if isinstance(key, str) and key in STYLES)
        style = data.get("style")
        if isinstance(style, str) and style in self.unlocked:
            self.style_key = style
        streak = data.get("streak")
        if self.levels[2] and type(streak) is int and 0 <= streak < STREAK_LENGTH:
            self.streak = streak
        plots = data.get("plots")
        if isinstance(plots, list):
            for index, plot in enumerate(plots[:len(self.plots)]):
                if not isinstance(plot, list) or len(plot) not in (3, 4):
                    continue
                ready_at, duration, watered = plot[:3]
                key = plot[3] if len(plot) == 4 else (CROP_KEYS[index] if index < POT_COUNT else None)
                seed = self.seed_spec(key) if isinstance(key, str) else None
                if (seed and type(ready_at) in (int, float) and 0 < ready_at <= now + seed.seconds
                        and type(duration) in (int, float) and 0 < duration <= seed.seconds
                        and type(watered) is bool):
                    self.plots[index] = (ready_at, duration, watered, key)
                    if len(plot) == 3:
                        self.dirty = True
        self.restore_old_plants(now)
        stats = data.get("stats")
        if isinstance(stats, dict):
            for key in self.stats:
                value = stats.get(key)
                if type(value) is int and value >= 0:
                    self.stats[key] = value
        if self.stats["flowers"] >= SUN_CROWN_HARVESTS:
            self.yard.grant_rare_seed("sun_crown")
        if self.stats["moths"] >= MOONLACE_VISITS:
            self.yard.grant_rare_seed("moonlace")
        claimed = data.get("claimed")
        if isinstance(claimed, list):
            self.claimed.update(key for key in claimed if isinstance(key, str) and key in MILESTONES)
        tickets = data.get("tickets")
        if type(tickets) is int and tickets >= 0:
            self.tickets = tickets
        scores = data.get("best_scores")
        if isinstance(scores, dict):
            for key in self.best_scores:
                value = scores.get(key)
                if type(value) is int and value >= 0:
                    self.best_scores[key] = value
                    self.mode_scores[key]["medium"] = value
        mode_scores = data.get("mode_scores")
        if isinstance(mode_scores, dict):
            for key, modes in self.mode_scores.items():
                saved = mode_scores.get(key)
                if isinstance(saved, dict):
                    for mode in MODES:
                        value = saved.get(mode)
                        if type(value) is int and value >= 0:
                            modes[mode] = value
                self.best_scores[key] = max(self.best_scores[key], *modes.values())
        saved_at = data.get("saved_at")
        if self.levels[1] and type(saved_at) in (int, float) and 0 < saved_at < now:
            self.offline_clover = int(min(now - saved_at, OFFLINE_LIMIT)) * self.levels[1]
            self.credit(self.offline_clover)

    def save(self, now=None):
        if not self.dirty:
            return
        data = {"clover": self.clover, "levels": self.levels, "streak": self.streak,
                "unlocked": sorted(self.unlocked), "style": self.style_key, "plots": self.plots,
                "stats": self.stats, "claimed": sorted(self.claimed),
                "tickets": self.tickets, "best_scores": self.best_scores, "mode_scores": self.mode_scores,
                 "yard": self.yard.save(), "fullscreen": self.fullscreen,
                "saved_at": time.time() if now is None else now}
        try:
            self.save_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.save_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(data), encoding="utf-8")
            temporary.replace(self.save_file)
        except OSError:
            return
        self.dirty = False

    def credit(self, amount):
        if amount:
            self.clover += amount
            self.dirty = True

    def spend(self, amount):
        if amount > self.clover:
            return False
        self.credit(-amount)
        return True

    def bee_rate(self, now=None):
        return self.levels[1] + int(bool(self.levels[1]) and now is not None and self.yard.weather(now)[0] == "Sun")

    def advance_bees(self, elapsed, now=None):
        if not self.levels[1]:
            return 0
        seconds, self.bee_seconds = divmod(self.bee_seconds + elapsed, 1)
        payout = int(seconds) * self.bee_rate(now)
        self.credit(payout)
        return payout

    def pick(self):
        amount = 1 + self.levels[0]
        bonus = 0
        if self.levels[2]:
            self.streak = (self.streak + 1) % STREAK_LENGTH
            if not self.streak:
                bonus = self.levels[2] * 5
        self.stats["picks"] += 1
        if self.stats["picks"] % 36 == 0:
            self.yard.discover("rainbow")
            bonus += 9
        self.credit(amount + bonus)
        return amount + bonus, bool(bonus)

    def cost(self, index):
        return UPGRADES[index][2] * 2 ** self.levels[index]

    def buy(self, index):
        if self.levels[index] >= MAX_LEVEL or not self.spend(self.cost(index)):
            return False
        self.levels[index] += 1
        return True

    def choose_style(self, key):
        if self.style_key == key:
            return False
        if key not in self.unlocked:
            style = STYLES[key]
            if style.currency == "tickets":
                if self.tickets < style.price:
                    return False
                self.tickets -= style.price
            elif style.currency == "discovery":
                if not self.yard.aurora_ready():
                    return False
            elif not self.spend(style.price):
                return False
            self.unlocked.add(key)
        self.style_key = key
        self.dirty = True
        return True

    def can_equip(self, key):
        style = STYLES[key]
        if style.currency == "discovery":
            return key != self.style_key and (key in self.unlocked or self.yard.aurora_ready())
        balance = self.tickets if style.currency == "tickets" else self.clover
        return key != self.style_key and (key in self.unlocked or balance >= style.price)

    def impossible_unlocked(self):
        return sum(self.mode_scores[key]["hard"] >= goal for key, goal in HARD_GOALS.items()) >= 2

    def record_round(self, key, score, mode="medium"):
        best = score > self.mode_scores[key][mode]
        self.mode_scores[key][mode] = max(self.mode_scores[key][mode], score)
        self.best_scores[key] = max(self.best_scores[key], score)
        tickets = MODES[mode].tickets(score)
        self.tickets += tickets
        if score > 0:
            self.stats["rounds"] += 1
            self.dirty = True
        return tickets, best

    def exchange_tickets(self):
        if self.tickets < TICKET_COST:
            return 0
        self.tickets -= TICKET_COST
        self.credit(CLOVER_EXCHANGE)
        return CLOVER_EXCHANGE

    def seed_spec(self, key):
        hybrid = self.yard.hybrids.get(key)
        if hybrid is None:
            return SEEDS.get(key)
        traits = hybrid.traits
        return Seed(12 + traits.petals * 2 + traits.layers * 3,
                    12 + traits.length // 7 + traits.layers * 3,
                    26 + traits.petals * 4 + traits.layers * 8)

    def crop_reward(self, key):
        return self.seed_spec(key).reward * (5 + self.levels[4]) // 5

    def crop_duration(self, key):
        return max(1, round(self.seed_spec(key).seconds * 5 / (5 + self.levels[3])))

    def seed_unlocked(self, key):
        return (key in CROP_KEYS or ZONE_SEEDS.get(key) in self.yard.zones
                or ((key in LEGACY_HYBRIDS or key in self.yard.hybrids or key in RARE_SEEDS) and key in self.yard.stickers))

    def seed_options(self):
        # Bagged seeds come first, so a new hybrid or a snail gift is easy to find.
        favorites = self.yard.estate.favorites
        keys = sorted(self.yard.flower_keys(), key=lambda key: key not in favorites)
        yield from (key for key in keys if self.yard.seeds.get(key, 0))
        yield from (key for key in keys if not self.yard.seeds.get(key, 0) and self.seed_unlocked(key))

    def plant(self, index, key, now):
        seed = self.seed_spec(key)
        if self.plots[index] is not None or seed is None:
            return False
        if not self.yard.take_seed(key) and (not self.seed_unlocked(key) or not self.spend(seed.price)):
            return False
        duration = self.crop_duration(key)
        self.plots[index] = (now + duration, duration, False, key)
        self.apply_weather(now)
        return True

    def restore_old_plants(self, now):
        # Older saves had separate pots for expansion plants. Move them home,
        # leaving any overflow queued until a pot is harvested.
        for index, planted in enumerate(self.plots):
            if not self.yard.pending_plants:
                break
            if planted is None:
                zone = next(iter(self.yard.pending_plants))
                key = ZONES[zone][1]
                duration = SEEDS[key].seconds
                ready_at = min(self.yard.pending_plants.pop(zone), now + duration)
                self.plots[index] = (ready_at, duration, False, key)
                self.dirty = True

    def crop_progress(self, index, now):
        planted = self.plots[index]
        if planted is None:
            return 0
        return min(1, max(0, 1 - (planted[0] - now) / planted[1]))

    def crop_status(self, index, now):
        planted = self.plots[index]
        if planted is None:
            return "Empty pot", "Choose seed", True
        ready_at, _, watered, key = planted
        name = self.yard.flower_info(key)[0]
        remaining = max(0, math.ceil(ready_at - now))
        if remaining == 0:
            return f"{name} · Ready", f"Pick +{format_count(self.crop_reward(key))}", True
        return f"{name} · {remaining}s left", "Growing" if watered else "Water", not watered

    def tend(self, index, now):
        planted = self.plots[index]
        if planted is None:
            return None
        ready_at, duration, watered, key = planted
        if ready_at <= now:
            reward = self.crop_reward(key)
            self.credit(reward)
            self.stats["flowers"] += 1
            self.yard.collect_flower(key)
            if self.stats["flowers"] >= SUN_CROWN_HARVESTS:
                self.yard.grant_rare_seed("sun_crown")
            self.plots[index] = None
            if self.style_key == "aurora" and key in self.yard.hybrids:
                self.yard.estate.discover_moon()
            self.restore_old_plants(now)
            self.yard.estate.after_harvest(index, key, now)
            return f"+{format_count(reward)}"
        if not watered:
            self.plots[index] = (now + (ready_at - now) * .70, duration, True, key)
            self.dirty = True
            return "Watered"
        return None

    def apply_weather(self, now):
        if self.yard.weather(now)[0] != "Rain":
            return
        for index, planted in enumerate(self.plots):
            if planted is not None:
                ready, duration, watered, key = planted
                if not watered and now < ready:
                    self.plots[index] = (now + (ready - now) * .70, duration, True, key)
                    self.dirty = True

    def milestone_value(self, unit):
        return len(self.unlocked) if unit == "styles" else self.stats[unit]

    def claim(self, key):
        _, unit, target, reward = MILESTONES[key]
        if key in self.claimed or self.milestone_value(unit) < target:
            return 0
        self.claimed.add(key)
        self.credit(reward)
        return reward

    def greet_visitor(self, kind="butterfly"):
        reward = 10 + sum(self.levels) * 2
        self.stats["visitors"] += 1
        self.yard.discover(kind)
        if kind == "moth":
            self.stats["moths"] += 1
            if self.stats["moths"] >= MOONLACE_VISITS:
                self.yard.grant_rare_seed("moonlace")
        self.credit(reward)
        return reward
