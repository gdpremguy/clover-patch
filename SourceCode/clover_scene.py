import math
from functools import lru_cache

import pygame as pg

from clover_render import Canvas, paint
from flora import traits_for_stock
from garden import STYLES, VISIT_TIME
from yard import FLOWERS, RARE_SEEDS


WIDTH, HEIGHT = 372, 223
CLOVER = (186, 108)
POTS = ((89, 198), (186, 198), (283, 198))
POT_RECTS = tuple(pg.Rect(x - 23, y - 42, 46, 56) for x, y in POTS)


def pot_positions(count):
    return POTS if count == 3 else ((63, 198), (145, 198), (227, 198), (309, 198))


def pot_hitboxes(count):
    return POT_RECTS if count == 3 else tuple(pg.Rect(x - 23, y - 42, 46, 56) for x, y in pot_positions(count))


def oval(surface, color, x, y, rx, ry):
    paint.ellipse(surface, color, (x - rx, y - ry, 2 * rx, 2 * ry))


def sparkle(surface, color, x, y, radius):
    neck = radius * .32
    paint.polygon(surface, color, [(x, y - radius), (x + neck, y - neck), (x + radius, y),
                                   (x + neck, y + neck), (x, y + radius), (x - neck, y + neck),
                                   (x - radius, y), (x - neck, y - neck)])


@lru_cache(maxsize=16)
def backdrop(key, pixels=(WIDTH, HEIGHT)):
    style = STYLES[key]
    scene = Canvas((WIDTH, HEIGHT), pixels)
    sky = pg.Color(style.sky)
    top = sky.lerp(pg.Color(style.outline), .08)
    for y in range(pixels[1]):
        color = top.lerp(sky, min(1, y / (122 * scene.sy)))
        pg.draw.line(scene.surface, color, (0, y), (pixels[0] - 1, y))
    oval(scene, style.glow, 298, 43, 19, 19)
    if key in ("moonlight", "lantern", "aurora"):
        if key == "aurora":
            for index, color in enumerate(("#47716f", "#5d8c84", "#8778a1")):
                points = [(x, 56 + index * 10 + 16 * math.sin(x / 67 + index * .35) - x * .09)
                          for x in range(-12, WIDTH + 14, 9)]
                paint.lines(scene, color, False, points, 12 - 3 * index)
                paint.aalines(scene, pg.Color(color).lerp(sky, .20), False, points)
        oval(scene, top.lerp(pg.Color(style.sky), .26), 306, 35, 17, 17)
        for x, y in ((33, 37), (84, 65), (136, 25), (200, 37), (250, 63), (339, 24)):
            sparkle(scene, style.shine, x, y, 4)
    else:
        cloud = pg.Color(style.sky).lerp(pg.Color("#fff8e8"), .66)
        for x, y in ((56, 38), (104, 55)):
            oval(scene, cloud, x, y, 24, 5)
            oval(scene, cloud, x - 4, y - 3, 12, 7)
    oval(scene, style.hills[0], 106, 199, 216, 92)
    oval(scene, style.hills[1], 290, 235, 201, 113)
    if key == "pond":
        oval(scene, "#77a6aa", 324, 159, 72, 21)
        for x, y in ((28, 55), (73, 76), (130, 38), (234, 52), (279, 75), (341, 60)):
            paint.line(scene, "#81a8a7", (x, y), (x - 4, y + 8), 2)
        for x, y in ((282, 160), (326, 151), (352, 164)):
            paint.ellipse(scene, "#c0dcd2", (x - 11, y - 3, 22, 6), 1)
    elif key == "maple":
        for x, y in ((34, 145), (57, 94), (267, 97), (322, 132), (333, 190)):
            paint.polygon(scene, "#af6748", [(x - 8, y - 1), (x + 3, y - 5), (x + 9, y - 2), (x, y + 4)])
    elif key == "lantern":
        for x, y, side in ((42, 99, 1), (324, 109, -1), (357, 87, -1)):
            paint.lines(scene, "#584052", False, [(x, y + 57), (x, y), (x + 17 * side, y)], 3)
            lx = x + 17 * side
            oval(scene, "#88616a", lx, y + 14, 16, 19)
            paint.rect(scene, "#d6806e", (lx - 7, y + 3, 14, 18), border_radius=4)
            paint.rect(scene, "#ffd59a", (lx - 4, y + 5, 8, 14), border_radius=3)
            paint.line(scene, "#624356", (lx - 7, y + 4), (lx + 7, y + 4), 2)
            paint.line(scene, "#624356", (lx - 7, y + 20), (lx + 7, y + 20), 2)
    for x, y in ((28, 168), (65, 142), (112, 162), (231, 164), (315, 130), (337, 184), (360, 153)):
        paint.lines(scene, style.outline, False, [(x - 5, y - 5), (x, y), (x + 3, y - 7)], 1)
        if x % 2:
            oval(scene, style.shine, x + 3, y - 7, 3, 3)
    oval(scene, style.shadow, 186, 153, 53, 6)
    return scene


def smooth_polygon(points):
    for _ in range(2):
        pairs = zip(points, points[1:] + points[:1])
        points = tuple(p for (x, y), (u, v) in pairs
                       for p in ((.75 * x + .25 * u, .75 * y + .25 * v), (.25 * x + .75 * u, .25 * y + .75 * v)))
    return points


@lru_cache(maxsize=len(STYLES))
def leaves(key):
    if key in ("moonlight", "aurora"):
        leaf = ((0, 2), (-17, -10), (-14, -29), (0, -47), (14, -29), (17, -10))
        angles = (-44, 44, 126, 234, 0) if key == "aurora" else (-45, 45, 135, 225)
    elif key in ("strawberry", "lantern"):
        leaf = ((0, 2), (-19, -12), (-24, -29), (-14, -41), (-5, -39), (0, -30),
                (5, -39), (14, -41), (24, -29), (19, -12))
        angles = (-48, 48, 132, 228) if key == "lantern" else (-65, 65, 0)
    elif key == "maple":
        leaf = ((0, 2), (-20, -13), (-12, -16), (-23, -30), (-9, -28), (0, -47),
                (9, -28), (23, -30), (12, -16), (20, -13))
        angles = (-65, 65, 0)
    else:
        leaf = ((0, 2), (-18, -10), (-23, -24), (-15, -39), (0, -43),
                (15, -39), (23, -24), (18, -10))
        angles = (-65, 65, 0)
    if key != "maple":
        leaf = smooth_polygon(leaf)
    result = []
    for degrees in angles:
        angle = math.radians(degrees)
        sn, cs = math.sin(angle), math.cos(angle)

        def rotate(points):
            return tuple((x * cs - y * sn, x * sn + y * cs - 12) for x, y in points)

        result.append((rotate(leaf), rotate(((0, -4), (-3, -16), (0, -27))),
                       rotate(((-9, -22), (8, -24), (-7, -31)))))
    return result


def draw_clover(scene, key, tick, bounce_start):
    style = STYLES[key]
    age = (tick - bounce_start) / .42
    bounce = math.sin(age * math.tau) * (1 - age) * .20 if 0 <= age < 1 else 0
    sway = math.sin(tick * 1.65) * 3
    x, y = CLOVER

    def transform(pos):
        px, py = pos
        return (x + px * (1 + bounce) + sway * (45 - py) / 100, y + py * (1 - bounce))

    stem = ((-12, 42), (0, 29), (6, 15), (5, 3), (0, -12))
    paint.lines(scene, style.outline, False, [transform(p) for p in stem], 4)
    for index, (leaf, vein, seeds) in enumerate(leaves(key)):
        outline = [transform(p) for p in leaf]
        paint.polygon(scene, style.leaves[index % 3], outline)
        paint.aalines(scene, style.outline, True, outline)
        paint.aalines(scene, style.shine, False, [transform(p) for p in vein])
        if key == "strawberry":
            for px, py in map(transform, seeds):
                oval(scene, style.shine, px, py, 1.3, 1.8)


@lru_cache(maxsize=128)
def petal_geometry(traits):
    rings = []
    reach = 6 + .092 * traits.length
    breadth = min(2 + .067 * traits.width, 1.28 * reach * math.sin(math.pi / traits.petals))
    for layer in range(traits.layers):
        length = reach * (.73 ** layer)
        width = breadth * (.81 ** layer)
        paths = []
        for index in range(traits.petals):
            angle = math.tau * (index + layer * .48) / traits.petals - math.pi / 2
            cs, sn = math.cos(angle), math.sin(angle)

            def rotate(u, v):
                return u * cs - v * sn, u * sn + v * cs

            edge = []
            for step in range(13):
                t = step / 12
                bulge = math.sin(math.pi * t) ** (.45 + traits.point / 125)
                edge.append((length * t, width * bulge * (1.13 - t * .29)))
            points = [rotate(u, v) for u, v in edge]
            points.extend(rotate(u, -v) for u, v in reversed(edge[1:-1]))
            paths.append((points, rotate(length * .73, 0), rotate(length * .46, 0), rotate(length * .61, width * .25)))
        rings.append(paths)
    return rings


def generated_bloom(surface, x, y, traits, size=1):
    base = pg.Color(*traits.color)
    edge = base.lerp(pg.Color("#4d3f48"), .26)
    light = base.lerp(pg.Color("#fff6de"), .52)

    def at(p):
        return x + p[0] * size, y + p[1] * size

    for layer, ring in enumerate(petal_geometry(traits)):
        fill = base.lerp(light, layer * .29)
        for outline, tip, inner, spot in ring:
            points = [at(point) for point in outline]
            paint.polygon(surface, fill, points)
            paint.aalines(surface, edge, True, points)
            if traits.pattern == "veined":
                paint.line(surface, light, at(inner), at(tip), .5)
            elif traits.pattern == "speckled":
                for point in (spot, tip):
                    px, py = at(point)
                    oval(surface, light, px, py, .6 * size, .6 * size)
            elif traits.pattern == "tipped":
                px, py = at(tip)
                oval(surface, light, px, py, 1.15 * size, 1.15 * size)
    radius = (1.9 + traits.width / 60) * size
    oval(surface, traits.center, x, y, radius, radius)


def bloom(surface, x, y, key, size=1, yard=None):
    if yard is not None and key in yard.hybrids:
        generated_bloom(surface, x, y, yard.hybrids[key].traits, size)
        return
    color = FLOWERS[key][1]
    if key in RARE_SEEDS:
        generated_bloom(surface, x, y, traits_for_stock(key, color), size)
    elif key == "mushroom":
        paint.rect(surface, "#f4ddba", (x - 2*size, y, 4*size, 8*size))
        oval(surface, color, x, y - 2*size, 8*size, 5*size)
        oval(surface, "#fff2dd", x + 2*size, y - 4*size, size, size)
    elif key == "tulip":
        points = ((-8, -7), (-4, -4), (0, -9), (4, -4), (8, -7), (5, 5), (0, 7), (-5, 5))
        paint.polygon(surface, color, [(x + dx*size, y + dy*size) for dx, dy in points])
    elif key in ("lavender", "velvet", "moonbell"):
        for dx, dy in ((0, -8), (-4, -4), (4, -4), (-4, 1), (4, 1)):
            oval(surface, color, x + dx*size, y + dy*size, 3*size, 3*size)
    else:
        for i in range(5):
            angle = math.tau * i / 5
            oval(surface, color, x + math.cos(angle)*5*size, y + math.sin(angle)*5*size, 4*size, 4*size)
        oval(surface, "#ce935c", x, y, 3*size, 3*size)
        if key == "speckle":
            for dx, dy in ((-5, -1), (-2, 5), (2, -5)):
                oval(surface, "#fff0dc", x + dx*size, y + dy*size, size, size)


def pot_sprinkles(scene, x, y, kind, age):
    if kind == "water":
        if age < .41:
            stretch = 10 + age * 42
            paint.ellipse(scene, "#a9d7dc", (x - stretch, y - 9 - stretch * .2, stretch * 2, stretch * .4), 1)
        for i in range(5):
            dx = (i - 2) * 6 * (1 + age)
            dy = -47 + age * (82 + i * 11) - math.sin(i + age * 9) * 3
            radius = max(.6, 2.3 - age * 3.2)
            oval(scene, "#a7d1db", x + dx, y + dy, radius, radius * 1.45)
    else:
        colors = ("#ebcf8c", "#87aa6d", "#f9e8bb") if kind == "harvest" else ("#a77961", "#d6a785", "#e6bf9a")
        for i in range(6):
            dx = (-19 + i * 8) * (.24 + age * 1.25)
            dy = -10 + (8 + i % 3 * 8) * (age * 4 - 1.18) ** 2 - (15 if kind == "plant" else 34)
            radius = max(.45, 2.7 - age * 3.8)
            if kind == "harvest" and i % 2 == 0:
                sparkle(scene, colors[i % 3], x + dx, y + dy, radius * 1.5)
            else:
                oval(scene, colors[i % 3], x + dx, y + dy, radius, radius * .68)


def draw_pots(scene, garden, now, tick, selected=None, effects=None):
    style, pots = STYLES[garden.style_key], garden.plots
    effects = effects or {}
    for index, ((x, base_y), planted) in enumerate(zip(pot_positions(len(pots)), pots)):
        action, start = effects.get(index, ("", -100))
        age = tick - start
        hop = 5 * math.sin(math.pi * age / .31) if action in ("plant", "harvest") and 0 <= age < .31 else 0
        y = base_y - hop
        oval(scene, style.shadow, x, base_y + 8, 22 - hop * .35, 5 - hop * .17)
        if index == selected:
            radius = 26 + 1.2 * math.sin(tick * 5)
            paint.ellipse(scene, "#fff4d9", (x - radius, y + 1, radius * 2, 15), 2)
        moon = index == 3
        paint.polygon(scene, "#8279a7" if moon else "#ba7c63",
                      [(x - 17, y - 9), (x + 17, y - 9), (x + 12, y + 9), (x - 12, y + 9)])
        oval(scene, "#b2b3ce" if moon else "#d39b78", x, y - 8, 18, 5)
        oval(scene, "#6c4c3d", x, y - 8, 15, 3)
        if moon:
            sparkle(scene, "#f3e5c7", x + 20, y + 4, 3.6 + math.sin(tick*3))
        if planted is None:
            paint.line(scene, "#efd1af", (x - 3, y - 8), (x + 3, y - 8))
            paint.line(scene, "#efd1af", (x, y - 11), (x, y - 5))
            if age < .72:
                pot_sprinkles(scene, x, base_y, action, age)
            continue
        progress = garden.crop_progress(index, now)
        key = planted[3]
        color = garden.yard.flower_info(key)[1]
        tx = x + 2 * math.sin(tick * 2 + index)
        top = y - 13 - 17 * math.sin(progress * math.pi / 2)
        paint.line(scene, "#527456", (x, y - 8), (tx, top), 3)
        oval(scene, "#81a574", tx - 4, top + 6, 5, 2)
        if progress < 1:
            if progress > .82:
                bloom(scene, tx, top, key, .24 + (progress - .82) * 2.5, yard=garden.yard)
            else:
                radius = 1.5 + 1.5 * progress
                oval(scene, color, tx, top, radius, radius)
            paint.line(scene, "#f5d58c", (x - 10, y + 4), (x - 10 + 20 * progress, y + 4), 2)
            if planted[2]:
                oval(scene, "#a7d8e5", x + 11, y - 16, 2, 3)
        else:
            unfolding = min(1, (now - planted[0]) / .55)
            size = .69 + .31 * (1 - (1 - unfolding)**3) + .09 * math.sin(unfolding * math.pi)
            bloom(scene, tx, top, key, size, yard=garden.yard)
            if math.sin(tick * 4 + index) > -.3:
                sparkle(scene, style.shine, x + 15, top - 4, 3 + math.sin(tick*4+index))
        if age < .72:
            pot_sprinkles(scene, x, base_y, action, age)


def butterfly_pos(elapsed):
    flight = 1 - (1 - elapsed) ** 2 if elapsed < 1 else 1 - max(0, elapsed - (VISIT_TIME - 1)) ** 2
    return 34 + flight * 128 + math.sin(elapsed * 2) * 22, 49 + math.sin(elapsed * 3) * 12


def draw_butterfly(scene, elapsed, kind="butterfly"):
    x, y = butterfly_pos(elapsed)
    wing = 7 + 6 * abs(math.sin(elapsed * 14))
    for direction in (-1, 1):
        oval(scene, "#765262", x + direction * wing / 2, y - 4, wing / 2 + 1, 8)
        oval(scene, "#e8d3a8" if kind == "moth" else "#ffd395", x + direction * wing / 2, y - 4, wing / 2, 7)
        oval(scene, "#aa948b" if kind == "moth" else "#f3a8c5", x + direction * wing / 2, y + 4, wing / 2, 4)
        if kind == "moth":
            oval(scene, "#8b7067", x + direction * wing / 2, y - 4, 2, 2)
    paint.line(scene, "#653f4e", (x, y - 7), (x, y + 6), 2)


def draw_bee(scene, elapsed):
    x = 235 + elapsed * 96
    y = 100 - 38 * math.sin(elapsed * math.pi / .8)
    flap = 2 * math.sin(elapsed * 32)
    oval(scene, "#fff5de", x - 5, y - 6 - flap, 4, 4)
    oval(scene, "#fff5de", x + 1, y - 6 + flap, 4, 4)
    oval(scene, "#604533", x, y, 9, 5)
    oval(scene, "#f6be57", x, y, 8, 4)
    paint.line(scene, "#604533", (x - 3, y - 3), (x - 3, y + 3), 2)
    paint.line(scene, "#604533", (x + 2, y - 3), (x + 2, y + 3), 2)
