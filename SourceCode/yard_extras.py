from arcade_modes import MODES


COMMISSIONS = {
    "blue": ("Blue Ribbon", "Blue petals and at least 10 petals total", 165, 5),
    "peach": ("Peach Posy", "Warm pink petals in at least two layers", 120, 4),
    "freckles": ("Freckle Club", "Speckled petals with a pointed shape", 140, 5),
}
SHOWPIECES = {
    "stones": ("Stepping Stones", 45, "clover"),
    "lantern": ("Garden Lantern", 6, "tickets"),
    "bed": ("Flowerbed", 70, "clover"),
    "pebble": ("Painted Pebble", 0, "treasure"),
    "bunting": ("Festival Bunting", 5, "festival"),
}
DISPLAY_LIMIT = 48
DISPLAY_BOUNDS = (15, 122, 357, 206)
OLD_DISPLAY_POSITIONS = ((37, 150), (240, 167), (338, 151))
TREASURE_SPOTS = ("flat stone", "paper lantern", "tall fern", "empty shell")
FESTIVAL_TRIALS = {"petals": 12, "pop": 15}
AUTOMATION_PRICE = 220
QUEUE_LIMIT = 3
GHOST_LIMIT = 4000
GHOST_COURSES = {"easy": 4307, "medium": 1459, "hard": 9563, "endless": 7717, "impossible": 2089}


class Estate:
    def __init__(self, yard):
        self.yard = yard
        self.lineage = {}
        self.favorites = set()
        self.commissions = set()
        self.owned_showpieces = set()
        self.displays = []
        self.maps_done = 0
        self.map_step = 0
        self.festival_open = False
        self.festival_marks = set()
        self.festivals_done = 0
        self.automated = False
        self.auto_pots = set()
        self.presets = {}
        self.queues = {}
        self.moon = False
        self.ghosts = {}

    @property
    def garden(self):
        return self.yard.garden

    def load(self, data):
        if not isinstance(data, dict):
            return

        def number(name):
            value = data.get(name)
            return value if type(value) is int and value >= 0 else 0

        def known(name, options):
            values = data.get(name)
            return {v for v in values if isinstance(v, str) and v in options} if isinstance(values, list) else set()

        self.favorites = known("favorites", self.yard.hybrids)
        lineage = data.get("lineage")
        if isinstance(lineage, dict):
            self.lineage = {k: tuple(v) for k, v in lineage.items() if k in self.yard.hybrids
                            and isinstance(v, list) and len(v) == 2
                            and all(isinstance(p, str) and p != k and self.yard.is_flower(p) for p in v)}
        self.commissions = known("commissions", COMMISSIONS)
        self.owned_showpieces = known("owned", SHOWPIECES)
        displays = data.get("displays")
        if not isinstance(displays, list):
            showcase = data.get("showcase")
            displays = [[key, x, y] for key, (x, y) in zip(showcase, OLD_DISPLAY_POSITIONS)] if isinstance(showcase, list) else []
        for item in displays[:DISPLAY_LIMIT]:
            if not isinstance(item, list) or len(item) != 3:
                continue
            key, x, y = item
            if isinstance(key, str) and self.can_display(key) and self.valid_position(x, y):
                self.displays.append((key, x, y))
        self.maps_done = min(number("maps_done"), self.yard.snail_gifts // 2)
        self.map_step = min(number("map_step"), 1) if self.has_map() else 0
        self.festival_open = data.get("festival_open") is True
        self.festival_marks = known("festival_marks", ("game", "bouquet")) if self.festival_open else set()
        self.festivals_done = number("festivals_done")
        self.automated = data.get("automated") is True
        self.moon = data.get("moon") is True
        slots = 4 if self.moon else 3
        autos = data.get("auto_pots")
        if self.automated and isinstance(autos, list):
            self.auto_pots = {i for i in autos if type(i) is int and 0 <= i < slots}
        for field in ("presets", "queues"):
            table = data.get(field)
            target = getattr(self, field)
            if self.automated and isinstance(table, dict):
                for i in range(slots):
                    value = table.get(str(i))
                    if field == "presets" and isinstance(value, str) and self.yard.is_flower(value):
                        target[i] = value
                    if field == "queues" and isinstance(value, list):
                        target[i] = [k for k in value[:QUEUE_LIMIT] if isinstance(k, str) and self.yard.is_flower(k)]
        ghosts = data.get("ghosts")
        if isinstance(ghosts, dict):
            for mode, ghost in ghosts.items():
                if mode not in MODES or not isinstance(ghost, dict) or ghost.get("course") != GHOST_COURSES[mode]:
                    continue
                sample = ghost.get("points")
                duration, score = ghost.get("duration"), ghost.get("score")
                if (not isinstance(sample, list) or not 2 <= len(sample) <= GHOST_LIMIT or type(score) is not int
                        or type(duration) not in (float, int) or not 0 < duration < 10000):
                    continue
                clean = []
                for point in sample:
                    if not isinstance(point, list) or len(point) != 3:
                        break
                    if not all(type(v) in (int, float) and -1e6 <= v <= 1e6 for v in point):
                        break
                    t, x, y = point
                    if clean and (t < clean[-1][0] or x < clean[-1][1]):
                        break
                    clean.append((t, x, y))
                if len(clean) == len(sample):
                    self.ghosts[mode] = {"course": ghost["course"], "score": score, "duration": duration, "points": clean}

    def save(self):
        return {
            "lineage": self.lineage, "favorites": sorted(self.favorites), "commissions": sorted(self.commissions),
            "owned": sorted(self.owned_showpieces), "displays": self.displays, "maps_done": self.maps_done, "map_step": self.map_step,
            "festival_open": self.festival_open, "festival_marks": sorted(self.festival_marks), "festivals_done": self.festivals_done,
            "automated": self.automated, "auto_pots": sorted(self.auto_pots), "presets": self.presets, "queues": self.queues,
            "moon": self.moon, "ghosts": self.ghosts,
        }

    def toggle_favorite(self, key):
        if key not in self.yard.hybrids:
            return
        if key in self.favorites:
            self.favorites.remove(key)
        else:
            self.favorites.add(key)
        self.yard.changed()

    def matching(self, request, key):
        hybrid = self.yard.hybrids.get(key)
        if hybrid is None or request in self.commissions or not self.yard.flowers.get(key):
            return False
        t = hybrid.traits
        r, g, b = t.color
        if request == "blue":
            return b >= r + 15 and b >= g + 8 and t.petals >= 10
        if request == "peach":
            return r >= 163 and r > b + 10 and r > g + 12 and t.layers >= 2
        return request == "freckles" and t.pattern == "speckled" and t.point >= 48

    def submit(self, request, key):
        if not self.matching(request, key):
            return False
        _, _, reward, tickets = COMMISSIONS[request]
        self.yard.use_flowers({key: 1})
        self.commissions.add(request)
        self.garden.credit(reward)
        self.garden.tickets += tickets
        return True

    def can_display(self, key):
        return key in self.owned_showpieces or (self.yard.is_flower(key) and key in self.yard.stickers)

    def can_place(self, key):
        if self.can_display(key):
            return True
        if key not in SHOWPIECES:
            return False
        _, price, currency = SHOWPIECES[key]
        return (currency == "clover" and self.garden.clover >= price) or (
            currency == "tickets" and self.garden.tickets >= price)

    @staticmethod
    def valid_position(x, y):
        left, top, right, bottom = DISPLAY_BOUNDS
        return type(x) in (int, float) and type(y) in (int, float) and left <= x <= right and top <= y <= bottom

    def space_for(self, x, y, ignore=None):
        return self.valid_position(x, y) and all((x - xx)**2 + (y - yy)**2 >= 14**2
                                                for i, (_, xx, yy) in enumerate(self.displays) if i != ignore)

    def place(self, key, x, y):
        if len(self.displays) >= DISPLAY_LIMIT or not self.can_place(key) or not self.space_for(x, y):
            return False
        if not self.can_display(key):
            _, price, currency = SHOWPIECES[key]
            if currency == "tickets":
                self.garden.tickets -= price
            else:
                self.garden.spend(price)
            self.owned_showpieces.add(key)
        self.displays.append((key, round(x, 2), round(y, 2)))
        self.yard.changed()
        return True

    def move_display(self, index, x, y):
        if not 0 <= index < len(self.displays) or not self.space_for(x, y, ignore=index):
            return False
        key = self.displays[index][0]
        self.displays[index] = (key, round(x, 2), round(y, 2))
        self.yard.changed()
        return True

    def remove_display(self, index):
        if not 0 <= index < len(self.displays):
            return False
        self.displays.pop(index)
        self.yard.changed()
        return True

    def has_map(self):
        return self.yard.snail_gifts // 2 > self.maps_done

    def clue(self):
        return (self.maps_done * 3 + self.map_step + 2) % len(TREASURE_SPOTS)

    def search(self, spot):
        if not self.has_map() or spot != self.clue():
            return "Nothing there. Check the clue."
        if self.map_step == 0:
            self.map_step = 1
            self.yard.changed()
            return "You found the second clue!"
        self.map_step = 0
        prize = ("orchid", "lily", "velvet")[self.maps_done % 3]
        self.maps_done += 1
        self.owned_showpieces.add("pebble")
        self.yard.give_seed(prize)
        return f"Found a Painted Pebble and a {self.yard.flower_info(prize)[0]} seed!"

    def start_festival(self):
        if self.festival_open:
            return False
        self.festival_open = True
        self.festival_marks.clear()
        self.yard.changed()
        return True

    def enter_bouquet(self, index):
        if not self.festival_open or "bouquet" in self.festival_marks or not 0 <= index < len(self.yard.bouquets):
            return False
        if len(set(self.yard.bouquets[index]) - {""}) != 3:
            return False
        self.festival_marks.add("bouquet")
        self.yard.changed()
        return True

    def festival_game(self, key, score):
        if not self.festival_open or key not in FESTIVAL_TRIALS or score < FESTIVAL_TRIALS[key] or "game" in self.festival_marks:
            return False
        self.festival_marks.add("game")
        self.yard.changed()
        return True

    def buy_bunting(self):
        price = SHOWPIECES["bunting"][1]
        if not self.festival_open or "bunting" in self.owned_showpieces or self.garden.tickets < price:
            return False
        self.garden.tickets -= price
        self.owned_showpieces.add("bunting")
        self.yard.changed()
        return True

    def close_festival(self):
        if not self.festival_open or self.festival_marks != {"game", "bouquet"}:
            return False
        self.festival_open = False
        self.festival_marks.clear()
        self.festivals_done += 1
        self.garden.credit(125)
        self.garden.tickets += 8
        return True

    def buy_automation(self):
        if self.automated or "glass" not in self.yard.zones or not self.garden.spend(AUTOMATION_PRICE):
            return False
        self.automated = True
        return True

    def toggle_auto(self, index):
        if not self.automated or type(index) is not int or not 0 <= index < len(self.garden.plots):
            return
        if index in self.auto_pots:
            self.auto_pots.remove(index)
        else:
            self.auto_pots.add(index)
        self.yard.changed()

    def queue_seed(self, index, key):
        if not self.automated or not 0 <= index < len(self.garden.plots) or key not in self.garden.seed_options():
            return False
        queue = self.queues.setdefault(index, [])
        if len(queue) >= QUEUE_LIMIT:
            return False
        queue.append(key)
        self.yard.changed()
        return True

    def set_preset(self, index, key):
        if not self.automated or not 0 <= index < len(self.garden.plots) or key not in self.garden.seed_options():
            return False
        self.presets[index] = key
        self.yard.changed()
        return True

    def clear_queue(self, index):
        if self.queues.pop(index, None):
            self.yard.changed()

    def after_harvest(self, index, old_key, now):
        if index not in self.auto_pots:
            return
        queue = self.queues.get(index, [])
        key = queue[0] if queue else self.presets.get(index, old_key)
        if self.garden.plant(index, key, now) and queue:
            del queue[0]
            self.yard.changed()

    def discover_moon(self):
        if not self.moon:
            self.moon = True
            self.garden.plots.append(None)
            self.yard.changed()

    def keep_ghost(self, mode, duration, score, points, cleared):
        if len(points) < 2 or duration <= 0 or score <= 0 or (mode != "endless" and not cleared):
            return False
        old = self.ghosts.get(mode)
        if old and (mode == "endless" and score <= old["score"] or mode != "endless" and duration >= old["duration"]):
            return False
        self.ghosts[mode] = {
            "course": GHOST_COURSES[mode], "score": score, "duration": duration, "points": points[:GHOST_LIMIT],
        }
        self.yard.changed()
        return True
