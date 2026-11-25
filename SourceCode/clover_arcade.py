"""Pygame minigames for the garden's Play tab."""

import math
import random
from bisect import bisect_left
from dataclasses import dataclass

import pygame as pg

from clover_render import paint
from clover_scene import HEIGHT, WIDTH, oval, sparkle
from number_display import format_count
from yard_extras import GHOST_COURSES, GHOST_LIMIT


@dataclass
class Petal:
    x: float
    y: float
    speed: float
    phase: float
    gold: bool


class PetalCatch:
    basket_y = 185
    hint = ("Move the basket with your mouse or ← / →.", "Pink petals: 1 point   ·   Gold petals: 3 points")

    def __init__(self, rng=None, mode="medium"):
        self.rng = random.Random() if rng is None else rng
        self.festival = False
        self.seconds, self.half_width, self.speed = {
            "easy": (18, 35, .75), "medium": (20, 26, 1), "hard": (24, 20, 1.27),
            "endless": (None, 25, 1), "impossible": (24, 12, 1.9),
        }[mode]
        self.misses = 0
        self.score = 0
        self.done = False
        self.time = -1.0
        self.basket = self.target = WIDTH / 2
        self.next_drop = .10
        self.petals = []
        self.sparks = []
        self.keys = set()

    def aim(self, x):
        self.target = max(25, min(WIDTH - 25, x))

    def update(self, elapsed):
        if self.done:
            return
        direction = (pg.K_RIGHT in self.keys) - (pg.K_LEFT in self.keys)
        if direction:
            self.basket = max(25, min(WIDTH - 25, self.basket + direction * 250 * elapsed))
            self.target = self.basket
        else:
            self.basket += (self.target - self.basket) * (1 - math.exp(-elapsed * 27))
        before = self.time
        self.time += elapsed
        if self.seconds is not None:
            self.time = min(self.seconds, self.time)
        if self.time < 0:
            return
        step = self.time - max(0, before)
        if self.time >= self.next_drop:
            speed = self.speed + (min(.85, self.time / 100) if self.seconds is None else 0)
            gold = self.festival or self.rng.randrange(5) == 0
            self.petals.append(Petal(self.rng.uniform(23, WIDTH - 23), 32, self.rng.uniform(67, 97) * speed,
                                      self.rng.uniform(0, math.tau), gold))
            self.next_drop += self.rng.uniform(.43, .67) / speed
        remaining = []
        for petal in self.petals:
            last_y = petal.y
            petal.y += step * petal.speed
            petal.x += step * math.cos(self.time * 4 + petal.phase) * 19
            if last_y < self.basket_y <= petal.y:
                if abs(petal.x - self.basket) <= self.half_width:
                    self.score += 3 if petal.gold else 1
                    self.sparks.append((petal.x, self.time))
                else:
                    self.misses += 1
            elif petal.y < HEIGHT + 8:
                remaining.append(petal)
        self.petals = remaining
        self.sparks = [spark for spark in self.sparks if self.time - spark[1] < .38]
        self.done = self.misses >= 6 if self.seconds is None else self.time >= self.seconds

    def draw(self, scene, label):
        scene.fill("#f8ded6")
        oval(scene, "#e7d9b2", 100, 230, 195, 83)
        oval(scene, "#d3dfb8", 280, 238, 185, 76)
        paint.rect(scene, "#efd4bb", (0, 27, WIDTH, 2))
        remaining = (max(0, 6 - self.misses) / 6 if self.seconds is None else
                     1 - max(0, self.time) / self.seconds)
        paint.rect(scene, "#b46976", (0, 27, WIDTH * remaining, 2))
        label(f"{format_count(self.score)} pts", (12, 7), "button", "#633f43")
        status = f"{max(0, 6 - self.misses)} misses left" if self.seconds is None else f"{math.ceil(self.seconds * remaining)}s"
        label(status, (WIDTH - 12, 7), "button", "#633f43", "topright")
        for petal in self.petals:
            if petal.gold:
                sparkle(scene, "#ac722b", petal.x, petal.y, 8)
                sparkle(scene, "#ffdb84", petal.x, petal.y, 6)
            else:
                oval(scene, "#bf788d", petal.x, petal.y, 6, 7)
                oval(scene, "#f4a6bd", petal.x - 1, petal.y - 1, 5, 6)
        x, y = self.basket, self.basket_y
        radius = self.half_width
        oval(scene, "#abc398", x, y + 26, radius + 3, 5)
        paint.polygon(scene, "#b17c56", [(x - radius, y), (x + radius, y),
                                          (x + radius * .67, y + 22), (x - radius * .67, y + 22)])
        for height in (6, 12, 17):
            offset = radius * (.90 - height / 80)
            paint.line(scene, "#d8a774", (x - offset, y + height), (x + offset, y + height), 2)
        oval(scene, "#724c3b", x, y, radius, 5)
        paint.ellipse(scene, "#e1ad78", (x - radius, y - 5, radius * 2, 10), 2)
        for px, started in self.sparks:
            age = self.time - started
            sparkle(scene, "#fff6bb", px, y - 9 - age * 40, 6)
        if self.time < 0:
            label("Get ready", (WIDTH / 2, 100), "title", "#633f43", "center")


class FireflyTrail:
    pads = tuple(pg.Rect(22 + index * 86, 89, 70, 71) for index in range(4))
    colors = ("#efa8a7", "#f5cc88", "#b6d2a3", "#bbb8eb")
    hint = ("Watch the lights, then repeat the pattern.", "Click the lanterns or press 1–4.")

    def __init__(self, rng=None, mode="medium"):
        self.rng = random.Random() if rng is None else rng
        start, self.max_length, self.beat = {
            "easy": (2, 5, .98), "medium": (2, 8, .69), "hard": (3, 10, .49),
            "endless": (2, None, .65), "impossible": (5, 13, .28),
        }[mode]
        self.glow_time = self.beat * .71
        self.score = 0
        self.done = False
        self.pattern = [self.rng.randrange(4) for _ in range(start)]
        self.time = 0.0
        self.show_at = .60
        self.position = 0
        self.flash = None
        self.result = ""

    @property
    def ready(self):
        return self.time >= self.show_at + len(self.pattern) * self.beat

    def update(self, elapsed):
        self.time += elapsed

    def press(self, index):
        if self.done or not self.ready:
            return
        correct = index == self.pattern[self.position]
        self.flash = (index, self.time, correct)
        if not correct:
            self.result = "Pattern missed"
            self.done = True
            return
        self.position += 1
        if self.position == len(self.pattern):
            self.score += len(self.pattern)
            if self.max_length is not None and len(self.pattern) >= self.max_length:
                self.result = "Perfect trail!"
                self.done = True
            else:
                self.pattern.append(self.rng.randrange(4))
                if self.max_length is None:
                    self.beat = max(.32, self.beat * .97)
                    self.glow_time = self.beat * .71
                self.show_at = self.time + .68
                self.position = 0

    def click(self, x, y):
        for index, rect in enumerate(self.pads):
            if rect.collidepoint(x, y):
                self.press(index)
                break

    def active_light(self):
        age = self.time - self.show_at
        if 0 <= age < len(self.pattern) * self.beat and age % self.beat < self.glow_time:
            return self.pattern[int(age / self.beat)]
        return None

    def draw(self, scene, label):
        scene.fill("#38334d")
        oval(scene, "#4b4c64", 83, 258, 200, 85)
        oval(scene, "#544c66", 290, 235, 178, 56)
        for x, y in ((21, 44), (61, 76), (113, 24), (229, 35), (301, 62), (345, 48), (322, 186)):
            sparkle(scene, "#b5a1bb", x, y, 4)
        label(f"{format_count(self.score)} pts", (12, 7), "button", "#fdf0d8")
        label(f"Length {format_count(len(self.pattern))}", (WIDTH - 12, 7), "button", "#fdf0d8", "topright")
        status = self.result or ("Your turn" if self.ready else "Watch")
        label(status, (WIDTH / 2, 52), "title", "#fdf0d8", "center")
        active = self.active_light()
        for index, rect in enumerate(self.pads):
            pressed = self.flash and self.flash[0] == index and self.time - self.flash[1] < .25
            color = self.colors[index] if active == index or pressed else "#5e5572"
            if pressed and not self.flash[2]:
                color = "#a56272"
            paint.rect(scene, "#29263d", rect.move(0, 4), border_radius=14)
            paint.rect(scene, color, rect, border_radius=14)
            bright = active == index or pressed
            sparkle(scene, "#fff5ce" if bright else "#a796aa", rect.centerx, rect.centery - 8, 12 if bright else 8)
            label(str(index + 1), (rect.centerx, rect.bottom - 15), "button",
                  "#534054" if bright else "#fdf0d8", "center")
        if len(self.pattern) <= 22:
            step = min(14, 248 / len(self.pattern))
            for index in range(len(self.pattern)):
                x = WIDTH / 2 + (index - (len(self.pattern) - 1) / 2) * step
                oval(scene, "#f6cf8c" if index < self.position else "#776884", x, 187, 3, 3)
        else:
            label(f"{format_count(self.position)}/{format_count(len(self.pattern))}", (WIDTH/2, 187), "button", "#fdf0d8", "center")


class PondFishing:
    hint = ("When you get a bite, stop the bar in the green.", "Click the pond or press Space to reel in.")

    def __init__(self, rng=None, mode="medium"):
        self.rng = random.Random() if rng is None else rng
        self.cast_limit, self.bite_seconds, self.tolerance = {
            "easy": (4, 1.85, 1.42), "medium": (3, 1.45, 1),
            "hard": (3, 1.04, .72), "endless": (None, 1.35, .94), "impossible": (3, .69, .36),
        }[mode]
        self.misses = 0
        self.score = 0
        self.done = False
        self.casts = 0
        self.time = 0
        self.bite_at = self.rng.uniform(1.0, 2.4)
        self.target = self.rng.uniform(.28, .72)
        self.catches = []
        self.message = ""
        self.message_until = 0

    def update(self, elapsed):
        self.time += elapsed
        if not self.done and self.time - self.bite_at > self.bite_seconds:
            self.next_cast("It got away")

    def press(self):
        if self.done or not self.bite_at <= self.time <= self.bite_at + self.bite_seconds:
            return
        distance = abs((self.time - self.bite_at) / self.bite_seconds - self.target) / self.tolerance
        if distance <= .045:
            kind, points, text = "lily_seed", 5, "A lucky lily seed!"
        elif distance <= .13:
            kind, points, text = "fish", 3, "Sunfish!"
        elif distance <= .23:
            kind, points, text = "button", 1, "A lost button!"
        else:
            self.next_cast("Splash!")
            return
        self.catches.append(kind)
        self.score += points
        self.next_cast(text, caught=True)

    def next_cast(self, message, caught=False):
        self.casts += 1
        if not caught:
            self.misses += 1
        self.message, self.message_until = message, self.time + .9
        self.done = self.misses >= 3 if self.cast_limit is None else self.casts >= self.cast_limit
        if self.cast_limit is None and caught:
            self.bite_seconds = max(.83, self.bite_seconds * .975)
        if not self.done:
            self.bite_at = self.time + self.rng.uniform(1.3, 2.6)
            self.target = self.rng.uniform(.28, .72)

    def draw(self, scene, label):
        scene.fill("#dae8d4")
        oval(scene, "#afcfae", 109, 97, 172, 60)
        oval(scene, "#83b8b6", 196, 214, 231, 150)
        for x, y in ((49, 145), (88, 174), (291, 128), (319, 188)):
            oval(scene, "#78a685", x, y, 14, 4)
            oval(scene, "#f0b4cc", x+3, y-3, 4, 3)
        biting = self.bite_at <= self.time <= self.bite_at + self.bite_seconds and not self.done
        bob = 2 * math.sin(self.time * (24 if biting else 5))
        oval(scene, "#b4d5c8", 186, 116, 18 + (4 if biting else 0), 5)
        oval(scene, "#fdf3d6", 186, 108 + bob, 6, 7)
        oval(scene, "#cc726e", 186, 105 + bob, 5, 4)
        label(f"{format_count(self.score)} pts", (12, 7), "button", "#395a55")
        status = (f"{3 - self.misses} misses left" if self.cast_limit is None else
                  f"Cast {min(self.cast_limit, self.casts + 1)} / {self.cast_limit}")
        label(status, (WIDTH - 12, 7), "button", "#395a55", "topright")
        message = "Bite!" if biting else self.message if self.time < self.message_until else "Wait for a bite…"
        label(message, (WIDTH / 2, 56), "title", "#395a55", "center")
        bar = pg.Rect(51, 185, 270, 14)
        paint.rect(scene, "#e4efd6", bar, border_radius=7)
        if biting:
            center = bar.x + round(bar.width * self.target)
            green, gold = 35 * self.tolerance, 12 * self.tolerance
            paint.rect(scene, "#8abd91", (center - green, bar.y, green * 2, bar.height), border_radius=6)
            paint.rect(scene, "#efcf78", (center - gold, bar.y, gold * 2, bar.height), border_radius=5)
            x = bar.x + round(bar.width * (self.time - self.bite_at) / self.bite_seconds)
            paint.line(scene, "#4d6d5f", (x, bar.y - 3), (x, bar.bottom + 3), 3)


@dataclass
class Ledge:
    start: float
    end: float
    top: int
    index: int
    dew: bool


class MushroomHop:
    hint = ("Jump from mushroom to mushroom. Don’t fall!", "Space / ↑ / click to jump. Hold ← to slow down.")

    def __init__(self, rng=None, mode="medium", ghost=None):
        self.rng = random.Random(GHOST_COURSES[mode]) if rng is None else rng
        self.speed, self.gaps, self.finish = {
            "easy": (81, (15, 30), 7), "medium": (98, (23, 46), 10),
            "hard": (123, (34, 65), 13), "endless": (104, (26, 51), None),
            "impossible": (154, (54, 85), 15),
        }[mode]
        self.score = 0
        self.done = False
        self.time = -.65
        self.x, self.y = 44.0, 176.0
        self.vy = 0
        self.on_ground = True
        self.last_ground = self.time
        self.jump_until = -100
        self.ledges = [Ledge(0, 171, 176, 0, False)]
        self.farthest = 0
        self.landed_at = -100
        self.result = ""
        self.keys = set()
        self.trace = [(0.0, self.x, self.y)]
        self.next_sample = .09
        self.ghost = ghost["points"] if ghost else ()
        self.ghost_times = [p[0] for p in self.ghost]
        self.ghost_xs = [p[1] for p in self.ghost]

    def grow_course(self):
        while self.ledges[-1].end < self.x + WIDTH + 46:
            last = self.ledges[-1]
            gap = self.rng.randint(*self.gaps)
            start = last.end + gap
            top = max(136, min(184, last.top + self.rng.randint(-18, 18)))
            width = self.rng.randint(55, 98)
            self.ledges.append(Ledge(start, start + width, top, last.index + 1, self.rng.randrange(4) == 0))

    def jump(self):
        self.jump_until = self.time + .14

    def update(self, elapsed):
        if self.done:
            return
        before = self.time
        self.time += elapsed
        self.grow_course()
        if self.time < 0:
            return
        dt = self.time - max(0, before)
        # Small physics steps keep landing and jumping consistent at lower frame rates.
        count = max(1, math.ceil(dt / .012))
        for _ in range(count):
            self.step(dt / count)
            if self.done:
                break
        if len(self.trace) < GHOST_LIMIT and (self.time >= self.next_sample or self.done) and self.time > self.trace[-1][0]:
            self.trace.append((round(self.time, 3), round(self.x, 2), round(self.y, 2)))
            self.next_sample = self.time + .09

    def step(self, dt):
        speed = self.speed + (min(self.farthest * 1.8, 48) if self.finish is None else 0)
        if self.on_ground and pg.K_LEFT in self.keys:
            speed *= .82
        self.x += speed * dt
        if self.on_ground:
            if any(p.start - 3 <= self.x <= p.end + 3 and p.top == self.y for p in self.ledges):
                self.last_ground = self.time
            else:
                self.on_ground = False
        if self.time <= self.jump_until and self.time - self.last_ground <= .095:
            self.on_ground = False
            self.vy = -286
            self.last_ground = self.jump_until = -100
        if not self.on_ground:
            previous = self.y
            self.vy += 790 * dt
            self.y += self.vy * dt
            if self.vy >= 0:
                for ledge in self.ledges:
                    if ledge.start - 3 <= self.x <= ledge.end + 3 and previous <= ledge.top <= self.y:
                        self.y, self.vy = ledge.top, 0
                        self.on_ground, self.last_ground, self.landed_at = True, self.time, self.time
                        if ledge.index > self.farthest:
                            self.farthest = ledge.index
                            self.score += 3
                        if self.finish is not None and self.farthest >= self.finish:
                            self.result, self.done = "Trail cleared!", True
                        break
        for ledge in self.ledges:
            if ledge.dew and abs(self.x - (ledge.start + ledge.end) / 2) < 12 and abs(self.y - ledge.top) < 39:
                ledge.dew = False
                self.score += 2
        self.ledges = [p for p in self.ledges if p.end >= self.x - 165]
        if self.y > HEIGHT + 25:
            self.result, self.done = "Tumbled off", True

    def ghost_position(self):
        if not self.ghost:
            return None
        i = bisect_left(self.ghost_times, max(0, self.time))
        if i == 0:
            return self.ghost[0][1:]
        if i == len(self.ghost):
            return self.ghost[-1][1:]
        first, second = self.ghost[i-1], self.ghost[i]
        t = (self.time - first[0]) / max(.001, second[0] - first[0])
        return tuple(a + (b-a)*t for a, b in zip(first[1:], second[1:]))

    def ghost_gap(self):
        if not self.ghost or self.time < 0:
            return None
        i = bisect_left(self.ghost_xs, self.x)
        if not 0 < i < len(self.ghost):
            return None
        a, b = self.ghost[i-1], self.ghost[i]
        t = (self.x - a[1]) / max(.01, b[1] - a[1])
        return self.time - (a[0] + (b[0] - a[0])*t)

    def draw(self, scene, label):
        scene.fill("#e9edce")
        camera = max(0, self.x - 104)
        oval(scene, "#f4d995", 302, 54, 24, 24)
        for i in range(4):
            x = (i * 133 - camera * .23) % (4 * 133) - 83
            oval(scene, "#c9dba9", x, 237, 115, 113)
        paint.rect(scene, "#b1c4a3", (0, HEIGHT - 14, WIDTH, 14))
        for i in range(13):
            x = (i * 31 - camera * .67) % (13 * 31)
            oval(scene, "#c9d4b6", x, 215 + 2 * math.sin(x), 11, 1)
        for ledge in self.ledges:
            x, y = ledge.start - camera, ledge.top
            width = ledge.end - ledge.start
            if x > WIDTH or x + width < 0:
                continue
            paint.rect(scene, "#caac8c", (x + width * .42, y + 8, width * .16, HEIGHT - y + 4))
            color = "#97aa68" if self.finish == ledge.index else "#bc7a69"
            paint.rect(scene, color, (x, y, width, 14), border_radius=6)
            for i in range(1, max(2, int(width // 16))):
                oval(scene, "#f2cfaa", x + width * i / max(2, int(width // 16)), y + 4 + 4 * (i % 2), 2.5, 1.5)
            if ledge.dew:
                sparkle(scene, "#bf8a46", x + width / 2, y - 24 + 2 * math.sin(self.time * 6), 6)
        ghost = self.ghost_position()
        if ghost:
            gx, gy = ghost
            gx -= camera
            if -15 <= gx <= WIDTH + 15:
                oval(scene, "#a6a2c1", gx, gy - 7, 8, 7)
                oval(scene, "#b8b4d0", gx, gy - 15, 11, 6)
                sparkle(scene, "#e5daee", gx - 5, gy - 15, 4)
        x = self.x - camera
        landing = max(0, 1 - (self.time - self.landed_at) / .22)
        oval(scene, "#ecddba", x, self.y - 7 + landing, 8 + landing, 8 - landing * 2)
        oval(scene, "#c67d65", x, self.y - 15 + landing * 2, 11 + landing, 6 - landing * 2)
        oval(scene, "#fff1da", x + 3, self.y - 17 + landing, 2, 2)
        oval(scene, "#554737", x + 4, self.y - 6, 1, 1.4)
        label(f"{format_count(self.score)} pts", (12, 7), "button", "#3d543d")
        status = f"Ledges {format_count(self.farthest)}" if self.finish is None else f"Ledges {self.farthest}/{self.finish}"
        label(status, (WIDTH - 12, 7), "button", "#3d543d", "topright")
        split = self.ghost_gap()
        if split is not None:
            label(f"vs ghost {split:+.2f}s", (WIDTH / 2, 15), "small", "#604d80", "center")
        if self.time < 0:
            label("Get ready", (WIDTH / 2, 73), "title", "#3d543d", "center")


class CloverPop:
    hint = ("Tap the clovers before they disappear.", "Regular clovers: 1 point · Golden clovers: 3 points")

    def __init__(self, rng=None, mode="medium"):
        self.rng = random.Random() if rng is None else rng
        self.festival = False
        self.seconds, self.lifetime, self.radius = {
            "easy": (17, 1.9, 23), "medium": (21, 1.27, 19), "hard": (24, .89, 15),
            "endless": (None, 1.27, 19), "impossible": (24, .5, 10),
        }[mode]
        self.score = 0
        self.misses = 0
        self.done = False
        self.time = -.65
        self.spawn_at = .05
        self.target = None
        self.spark = None

    def update(self, elapsed):
        self.time += elapsed
        if self.target and self.time >= self.target[2] + self.target[3]:
            self.target = None
            self.misses += 1
            self.spawn_at = self.time + .10
        self.done = self.misses >= 4 if self.seconds is None else self.time >= self.seconds
        if not self.done and self.target is None and self.time >= self.spawn_at:
            fade = min(self.score / 95, .48) if self.seconds is None else 0
            self.target = (self.rng.uniform(30, WIDTH - 30), self.rng.uniform(55, HEIGHT - 30),
                           self.time, self.lifetime * (1 - fade), self.festival or self.rng.randrange(5) == 0)

    def click(self, x, y):
        if not self.target or self.done:
            return
        tx, ty, _, _, gold = self.target
        if (tx - x)**2 + (ty - y)**2 <= (self.radius + 4)**2:
            self.score += 3 if gold else 1
            self.spark = (tx, ty, self.time)
            self.target = None
            self.spawn_at = self.time + .13

    def draw(self, scene, label):
        scene.fill("#e2edda")
        for i in range(15):
            x = (58 + i * 83) % WIDTH
            y = 38 + (37 + i * 29) % (HEIGHT - 51)
            oval(scene, "#d4e3ce", x, y, 6, 2)
        label(f"{format_count(self.score)} pts", (12, 7), "button", "#3d543d")
        status = (f"{4 - self.misses} misses left" if self.seconds is None else
                  f"{max(0, math.ceil(self.seconds - max(0, self.time)))}s")
        label(status, (WIDTH - 12, 7), "button", "#3d543d", "topright")
        if self.target:
            x, y, appeared, duration, golden = self.target
            age = (self.time - appeared) / duration
            radius = self.radius * (.65 + .35 * min(1, age * 7))
            color = "#d89a48" if golden else "#63945f"
            outline = "#bd8950" if golden else "#81aa76"
            r = self.radius + 6 - age * 4
            paint.ellipse(scene, outline, (x - r, y - r, 2 * r, 2 * r), 1)
            for i in range(4):
                angle = (i + .5) * math.tau / 4
                oval(scene, color, x + math.cos(angle) * radius * .47, y + math.sin(angle) * radius * .47,
                     radius * .46, radius * .46)
        if self.spark:
            x, y, started = self.spark
            age = self.time - started
            if age < .42:
                for angle in (0, 2.1, 4.2):
                    r = 7 + age * 54
                    sparkle(scene, "#b99658", x + math.cos(angle) * r, y + math.sin(angle) * r, 5 - age * 5)
        if self.time < 0:
            label("Get ready", (WIDTH / 2, 100), "title", "#3d543d", "center")


GAME_TYPES = {
    "petals": PetalCatch, "fireflies": FireflyTrail, "fishing": PondFishing,
    "hopping": MushroomHop, "pop": CloverPop,
}
