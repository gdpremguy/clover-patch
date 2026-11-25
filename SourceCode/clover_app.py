import math
import os
import sys
import time
from functools import lru_cache

import pygame as pg

from arcade_modes import MODES
from clover_arcade import GAME_TYPES, CloverPop, FireflyTrail, MushroomHop, PetalCatch, PondFishing
from clover_estate import ESTATE_PAGES, draw_showcase
from clover_layout import (
    CONTEXT, DISPLAY_MODE, GARDEN_TAB, GUIDES, LIST, NAV, NAV_TITLES, PANEL, PICK, PLAY_TAB,
    REPLAY, ROW_HEIGHT, SCENE, SIZE, TAB_PAGE, TRACK, YARD_TAB, nav_rows,
)
from clover_render import Canvas, paint
from clover_scene import (
    CLOVER, HEIGHT, WIDTH, backdrop, butterfly_pos, draw_bee, draw_butterfly,
    draw_clover, draw_pots, oval, pot_hitboxes, pot_positions, sparkle,
)
from garden import (
    CLOVER_EXCHANGE, GAMES, MAX_LEVEL, MILESTONES, POT_COUNT, STREAK_LENGTH,
    STYLES, TICKET_COST, UPGRADES, VISIT_TIME, Garden,
)
from clover_yard import YARD_PAGES, YardView, draw_snail
from number_display import format_count as compact
from yard import RARE_SEEDS, STICKERS
from yard_extras import FESTIVAL_TRIALS


CREAM = "#f4f5ef"
PAPER = "#fdfdf8"
INK = "#27352b"
MUTED = "#576459"
GREEN = "#305943"
GREEN_HOVER = "#244834"
MINT = "#e4eee1"
LINE = "#e2e7de"
GOLD = "#8d5c2c"
ROW_COUNTS = (len(UPGRADES), POT_COUNT, len(STYLES), len(MILESTONES), len(GAMES) + 1)
FONT_SPECS = {
    "title": (26, True), "balance": (18, True), "heading": (19, True), "row": (15, True),
    "small": (13, False), "button": (13, True), "pick": (16, True), "group": (11, True),
}
SCENE_FONTS = {
    "title": (23, True), "balance": (16, True), "row": (14, True),
    "small": (12, False), "button": (12, True), "pick": (15, True),
}
GAME_DETAILS = {
    "petals": "Catch falling petals", "fireflies": "Repeat the lights",
    "fishing": "Time the bite", "hopping": "Jump across a mushroom trail", "pop": "Tap clovers before they vanish",
}


def viewport(size):
    width, height = size
    scale = min(width / SIZE[0], height / SIZE[1])
    scaled = (max(1, round(SIZE[0] * scale)), max(1, round(SIZE[1] * scale)))
    rect = pg.Rect(0, 0, *scaled)
    rect.center = (width // 2, height // 2)
    return rect


def scene_point(point):
    x, y = point
    return (x-SCENE.x)*WIDTH/SCENE.width, (y-SCENE.y)*HEIGHT/SCENE.height


def window_size():
    if sys.platform != "win32" or os.environ.get("SDL_VIDEODRIVER") == "dummy":
        return SIZE
    # Avoid Windows enlarging the whole window as a blurry bitmap.
    import ctypes

    user = ctypes.windll.user32
    try:
        user.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except AttributeError:
        user.SetProcessDPIAware()
    try:
        scale = max(1, user.GetDpiForSystem() / 96)
    except AttributeError:
        scale = 1
    return tuple(round(length * scale) for length in SIZE)


class GameDisplay:
    def __init__(self, preferred_size):
        desktops = pg.display.get_desktop_sizes()
        self.desktop = desktops[0] if desktops else None
        self.windowed_size = self.fit_window(preferred_size)
        self.screen = None
        self.fullscreen = False

    def fit_window(self, requested):
        if self.desktop is None:
            return requested
        # Keep the taskbar, the title bar, and a little breathing room outside the window.
        work = (max(1, self.desktop[0] - 48), max(1, self.desktop[1] - 86))
        return viewport(tuple(min(length, available) for length, available in zip(requested, work))).size

    def show(self, fullscreen):
        if self.screen is not None and not self.fullscreen and fullscreen:
            self.windowed_size = self.fit_window(self.screen.get_size())
        if fullscreen:
            try:
                self.screen = pg.display.set_mode(self.desktop or (0, 0), pg.FULLSCREEN)
                self.fullscreen = True
                return
            except pg.error:
                pass
        self.screen = pg.display.set_mode(self.windowed_size, pg.RESIZABLE)
        if self.screen.get_size() != self.windowed_size:
            # Some SDL drivers report the old fullscreen size on the first call.
            self.screen = pg.display.set_mode(self.windowed_size, pg.RESIZABLE)
        self.fullscreen = False


def clover_mark(canvas, x, y, color):
    paint.line(canvas, color, (x+1, y+1), (x-3, y+7), 1.6)
    for dx, dy in ((-4.5, -1), (4.5, -1), (0, -5.4)):
        oval(canvas, color, x+dx, y+dy, 3.8, 3.8)


class CloverApp:
    def __init__(self, garden):
        self.garden = garden
        self.frame = None
        self.tab = GARDEN_TAB
        self.seed_pot = None
        self.fullscreen = garden.fullscreen
        self.display_requested = False
        self.scroll_positions = [0.0] * len(TAB_PAGE)
        self.scroll = 0.0
        self.drag_offset = None
        self.pointer = (-1, -1)
        self.hover = 0.0
        self.tick = 0.0
        self.bounce = self.bee_at = self.visit_at = -100.0
        self.next_visit = 18.0
        self.last_save = 0.0
        self.wall_time = time.time()
        self.visitor_kind = "butterfly"
        self.effects = []
        self.previous_background = None
        self.transition_at = -100.0
        self.status = None
        self.arcade = None
        self.arcade_key = None
        self.arcade_mode = None
        self.play_choice = None
        self.arcade_reward = None
        self.result_at = -100
        self.secret_match = False
        self.rare_match = None
        self.festival_round = False
        self.festival_stamp = False
        self.saved_ghost = False
        self.known_rares = garden.yard.rare_finds()
        self.pot_effects = {}
        self.tab_changed = -100
        self.pick_press = -100
        self.yard_view = YardView(garden.yard)
        self.resize(SIZE)
        if garden.offline_clover:
            self.status = (f"+{compact(garden.offline_clover)} while away", 4.5)

    def resize(self, pixels):
        if self.frame is not None and self.frame.pixels == pixels:
            return
        self.frame = Canvas(SIZE, pixels)
        scene_pixels = self.frame.rect(SCENE).size
        scene_pixels = tuple(max(1, dim) for dim in scene_pixels)
        self.scene = Canvas((WIDTH, HEIGHT), scene_pixels, alpha=True)
        self.mask = Canvas((WIDTH, HEIGHT), scene_pixels, alpha=True)
        paint.rect(self.mask, (255, 255, 255, 255), self.mask.get_rect(), border_radius=14)
        self.menu_veil = Canvas(LIST.size, tuple(max(1, value) for value in self.frame.rect(LIST).size))
        self.menu_veil.fill(PAPER)
        self.fonts = {key: pg.font.SysFont(("segoeui", "arial"), self.frame.units(size), bold=bold)
                      for key, (size, bold) in FONT_SPECS.items()}
        self.scene_fonts = {key: pg.font.SysFont(("segoeui", "arial"), self.scene.units(size), bold=bold)
                            for key, (size, bold) in SCENE_FONTS.items()}
        self.text.cache_clear()
        backdrop.cache_clear()
        self.previous_background = None

    @lru_cache(maxsize=512)
    def text(self, value, font, color, in_scene=False):
        fonts = self.scene_fonts if in_scene else self.fonts
        return fonts[font].render(value, True, color)

    def label(self, value, pos, font="small", color=INK, anchor="topleft", target=None):
        image = self.text(value, font, color, target is self.scene)
        (self.frame if target is None else target).text(image, pos, anchor)

    def fit_text(self, value, font, width):
        measure = self.fonts[font].size
        width *= self.frame.sx
        if measure(value)[0] <= width:
            return value
        while value and measure(value + "…")[0] > width:
            value = value[:-1]
        return value.rstrip() + "…"

    def paragraph(self, value, pos, width, lines=3, color=MUTED):
        words = value.split()
        x, y = pos
        for index in range(lines):
            if not words:
                break
            line = words.pop(0)
            while words and self.fit_text(line + " " + words[0], "small", width) == line + " " + words[0]:
                line += " " + words.pop(0)
            if index == lines - 1 and words:
                line = self.fit_text(line + "…", "small", width)
            self.label(line, (x, y + index * 20), color=color)

    def yard_page(self):
        return self.yard_view.page if self.tab == YARD_TAB else None

    def page_key(self):
        return self.yard_page() or TAB_PAGE[self.tab]

    def rows(self, now):
        garden = self.garden
        if self.tab == 0:
            for index, (name, effect, _) in enumerate(UPGRADES):
                level, price = garden.levels[index], garden.cost(index)
                detail = f"{effect}  ·  Lv. {level}" if level else effect
                yield index, name, detail, "Max" if level == MAX_LEVEL else f"{compact(price)} clover", (
                    level < MAX_LEVEL and garden.clover >= price), None
        elif self.tab == GARDEN_TAB:
            if self.seed_pot is None:
                for index, planted in enumerate(garden.plots):
                    detail, action, enabled = garden.crop_status(index, now)
                    name = "Moon Pot" if index == 3 else f"Pot {index + 1}"
                    yield index, name, detail, action, enabled, garden.yard.flower_info(planted[3])[1] if planted else None
            else:
                for key in garden.seed_options():
                    name, color = garden.yard.flower_info(key)
                    count = garden.yard.seeds.get(key, 0)
                    rarity = "Rare  ·  " if key in RARE_SEEDS else ""
                    detail = f"{rarity}{garden.crop_duration(key)}s  ·  +{compact(garden.crop_reward(key))}"
                    if count:
                        detail += f"  ·  {compact(count)} in bag"
                    price = garden.seed_spec(key).price
                    yield key, name, detail, "Use seed" if count else f"{compact(price)} clover", bool(count) or garden.clover >= price, color
        elif self.tab == 2:
            for key, style in STYLES.items():
                equipped, owned = key == garden.style_key, key in garden.unlocked
                can_equip = garden.can_equip(key)
                if equipped:
                    action = "Equipped"
                elif owned or (style.currency == "discovery" and can_equip):
                    action = "Equip"
                elif style.currency == "discovery":
                    action = "Rare finds"
                else:
                    action = f"{compact(style.price)} {style.currency}"
                yield key, style.name, "Grow all 3 rare plants" if style.currency == "discovery" else "", action, can_equip, style.leaves
        elif self.tab == 3:
            for key, (name, unit, target, reward) in MILESTONES.items():
                value, claimed = min(target, garden.milestone_value(unit)), key in garden.claimed
                yield key, name, f"{compact(value)}/{compact(target)} {unit}  ·  +{compact(reward)}", (
                    "Claimed" if claimed else f"Claim +{compact(reward)}"), not claimed and value == target, None
        elif self.tab == PLAY_TAB:
            if self.play_choice is not None:
                for key in self.play_modes():
                    mode = MODES[key]
                    best = garden.mode_scores[self.play_choice][key]
                    detail = mode.rate + (f"  ·  Best {compact(best)}" if best else "")
                    ghost = garden.yard.estate.ghosts.get(key) if self.play_choice == "hopping" else None
                    if ghost:
                        detail += f"  ·  Ghost {ghost['duration']:.2f}s"
                    yield key, mode.name, detail, "Race ghost" if ghost else "Start", True, "#c993a6" if key == "impossible" else None
            else:
                for key, name in GAMES.items():
                    best = garden.best_scores[key]
                    if key == "fishing" and "pond" not in garden.yard.zones:
                        yield key, name, "Unlock the Lily Pond in Yard", "Find pond", True, None
                    else:
                        yield key, name, f"{GAME_DETAILS[key]}  ·  Best {compact(best)}" if best else GAME_DETAILS[key], "Modes", True, None
                yield "exchange", "Ticket Exchange", f"{TICKET_COST} tickets for {CLOVER_EXCHANGE} clover", (
                    "Trade"), garden.tickets >= TICKET_COST, "#d9a25e"
        else:
            yield from self.yard_view.rows(now)

    def row_count(self):
        if self.play_choice is not None:
            return len(self.play_modes())
        if self.tab == GARDEN_TAB and self.seed_pot is not None:
            return sum(1 for _ in self.garden.seed_options())
        if self.tab == GARDEN_TAB:
            return len(self.garden.plots)
        if self.tab == YARD_TAB:
            return sum(1 for _ in self.yard_view.rows(self.wall_time))
        return ROW_COUNTS[self.tab]

    def play_modes(self):
        return tuple(key for key in MODES if key != "impossible" or self.garden.impossible_unlocked())

    def row_step(self):
        return ROW_HEIGHT

    def scroll_max(self):
        return max(0, self.row_count() * self.row_step() - 2 - LIST.height)

    def scrollbar(self):
        maximum = self.scroll_max()
        height = max(24, round(TRACK.height * LIST.height / (LIST.height + maximum)))
        top = TRACK.y + round((TRACK.height - height) * self.scroll / maximum) if maximum else TRACK.y
        return pg.Rect(TRACK.x, top, TRACK.width, height)

    def set_scroll(self, value):
        self.scroll_positions[self.tab] = max(0, min(value, self.scroll_max()))

    def select_tab(self, index):
        if index != self.tab:
            if self.tab == GARDEN_TAB and self.seed_pot is not None:
                self.set_seed_pot(None)
            if self.tab == PLAY_TAB and self.play_choice is not None:
                self.set_play_choice(None)
            self.tab = index
            self.scroll = self.scroll_positions[index]
            self.drag_offset = None
            self.tab_changed = self.tick
            if index == YARD_TAB and self.yard_view.page is None:
                self.set_yard_page("breed")

    def navigate(self, tab, page=None):
        self.select_tab(tab)
        if tab == YARD_TAB:
            self.set_yard_page(page or "breed")
        elif tab == GARDEN_TAB and self.seed_pot is not None:
            self.set_seed_pot(None)
        elif tab == PLAY_TAB and self.play_choice is not None:
            self.set_play_choice(None)

    def effect(self, value, color=GOLD, point=CLOVER, bounce=False):
        if bounce:
            self.bounce = self.tick
        offset = (0, 16, -16, 30, -30)[len(self.effects) % 5]
        self.effects.append((self.tick, value, color, point[0] + offset, point[1]))
        self.effects = self.effects[-36:]

    def pick(self):
        self.pick_press = self.tick
        amount, bonus = self.garden.pick()
        self.effect(f"+{compact(amount)}", GOLD if bonus else GREEN, bounce=True)

    def tend(self, index, now):
        if self.garden.plots[index] is None:
            self.select_tab(GARDEN_TAB)
            self.set_seed_pot(index)
            return
        result = self.garden.tend(index, now)
        if result:
            x, y = pot_positions(len(self.garden.plots))[index]
            self.pot_effects[index] = ("water" if result == "Watered" else "harvest", self.tick)
            self.effect(result, "#466f8e" if result == "Watered" else GOLD, (x, y - 30))
            if self.seed_pot is not None and self.garden.plots[self.seed_pot] is not None:
                self.set_seed_pot(None)

    def set_seed_pot(self, index):
        self.seed_pot = index
        self.set_scroll(0)
        self.scroll = 0
        self.drag_offset = None

    def set_yard_page(self, page):
        self.yard_view.projects.cancel_decoration()
        self.yard_view.leave()
        self.yard_view.page = page
        self.set_scroll(0)
        self.scroll = 0
        self.tab_changed = self.tick

    def close_yard_page(self):
        self.yard_view.projects.cancel_decoration()
        self.navigate(GARDEN_TAB)

    def decoration_active(self):
        editor = self.yard_view.projects
        return self.yard_page() == "showcase" and (editor.placing is not None or editor.selected_piece() is not None)

    def set_play_choice(self, key):
        self.play_choice = key
        self.set_scroll(0)
        self.scroll = 0
        self.drag_offset = None
        self.tab_changed = self.tick

    def row_action(self, key, now):
        if self.tab == 0 and self.garden.buy(key):
            self.effect("Upgraded", bounce=True)
        elif self.tab == GARDEN_TAB:
            if self.seed_pot is None:
                self.tend(key, now)
            else:
                index = self.seed_pot
                if self.garden.plant(index, key, now):
                    x, y = pot_positions(len(self.garden.plots))[index]
                    self.pot_effects[index] = ("plant", self.tick)
                    self.set_seed_pot(None)
                    self.effect("Planted", GREEN, (x, y - 26))
        elif self.tab == 2:
            previous = self.garden.style_key
            if self.garden.choose_style(key):
                self.previous_background = backdrop(previous, self.scene.pixels).copy()
                self.transition_at = self.tick
                self.bounce = self.tick
        elif self.tab == 3:
            reward = self.garden.claim(key)
            if reward:
                self.effect(f"+{compact(reward)}", bounce=True)
        elif self.tab == PLAY_TAB:
            if self.play_choice is not None:
                self.start_arcade(self.play_choice, key)
            elif key == "exchange":
                reward = self.garden.exchange_tickets()
                if reward:
                    self.effect(f"+{compact(reward)}", bounce=True)
            elif key == "fishing" and "pond" not in self.garden.yard.zones:
                self.select_tab(YARD_TAB)
                self.set_yard_page("zones")
            else:
                self.set_play_choice(key)
        elif self.tab == YARD_TAB:
            before = self.yard_view.page
            had_preview = self.yard_view.preview is not None
            result = self.yard_view.activate(key, now, self.tick)
            if result:
                action, value = result
                if action == "trial":
                    self.start_arcade(value, festival=True)
                elif action == "moon_pot":
                    self.select_tab(GARDEN_TAB)
                    if self.garden.plots[value] is None:
                        self.set_seed_pot(value)
            nested = before in ESTATE_PAGES and isinstance(key, tuple) and key[0] in ("tree", "request", "pot")
            if nested or before != self.yard_view.page or (before == "breed" and not had_preview and self.yard_view.preview):
                self.set_scroll(0)
                self.scroll = 0

    def start_arcade(self, key, mode="medium", festival=False):
        if key == "fishing" and "pond" not in self.garden.yard.zones:
            return
        if mode not in self.play_modes():
            return
        estate = self.garden.yard.estate
        if festival and (not estate.festival_open or key not in FESTIVAL_TRIALS):
            return
        self.arcade_key = key
        self.arcade_mode = mode
        self.arcade = MushroomHop(mode=mode, ghost=estate.ghosts.get(mode)) if key == "hopping" else GAME_TYPES[key](mode=mode)
        self.festival_round = festival
        if festival:
            self.arcade.festival = True
        self.festival_stamp = False
        self.saved_ghost = False
        self.arcade_reward = None
        self.secret_match = False
        self.rare_match = None

    def notice_rares(self):
        latest = self.garden.yard.rare_finds()
        new = latest - self.known_rares
        self.known_rares = latest
        if not new:
            return
        key = "moon_garden" if "moon_garden" in new else "aurora" if "aurora" in new else sorted(new)[0]
        text = ("Moon Garden opened! You have a fourth pot." if key == "moon_garden" else
                "Aurora Garden unlocked!" if key == "aurora" else
                f"Rare find: {STICKERS[key][0]}" + (" seed" if key in RARE_SEEDS else ""))
        if self.arcade is not None:
            self.rare_match = text
        else:
            self.status = (text, self.tick + 4.2)

    def finish_arcade(self):
        if self.arcade.done and self.arcade_reward is None:
            unlocked = self.garden.impossible_unlocked()
            self.arcade_reward = self.garden.record_round(self.arcade_key, self.arcade.score, self.arcade_mode)
            self.secret_match = not unlocked and self.garden.impossible_unlocked()
            self.result_at = self.tick
            estate = self.garden.yard.estate
            if self.festival_round:
                self.festival_stamp = estate.festival_game(self.arcade_key, self.arcade.score)
            if isinstance(self.arcade, MushroomHop):
                cleared = self.arcade.finish is not None and self.arcade.farthest >= self.arcade.finish
                self.saved_ghost = estate.keep_ghost(self.arcade_mode, self.arcade.time, self.arcade.score, self.arcade.trace, cleared)
            if isinstance(self.arcade, PondFishing):
                for prize in self.arcade.catches:
                    self.garden.yard.catch(prize)
                if self.arcade_mode in ("hard", "impossible") and self.arcade.catches.count("lily_seed") >= 3:
                    self.garden.yard.discover("silver_pearl")
            elif (isinstance(self.arcade, MushroomHop) and self.arcade_mode in ("hard", "impossible")
                  and self.arcade.finish is not None and self.arcade.farthest >= self.arcade.finish):
                self.garden.yard.grant_rare_seed("dewglass")
            self.notice_rares()

    def return_to_garden(self):
        if self.arcade_mode == "endless" and not self.arcade.done:
            self.arcade.done = True
            self.finish_arcade()
            self.status = (f"+{compact(self.arcade_reward[0])} tickets", self.tick + 2)
        self.finish_arcade()
        self.arcade = self.arcade_key = self.arcade_mode = self.arcade_reward = None

    def handle_arcade(self, event):
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            if PICK.collidepoint(self.pointer):
                self.return_to_garden()
            elif self.arcade.done and REPLAY.collidepoint(self.pointer):
                self.start_arcade(self.arcade_key, self.arcade_mode, self.festival_round)
            elif self.arcade_mode == "endless" and REPLAY.collidepoint(self.pointer):
                self.arcade.done = True
                self.finish_arcade()
            elif isinstance(self.arcade, (FireflyTrail, CloverPop)) and SCENE.collidepoint(self.pointer):
                self.arcade.click(*scene_point(self.pointer))
                self.finish_arcade()
            elif isinstance(self.arcade, PondFishing) and SCENE.collidepoint(self.pointer):
                self.arcade.press()
                self.finish_arcade()
            elif isinstance(self.arcade, MushroomHop) and SCENE.collidepoint(self.pointer):
                self.arcade.jump()
        elif event.type == pg.MOUSEMOTION and isinstance(self.arcade, PetalCatch) and SCENE.collidepoint(self.pointer):
            self.arcade.aim(scene_point(self.pointer)[0])
        elif event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                self.return_to_garden()
            elif self.arcade.done and event.key in (pg.K_RETURN, pg.K_SPACE):
                self.start_arcade(self.arcade_key, self.arcade_mode, self.festival_round)
            elif isinstance(self.arcade, PetalCatch) and event.key in (pg.K_LEFT, pg.K_RIGHT):
                self.arcade.keys.add(event.key)
            elif isinstance(self.arcade, FireflyTrail) and pg.K_1 <= event.key <= pg.K_4:
                self.arcade.press(event.key - pg.K_1)
                self.finish_arcade()
            elif isinstance(self.arcade, PondFishing) and event.key == pg.K_SPACE:
                self.arcade.press()
                self.finish_arcade()
            elif isinstance(self.arcade, MushroomHop) and event.key in (pg.K_SPACE, pg.K_UP):
                self.arcade.jump()
            elif isinstance(self.arcade, MushroomHop) and event.key == pg.K_LEFT:
                self.arcade.keys.add(event.key)
        elif isinstance(self.arcade, (PetalCatch, MushroomHop)):
            if event.type == pg.KEYUP:
                self.arcade.keys.discard(event.key)
            elif event.type == pg.WINDOWFOCUSLOST:
                self.arcade.keys.clear()

    def visit_active(self):
        return 0 <= self.tick - self.visit_at < VISIT_TIME

    def scene_click(self, pos, now):
        x, y = scene_point(pos)
        if self.visit_active():
            bx, by = butterfly_pos(self.tick - self.visit_at)
            if abs(x - bx) <= 20 and abs(y - by) <= 16:
                self.visit_at = -100.0
                reward = self.garden.greet_visitor(self.visitor_kind)
                self.effect(f"+{compact(reward)}", point=(bx, by + 12))
                return
        if self.garden.yard.snail and abs(x - self.snail_x()) < 22 and abs(y - 180) < 16:
            message = self.garden.yard.gift(now) or self.garden.yard.snail
            self.effect(message, point=(72, 169))
            return
        for index, rect in enumerate(pot_hitboxes(len(self.garden.plots))):
            if rect.collidepoint(x, y):
                self.tend(index, now)
                return
        self.pick()

    def row_rects(self):
        step = self.row_step()
        for index in range(self.row_count()):
            row = pg.Rect(LIST.x, LIST.y + index * step - round(self.scroll), LIST.width - 13, step - 3)
            button = pg.Rect(row.right - 95, row.y + 3, 90, 24)
            yield row, button

    def click(self, pos, now):
        yard_page = self.yard_page()
        if NAV.collidepoint(pos):
            for tab, page, _, rect in nav_rows(self.garden.yard.estate.moon):
                if tab is not None and rect.collidepoint(pos):
                    self.navigate(tab, page)
                    return
        elif SCENE.collidepoint(pos):
            if yard_page:
                self.yard_view.click_scene(*scene_point(pos), self.tick)
            elif self.play_choice is None:
                self.scene_click(pos, now)
        elif PICK.collidepoint(pos):
            if yard_page:
                if self.decoration_active():
                    self.yard_view.projects.cancel_decoration()
                else:
                    self.close_yard_page()
            elif self.seed_pot is not None:
                self.set_seed_pot(None)
            elif self.play_choice is not None:
                self.set_play_choice(None)
            else:
                self.pick()
        elif LIST.collidepoint(pos):
            if pos[0] >= TRACK.x - 4 and self.scroll_max():
                thumb = self.scrollbar()
                self.drag_offset = pos[1] - thumb.top if thumb.collidepoint(pos) else thumb.height / 2
                self.drag_scroll(pos[1])
                return
            for (row, button), (key, _, _, _, enabled, _) in zip(self.row_rects(), self.rows(now)):
                target = row if self.seed_pot is not None or self.play_choice is not None or yard_page == "showcase" else button
                if enabled and target.collidepoint(pos):
                    self.row_action(key, now)
                    return

    def drag_scroll(self, y):
        distance = TRACK.height - self.scrollbar().height
        if distance > 0:
            self.set_scroll((y - self.drag_offset - TRACK.top) / distance * self.scroll_max())

    def handle(self, event, area, now):
        if event.type == pg.QUIT:
            return False
        if event.type in (pg.MOUSEMOTION, pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP) and hasattr(event, "pos"):
            x, y = event.pos
            self.pointer = ((x - area.left) * SIZE[0] / area.width, (y - area.top) * SIZE[1] / area.height)
        elif event.type == pg.WINDOWLEAVE:
            self.pointer = (-1, -1)
        if ((event.type == pg.KEYDOWN and event.key == pg.K_F11)
                or (event.type == pg.MOUSEBUTTONDOWN and event.button == 1 and DISPLAY_MODE.collidepoint(self.pointer))):
            self.display_requested = True
            return True
        if self.arcade is not None:
            self.handle_arcade(event)
            return True
        if self.yard_view.editing:
            if event.type == pg.MOUSEBUTTONDOWN and event.button == 1 and (PICK.collidepoint(self.pointer) or NAV.collidepoint(self.pointer)):
                self.yard_view.leave()
                if PICK.collidepoint(self.pointer):
                    self.close_yard_page()
                else:
                    self.click(self.pointer, now)
            else:
                self.yard_view.on_text(event, now, self.tick)
            return True
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            self.click(self.pointer, now)
        elif event.type == pg.MOUSEBUTTONUP and event.button == 1:
            self.drag_offset = None
            if self.tab == YARD_TAB:
                self.yard_view.release_scene(*scene_point(self.pointer))
        elif event.type == pg.MOUSEMOTION and self.drag_offset is not None:
            self.drag_scroll(self.pointer[1])
        elif event.type == pg.MOUSEWHEEL and LIST.inflate(12, 20).collidepoint(self.pointer):
            self.set_scroll(self.scroll_positions[self.tab] - event.y * self.row_step())
        elif event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE and self.decoration_active():
                self.yard_view.projects.cancel_decoration()
            elif event.key == pg.K_ESCAPE and self.seed_pot is not None:
                self.set_seed_pot(None)
            elif event.key == pg.K_ESCAPE and self.play_choice is not None:
                self.set_play_choice(None)
            elif event.key == pg.K_ESCAPE and self.tab == YARD_TAB and self.yard_view.page:
                self.close_yard_page()
            elif event.key == pg.K_ESCAPE and self.fullscreen:
                self.display_requested = True
            elif event.key == pg.K_SPACE and self.play_choice is None and not (self.tab == YARD_TAB and self.yard_view.page):
                self.pick()
            elif pg.K_1 <= event.key <= pg.K_6:
                self.navigate(event.key - pg.K_1)
            elif event.key in (pg.K_PAGEUP, pg.K_PAGEDOWN):
                move = -2 if event.key == pg.K_PAGEUP else 2
                self.set_scroll(self.scroll_positions[self.tab] + self.row_step() * move)
        return True

    def update(self, elapsed, now=None):
        self.wall_time = now = time.time() if now is None else now
        self.tick += elapsed
        speed = 1 - math.exp(-elapsed * 16)
        if self.tab == YARD_TAB or self.seed_pot is not None:
            self.set_scroll(self.scroll_positions[self.tab])
            self.scroll = min(self.scroll, self.scroll_max())
        self.scroll += (self.scroll_positions[self.tab] - self.scroll) * speed
        self.hover += (PICK.collidepoint(self.pointer) - self.hover) * speed
        self.garden.apply_weather(now)
        if self.garden.advance_bees(elapsed, now):
            self.bee_at = self.tick
        if self.tick >= self.next_visit:
            self.visit_at = self.tick
            self.next_visit = self.tick + 35
            self.visitor_kind = "moth" if self.garden.yard.weather(now)[0] == "Fog" else "butterfly"
        if self.arcade is not None and not self.arcade.done:
            self.arcade.update(min(elapsed, .1))
            self.finish_arcade()
        self.notice_rares()
        if self.tick - self.last_save >= 10:
            self.garden.save(now)
            self.last_save = self.tick
        self.effects = [effect for effect in self.effects if self.tick - effect[0] < .78]
        self.pot_effects = {index: event for index, event in self.pot_effects.items() if self.tick - event[1] < .72}

    def draw_scene(self, now):
        scene = self.scene
        scene.blit(backdrop(self.garden.style_key, scene.pixels), (0, 0))
        if self.previous_background is not None:
            fade = 1 - min(1, (self.tick - self.transition_at) / .36)
            if fade:
                self.previous_background.set_alpha(round(255 * fade * fade))
                scene.blit(self.previous_background, (0, 0))
            else:
                self.previous_background = None
        draw_clover(scene, self.garden.style_key, self.tick, self.bounce)
        draw_showcase(scene, self.garden.yard, self.tick)
        draw_pots(scene, self.garden, now, self.tick, self.seed_pot, self.pot_effects)
        if self.tab == GARDEN_TAB:
            for index, (x, y) in enumerate(pot_positions(len(self.garden.plots))):
                oval(scene, "#fff6e7", x - 27, y + 2, 7, 7)
                self.label(str(index + 1), (x - 27, y + 2), color=INK, anchor="center", target=scene)
        if self.garden.yard.snail:
            draw_snail(scene, self.snail_x(), 180, self.garden.yard.hat, .84)
        weather, _ = self.garden.yard.weather(now)
        if weather == "Rain":
            for i in range(16):
                x = (21 + 47 * i - self.tick * 18) % WIDTH
                y = (37 * i + self.tick * (71 + i % 4 * 5)) % HEIGHT
                paint.line(scene, "#a6c1bf", (x, y), (x - 3, y + 9), .7)
        elif weather == "Fog":
            for i in range(4):
                oval(scene, "#dfddd3", 62 + 83*i + 19*math.sin(self.tick * .4+i), 45+19*i, 36, 1.5)
        else:
            light = "#edda9b" if self.garden.style_key in ("moonlight", "lantern", "aurora") else "#fff0c7"
            for i in range(5):
                age = self.tick * (.5 + i * .09) + i * 1.7
                x = (29 + i * 97 + self.tick * (5 + i)) % WIDTH
                y = 78 + 18 * i + 9 * math.sin(age)
                radius = 1.25 + .7 * math.sin(age * 2)
                oval(scene, light, x, y, radius, radius)
        if self.visit_active():
            draw_butterfly(scene, self.tick - self.visit_at, self.visitor_kind)
        if self.tick - self.bee_at < .8:
            draw_bee(scene, self.tick - self.bee_at)
        for started, value, color, x, y in self.effects:
            age = (self.tick - started) / .78
            fade = 1 - max(0, (age - .36) / .64)
            rise = 39 * (1 - (1 - age) ** 2)
            dark = self.garden.style_key in ("moonlight", "lantern", "aurora")
            image = self.text(value, "pick", PAPER if dark else color, True).copy()
            image.set_alpha(round(fade * 255))
            scene.text(image, (x, max(12, y - 21 - rise)), "center")
            if age < .48:
                for angle in (0.65, 3.75):
                    radius = 9 + age * 46
                    sparkle(scene, "#fff2ca", x + math.cos(angle) * radius, y - 12 + math.sin(angle) * radius, 3)
        if self.status is not None:
            value, until = self.status
            if self.tick < until:
                width = self.text(value, "small", INK, True).get_width() / scene.sx + 20
                rect = (WIDTH / 2 - width / 2, 9, width, 23)
                paint.rect(scene, PAPER, rect, border_radius=9)
                self.label(value, (WIDTH / 2, 20.5), anchor="center", target=scene)
            else:
                self.status = None
        if self.yard_page() == "showcase":
            self.yard_view.projects.draw_decoration_tools(scene, scene_point(self.pointer), self.tick)
            self.yard_view.draw_message(scene, self.scene_label, self.tick)
        self.present_scene()

    def scene_label(self, value, pos, font="small", color=INK, anchor="topleft"):
        self.label(value, pos, font, color, anchor, self.scene)

    def present_scene(self):
        self.scene.blit(self.mask, (0, 0), special_flags=pg.BLEND_RGBA_MULT)
        paint.rect(self.frame, "#e5e8dd", SCENE.move(0, 2), border_radius=14)
        self.frame.blit(self.scene, SCENE)

    def snail_x(self):
        if self.garden.yard.estate.moon:
            return 29 + 8 * math.sin(self.tick * .6)
        return 36 + 15 * math.sin(self.tick * .6)

    def draw_sidebar(self):
        frame = self.frame
        paint.rect(frame, PAPER, NAV, border_radius=14)
        paint.rect(frame, LINE, NAV, 1, border_radius=14)
        ready = any(key not in self.garden.claimed and self.garden.milestone_value(unit) >= target
                    for key, (_, unit, target, _) in MILESTONES.items())
        for tab, page, title, rect in nav_rows(self.garden.yard.estate.moon):
            if tab is None:
                self.label(title.upper(), (rect.x + 4, rect.y), "group", MUTED)
                continue
            active = self.tab == tab and self.yard_page() == page
            hover = self.arcade is None and rect.collidepoint(self.pointer)
            if active or hover:
                paint.rect(frame, MINT if active else "#f0f4eb", rect, border_radius=6)
            self.label(title, (rect.x + 10, rect.centery), "button" if active else "small",
                       GREEN if active else INK, "midleft")
            if tab == 3 and ready:
                oval(frame, "#ca9757", rect.right - 13, rect.centery, 3, 3)

    def draw_panel_header(self, title, description):
        paint.rect(self.frame, PAPER, PANEL, border_radius=14)
        paint.rect(self.frame, LINE, PANEL, 1, border_radius=14)
        x = PANEL.x + 17
        self.label(self.fit_text(title, "heading", PANEL.width - 34), (x, PANEL.y + 15), "heading")
        self.paragraph(description, (x, PANEL.y + 45), PANEL.width - 34, lines=2)
        paint.line(self.frame, LINE, (x, LIST.y - 7), (PANEL.right - 17, LIST.y - 7))

    def draw_shop(self, now):
        frame = self.frame
        title, description, _ = GUIDES.get(self.page_key(), ("Activities", "Choose what to do next.", ""))
        if self.seed_pot is not None:
            title, description = "Choose a seed", "Seeds already in your bag are listed first."
        elif self.play_choice is not None:
            title, description = "Choose a mode", "Harder modes pay more tickets. Endless lets you cash out."
        self.draw_panel_header(title, description)
        frame.set_clip(LIST)
        for (rect, button), (_, title, detail, action, enabled, swatch) in zip(self.row_rects(), self.rows(now)):
            if not rect.colliderect(LIST):
                continue
            target = rect if self.seed_pot is not None or self.play_choice is not None or self.yard_page() == "showcase" else button
            hovered = enabled and target.collidepoint(self.pointer) and LIST.collidepoint(self.pointer)
            if hovered:
                paint.rect(frame, "#f1f5ed", rect, border_radius=7)
            if rect.bottom + 1 < LIST.bottom and rect.bottom + 1 >= LIST.top:
                paint.line(frame, LINE, (rect.left + 5, rect.bottom + 1), (rect.right - 3, rect.bottom + 1))
            x = rect.x + 10
            mark_y = rect.y + 15
            if isinstance(swatch, tuple) and isinstance(swatch[0], str):
                for (dx, dy), color in zip(((5, 3), (15, 3), (10, -4)), swatch):
                    oval(frame, color, x + dx * .8, mark_y + dy * .8, 4, 4)
                x += 21
            elif swatch:
                oval(frame, swatch, x + 4, mark_y, 4, 4)
                x += 14
            width = button.left - x - 6
            title = self.fit_text(title, "row", width)
            self.label(title, (x, mark_y), "row", anchor="midleft")
            if detail:
                self.label(self.fit_text(detail, "small", rect.width - 18), (rect.x + 10, rect.y + 28), color=MUTED)
            color = "#d4e5d1" if hovered else MINT if enabled else "#eef0ea"
            paint.rect(frame, color, button, border_radius=7)
            self.label(self.fit_text(action, "button", button.width - 6), button.center, "button",
                       GREEN if enabled else MUTED, "center")
        frame.set_clip(None)
        age = self.tick - self.tab_changed
        if 0 <= age < .22:
            self.menu_veil.set_alpha(round(95 * (1 - age / .22)**2))
            frame.blit(self.menu_veil, LIST)
        if self.scroll_max():
            paint.rect(frame, "#eef0ea", TRACK, border_radius=3)
            paint.rect(frame, "#a6b6a3", self.scrollbar(), border_radius=3)

    def draw_arcade(self):
        self.arcade.draw(self.scene, self.scene_label)
        x = PANEL.x + 18
        width = PANEL.width - 36
        if self.arcade_reward is None:
            mode = MODES[self.arcade_mode]
            line = f"All gold! Festival goal: {FESTIVAL_TRIALS[self.arcade_key]} points" if self.festival_round else f"{mode.name}  ·  {mode.rate}"
            self.draw_panel_header("How to play", line)
            for index, line in enumerate(self.arcade.hint):
                self.paragraph(line, (x, 204 + index * 60), width, lines=3, color=INK)
            if self.arcade_mode == "endless":
                paint.rect(self.frame, GREEN, REPLAY, border_radius=8)
                self.label("Cash out", REPLAY.center, "button", PAPER, "center")
        else:
            self.draw_panel_header("Round results", "Your progress and tickets are saved.")
            earned, best = self.arcade_reward
            t = min(1, (self.tick - self.result_at) / .28)
            drop = round(-19 * (1 - t)**3)
            card = pg.Rect(64, 62 + drop, WIDTH - 128, 102)
            paint.rect(self.scene, PAPER, card, border_radius=14)
            heading = "New best!" if best else (getattr(self.arcade, "result", "") or "Round complete")
            self.scene_label(heading, (card.centerx, 84 + drop), "row", INK, "center")
            self.scene_label(f"{compact(self.arcade.score)} points", (card.centerx, 116 + drop), "title", INK, "center")
            self.scene_label(f"+{compact(earned)} tickets", (card.centerx, 145 + drop), "button", GOLD, "center")
            self.label(f"{MODES[self.arcade_mode].name} best: {compact(self.garden.mode_scores[self.arcade_key][self.arcade_mode])} pts",
                       (x, 203), "row")
            messages = []
            if isinstance(self.arcade, PondFishing) and self.arcade.catches:
                prizes = ", ".join(STICKERS[k][0] for k in dict.fromkeys(self.arcade.catches))
                messages.append(prizes)
            if self.secret_match:
                messages.append("A hidden mode unlocked!")
            if self.rare_match:
                messages.append(self.rare_match)
            if self.festival_stamp:
                messages.append("Festival game stamp earned!")
            elif self.saved_ghost:
                messages.append("New ghost run saved!")
            for index, message in enumerate(messages):
                self.paragraph(message, (x, 242 + 30 * index), width, lines=2)
            paint.rect(self.frame, GREEN, REPLAY, border_radius=8)
            self.label("Play again", REPLAY.center, "button", PAPER, "center")
        self.present_scene()

    def draw_mode_preview(self):
        scene = self.scene
        scene.fill("#e3ecdc")
        oval(scene, "#cbdcc3", 110, 241, 230, 76)
        oval(scene, "#bccfb5", 340, 254, 210, 72)
        y = 63 + 3 * math.sin(self.tick * 2.8)
        oval(scene, "#f7f8ed", WIDTH/2, y, 27, 27)
        clover_mark(scene, WIDTH/2, y + 1, GREEN)
        for x, dy, delay in ((135, -8, 0), (239, 13, .9), (149, 22, 2)):
            sparkle(scene, "#d5bd78", x, y + dy, 3 + 1.5 * math.sin(self.tick * 4 + delay))
        self.label(GAMES[self.play_choice], (WIDTH/2, 116), "title", INK, "center", scene)
        mode = next((MODES[key] for key, (row, _) in zip(self.play_modes(), self.row_rects())
                     if LIST.collidepoint(self.pointer) and row.collidepoint(self.pointer)), None)
        self.label(mode.note if mode else "Choose a mode", (WIDTH/2, 151), "row", MUTED, "center", scene)
        self.present_scene()

    def draw_header(self, now):
        paint.rect(self.frame, MINT, (20, 20, 47, 47), border_radius=12)
        clover_mark(self.frame, 44, 44, GREEN)
        self.label("Clover Patch", (80, 17), "title")
        weather, _ = self.garden.yard.weather(now)
        self.label(f"{STYLES[self.garden.style_key].name} · {weather}", (82, 50), color=MUTED)

        hover = DISPLAY_MODE.collidepoint(self.pointer)
        paint.rect(self.frame, MINT if hover else PAPER, DISPLAY_MODE, border_radius=9)
        paint.rect(self.frame, LINE, DISPLAY_MODE, 1, border_radius=9)
        switch = "Exit fullscreen" if self.fullscreen else "Fullscreen"
        self.label(switch, (DISPLAY_MODE.x + 10, DISPLAY_MODE.centery), "button", GREEN, "midleft")
        self.label("F11", (DISPLAY_MODE.right - 9, DISPLAY_MODE.centery), "group", MUTED, "midright")
        right = DISPLAY_MODE.left - 12
        status = (f"{compact(self.garden.clover)} clover", f"{compact(self.garden.tickets)} tickets")
        for i, value in enumerate(status):
            ink, fill = (GREEN, MINT) if i == 0 else (GOLD, "#f3ebd9")
            width = self.text(value, "balance", ink).get_width()/self.frame.sx + 26
            chip = (right - width, 23, width, 34)
            paint.rect(self.frame, fill, chip, border_radius=9)
            self.label(value, (right - width/2, 40), "balance", ink, "center")
            right -= width + 10
        rate = self.garden.bee_rate(now)
        if rate:
            self.label(f"Bees +{compact(rate)}/sec", (right - 5, 40), color=MUTED, anchor="midright")

    def draw_context(self, title, note, foot=""):
        paint.rect(self.frame, PAPER, CONTEXT, border_radius=14)
        paint.rect(self.frame, LINE, CONTEXT, 1, border_radius=14)
        x = CONTEXT.x + 18
        self.label(title, (x, CONTEXT.y + 15), "heading")
        self.paragraph(note, (x, CONTEXT.y + 46), CONTEXT.width - 36)
        if foot:
            self.paragraph(foot, (x, CONTEXT.y + 114), CONTEXT.width - 36, lines=2, color=GREEN)

    def draw(self, now, pixels=None):
        if pixels is not None:
            self.resize(pixels)
        self.frame.fill(CREAM)
        garden = self.garden
        self.draw_header(now)
        self.draw_sidebar()
        page = self.yard_page()
        key = self.page_key()
        _, description, guide = GUIDES.get(key, ("Activities", "Choose what to do next.", ""))
        title = NAV_TITLES.get(key, YARD_PAGES[page][0] if page else "Garden")
        if self.seed_pot is not None:
            name = "Moon Pot" if self.seed_pot == 3 else f"Pot {self.seed_pot + 1}"
            title, description = f"Choose a seed for {name}", "Select a flower from the list on the right."
            guide = "Bagged seeds are free to plant. When you’re out of those, unlocked seeds can be bought with clover."
        elif self.arcade is not None:
            title = GAMES[self.arcade_key]
            description = "Festival remix" if self.festival_round else MODES[self.arcade_mode].name
        elif self.play_choice is not None:
            title, description = GAMES[self.play_choice], GAME_DETAILS[self.play_choice]
            guide = "Choose a mode on the right. Each mode has its own record and ticket rate."
        self.label(self.fit_text(title, "title", SCENE.width), (SCENE.x, 94), "title")
        self.paragraph(description, (SCENE.x, 132), SCENE.width, lines=1)
        color = pg.Color(GREEN).lerp(pg.Color(GREEN_HOVER), self.hover)
        if self.arcade is not None:
            self.draw_arcade()
            paint.rect(self.frame, color, PICK, border_radius=9)
            action = ("Cash out & exit" if self.arcade_mode == "endless" and not self.arcade.done else "Back to modes")
            if self.festival_round:
                action = "Back to festival"
            self.label(action, PICK.center, "pick", PAPER, "center")
            self.draw_context("Leaving a round",
                              "Finish a timed round to keep your score. In Endless, cash out whenever you’re ready.",
                              "Esc goes back.")
            return self.frame.surface
        if page == "showcase":
            self.draw_scene(now)
        elif page:
            def label(value, pos, font="small", color=INK, anchor="topleft"):
                if font != "title" or value != YARD_PAGES[page][0]:
                    self.scene_label(value, pos, font, color, anchor)

            self.yard_view.draw(self.scene, label, now, self.tick)
            self.present_scene()
        elif self.play_choice is not None:
            self.draw_mode_preview()
        else:
            self.draw_scene(now)
        age = self.tick - self.pick_press
        indent = round(3 * (1 - age / .16)**2) if 0 <= age < .16 else 0
        button = PICK.inflate(-2 * indent, -indent).move(0, indent)
        paint.rect(self.frame, color, button, border_radius=9)
        if self.decoration_active():
            action = "Cancel move" if self.yard_view.projects.moving else "Done editing"
        else:
            action = ("Back to garden" if page else "Back to pots" if self.seed_pot is not None
                      else "Back to all games" if self.play_choice is not None
                      else f"Pick clover  +{compact(1 + garden.levels[0])}")
        self.label(action, button.center, "pick", PAPER, "center")
        if garden.levels[2] and not page and self.play_choice is None:
            track = pg.Rect(PICK.x, PICK.bottom + 6, PICK.width, 5)
            paint.rect(self.frame, LINE, track, border_radius=2)
            if garden.streak:
                track.width = round(track.width * garden.streak / STREAK_LENGTH)
                paint.rect(self.frame, "#94a978", track, border_radius=2)
        foot = ("Select another activity from the sidebar at any time." if page else
                "Press Space to pick clover." if self.play_choice is None and self.seed_pot is None else "Esc goes back.")
        if page == "showcase":
            foot = f"{len(garden.yard.estate.displays)} decorations placed"
        self.draw_context("How it works", guide, foot)
        self.draw_shop(now)
        return self.frame.surface


def main(save_file=None):
    initial_size = window_size()
    os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
    pg.display.init()
    pg.font.init()
    try:
        icon = Canvas((32, 32), (32, 32), alpha=True)
        paint.rect(icon, CREAM, icon.get_rect(), border_radius=8)
        clover_mark(icon, 16, 17, GREEN)
        pg.display.set_icon(icon.surface)
        pg.display.set_caption("Clover Patch")
        garden = Garden() if save_file is None else Garden(save_file)
        display = GameDisplay(initial_size)
        display.show(garden.fullscreen)
        app = CloverApp(garden)
        app.fullscreen = display.fullscreen
        clock = pg.time.Clock()
        running = True
        try:
            while running:
                elapsed = clock.tick(60) / 1000
                now = time.time()
                app.update(elapsed, now)
                area = viewport(display.screen.get_size())
                for event in pg.event.get():
                    if not app.handle(event, area, now):
                        running = False
                        break
                    if app.display_requested:
                        app.display_requested = False
                        display.show(not display.fullscreen)
                        app.fullscreen = display.fullscreen
                        if garden.fullscreen != display.fullscreen:
                            garden.fullscreen = display.fullscreen
                            garden.dirty = True
                        area = viewport(display.screen.get_size())
                        app.pointer = (-1, -1)
                if running:
                    screen = display.screen
                    frame = app.draw(now, area.size)
                    if area.size != screen.get_size():
                        screen.fill(CREAM)
                    screen.blit(frame, area)
                    pg.display.flip()
        finally:
            garden.save()
    finally:
        pg.quit()
