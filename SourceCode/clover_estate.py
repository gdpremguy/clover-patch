import math

import pygame as pg

from clover_render import paint
from clover_scene import WIDTH, bloom, oval, sparkle
from number_display import format_count as count
from yard_extras import AUTOMATION_PRICE, COMMISSIONS, DISPLAY_BOUNDS, DISPLAY_LIMIT, FESTIVAL_TRIALS, QUEUE_LIMIT, SHOWPIECES, TREASURE_SPOTS


ESTATE_PAGES = {
    "projects": ("Garden Projects", "Family trees, festivals, and more", "#dce8d3"),
    "family": ("Hybrid Family Tree", "Trace and pin the flowers you’ve created", "#e2d3ea"),
    "commissions": ("Breeding Challenges", "Grow hybrids with requested traits", "#eed7c5"),
    "showcase": ("Garden Showcase", "Decorate the main garden", "#dce8d3"),
    "treasure": ("Snail Treasure Maps", "Follow the clues your snail brings home", "#e8dab5"),
    "festival": ("Garden Festivals", "Bouquet shows, remixed games, and prizes", "#f3d9be"),
    "automation": ("Greenhouse Automation", "Set planting presets and seed queues", "#cde4d9"),
    "moon": ("Moon Garden", "A fourth pot under the aurora", "#babfe0"),
}
MAP_SPOTS = tuple(pg.Rect(21 + 85*i, 94, 73, 64) for i in range(4))
PARENTS = (pg.Rect(55, 119, 110, 74), pg.Rect(207, 119, 110, 74))


def row(key, name, detail, action, enabled=True, swatch=None):
    return key, name, detail, action, enabled, swatch


def piece_name(yard, key):
    return SHOWPIECES[key][0] if key in SHOWPIECES else yard.flower_info(key)[0] if key else "Empty"


def draw_piece(scene, yard, key, x, y, tick, scale=1):
    if not key:
        return
    if key == "stones":
        for i in range(3):
            oval(scene, "#b1a49a", x + (i - 1) * 13 * scale, y - (i % 2) * 7 * scale, 7 * scale, 4 * scale)
    elif key == "lantern":
        paint.line(scene, "#5b5e4f", (x - 9*scale, y+4*scale), (x - 9*scale, y-27*scale), 2*scale)
        paint.line(scene, "#5b5e4f", (x-9*scale, y-27*scale), (x+6*scale, y-27*scale), 2*scale)
        oval(scene, "#f3ddb0", x+6*scale, y-16*scale, (10 + math.sin(tick*3))*scale, 11*scale)
        paint.rect(scene, "#d69a61", (x, y-24*scale, 12*scale, 16*scale), border_radius=3)
        paint.rect(scene, "#ffe7a0", (x+2*scale, y-21*scale, 8*scale, 10*scale), border_radius=2)
    elif key == "bed":
        oval(scene, "#9b8f6e", x, y+2*scale, 23*scale, 6*scale)
        for i, flower in enumerate(("daisy", "tulip", "lavender")):
            xx = x + (i-1)*13*scale
            paint.line(scene, "#6c945f", (xx, y), (xx, y-10*scale), 2*scale)
            bloom(scene, xx, y-11*scale, flower, .52*scale)
    elif key == "pebble":
        oval(scene, "#8aafc2", x, y-3*scale, 12*scale, 7*scale)
        sparkle(scene, "#f5df82", x+2*scale, y-5*scale, 4*scale)
    elif key == "bunting":
        for sign in (-1, 1):
            paint.line(scene, "#786958", (x + sign*22*scale, y), (x + sign*22*scale, y-27*scale), 2*scale)
        for i, color in enumerate(("#e3a09c", "#f2d585", "#a4bfa3", "#b9a8da")):
            left, yy = x+(-20+i*11)*scale, y-25*scale+math.sin(tick*5+i)*2*scale
            paint.polygon(scene, color, [(left, yy), (left+9*scale, yy), (left+4*scale, yy+10*scale)])
    elif yard.is_flower(key):
        sway = math.sin(tick*2 + x) * 2
        oval(scene, "#8aa078", x, y + 1, 15*scale, 4*scale)
        paint.line(scene, "#638464", (x, y), (x+sway, y-17*scale), 2*scale)
        bloom(scene, x+sway, y-18*scale, key, .88*scale, yard=yard)


def draw_showcase(scene, yard, tick):
    for key, x, y in sorted(yard.estate.displays, key=lambda item: item[2]):
        draw_piece(scene, yard, key, x, y, tick, .76)


class EstateView:
    def __init__(self, yard):
        self.yard = yard
        self.flower = None
        self.request = None
        self.placing = None
        self.display_selected = None
        self.moving = False
        self.pot = None
        self.queue_mode = False

    @property
    def e(self):
        return self.yard.estate

    def rows(self, page):
        e, y = self.e, self.yard
        if page == "projects":
            for key, (name, detail, color) in ESTATE_PAGES.items():
                if key != page and (key != "moon" or e.moon):
                    yield row(key, name, detail, "Open", swatch=color)
        elif page == "family":
            if self.flower in y.hybrids:
                name, color = y.flower_info(self.flower)
                pinned = self.flower in e.favorites
                yield row(("pin", self.flower), name, "Pinned at the top of seed lists" if pinned else "Pin to find this hybrid later",
                          "Unpin" if pinned else "Pin", swatch=color)
                for key in e.lineage.get(self.flower, ()):
                    name, color = y.flower_info(key)
                    yield row(("tree", key), name, "Parent", "Follow" if key in y.hybrids else "Original",
                              key in y.hybrids, color)
            if not y.hybrids:
                yield row("breed", "No hybrids yet", "Make a hybrid to start its family tree", "Hybrid Maker")
            for key in sorted(y.hybrids, key=lambda k: k not in e.favorites):
                if key != self.flower:
                    name, color = y.flower_info(key)
                    yield row(("tree", key), name, "Pinned hybrid" if key in e.favorites else "Hybrid",
                              "View", swatch=color)
        elif page == "commissions":
            for key, (name, hint, reward, tickets) in COMMISSIONS.items():
                claimed = key in e.commissions
                if self.request is None or self.request == key:
                    yield row(("request", key), name, hint, "Done" if claimed else
                              "All requests" if self.request else "View", not claimed or self.request == key)
                if self.request == key and not claimed:
                    for flower in y.hybrids:
                        if e.matching(key, flower):
                            title, color = y.flower_info(flower)
                            yield row(("submit", flower), title, f"+{reward} clover · +{tickets} tickets", "Deliver", swatch=color)
                    if not any(e.matching(key, k) for k in y.hybrids):
                        yield row("missing", "No matching flowers", "Harvest a hybrid that meets the request", "Waiting", False)
        elif page == "showcase":
            selected = self.selected_piece()
            if self.moving:
                yield row("cancel", "Moving a decoration", "Click where you want it to go", "Cancel")
            elif self.placing:
                yield row("cancel", f"Placing {piece_name(y, self.placing)}", "Click the ground to add copies", "Done")
            elif selected:
                name = piece_name(y, selected[0])
                yield row("move", name, "Pick a new spot in the garden", "Move")
                yield row("remove", "Remove decoration", "You keep the item and can place it again", "Remove")
            else:
                yield row("count", "Garden decorations", f"{len(e.displays)}/{DISPLAY_LIMIT} placed · Select an item below", "Ready", False)
            for key, (name, price, currency) in SHOWPIECES.items():
                owned = key in e.owned_showpieces
                detail = ("From snail maps" if currency == "treasure" else "From the festival stall" if currency == "festival" else
                          "Owned" if owned else f"{price} {currency}")
                yield row(("place", key), name, detail, "Select" if owned else
                          "Locked" if currency in ("treasure", "festival") else "Select", e.can_place(key))
            for key in sorted(y.stickers & set(y.flower_keys()), key=lambda k: (k not in e.favorites, y.flower_info(k)[0])):
                name, color = y.flower_info(key)
                yield row(("place", key), name, "Display without using up a flower", "Select", swatch=color)
        elif page == "treasure":
            if e.has_map():
                yield row("clue", f"Clue {e.map_step + 1}/2", f"Look under the {TREASURE_SPOTS[e.clue()]}", "Search below", False)
                for i, name in enumerate(TREASURE_SPOTS):
                    yield row(("search", i), name.title(), "", "Search")
            else:
                yield row("snail", "No map in the bag", "Your snail brings one every two gifts", "See snail")
        elif page == "festival":
            if not e.festival_open:
                yield row("begin", "Open the festival", "Enter a bouquet and play a remix", "Begin")
            else:
                done = len(e.festival_marks)
                yield row("finish", "Festival prizes", f"{done}/2 stamps · +125 clover · +8 tickets", "Claim", done == 2)
                for key, name in (("petals", "Golden Petal Catch"), ("pop", "Golden Clover Pop")):
                    yield row(("trial", key), name, f"Gold-only remix · Goal {FESTIVAL_TRIALS[key]} points", "Play")
                owned = "bunting" in e.owned_showpieces
                yield row("bunting", "Festival stall", "Festival Bunting · 5 tickets", "Owned" if owned else "Buy", not owned and e.garden.tickets >= 5)
                matches = [i for i, value in enumerate(y.bouquets) if len(set(value) - {""}) == 3]
                if not matches:
                    yield row("bouquet", "Bouquet show", "Save a bouquet with three different flowers", "Arrange")
                for i in matches:
                    yield row(("entry", i), f"Enter Bouquet {i+1}", "Three different blooms",
                              "Entered" if "bouquet" in e.festival_marks else "Enter", "bouquet" not in e.festival_marks)
        elif page == "automation":
            if "glass" not in y.zones:
                yield row("zones", "Greenhouse required", "Unlock the greenhouse first", "Find it")
            elif not e.automated:
                yield row("buy", "Replanting controls", "Set a preset or queue per pot", f"{AUTOMATION_PRICE} clover",
                          e.garden.clover >= AUTOMATION_PRICE)
            elif self.pot is None:
                for i in range(len(e.garden.plots)):
                    state = "Auto-replant on" if i in e.auto_pots else "Manual planting"
                    yield row(("pot", i), f"Pot {i+1}", f"{state} · {len(e.queues.get(i, []))} queued", "Settings")
            else:
                i = self.pot
                active = i in e.auto_pots
                preset = e.presets.get(i)
                queue = e.queues.get(i, [])
                yield row("toggle", f"Pot {i+1} auto-replant", f"Preset: {y.flower_info(preset)[0]}" if preset else "Default: replant the last crop",
                          "Switch off" if active else "Switch on")
                yield row("toggle_mode", "Seed queue" if self.queue_mode else "Planting preset",
                          f"{len(queue)}/{QUEUE_LIMIT} queued" if self.queue_mode else "Choose a seed below",
                          "Edit preset" if self.queue_mode else "Edit queue")
                yield row("pots", "Pot settings", "Pick another pot", "Other pots")
                if queue and self.queue_mode:
                    names = " → ".join(y.flower_info(k)[0] for k in queue)
                    yield row("clear_queue", "Queued seeds", names, "Clear")
                for key in e.garden.seed_options():
                    name, color = y.flower_info(key)
                    yield row(("seed", key), name, "Uses normal seed prices or your bag", "Queue" if self.queue_mode else "Set",
                              not self.queue_mode or len(queue) < QUEUE_LIMIT, color)
        elif page == "moon":
            yield row("moon_pot", "Moon Pot", "Use it like any other garden pot", "Go to pot")

    def action(self, page, key):
        e = self.e
        action, value = key if isinstance(key, tuple) else (key, None)
        if page == "projects":
            return ("open", key)
        if page == "family":
            if action == "tree":
                self.flower = value
            elif action == "pin":
                e.toggle_favorite(value)
            elif action == "breed":
                return ("open", "breed")
        elif page == "commissions":
            if action == "request":
                self.request = None if self.request == value else value
            elif action == "submit" and self.request and e.submit(self.request, value):
                self.request = None
                return ("note", "Request completed!")
        elif page == "showcase":
            if action == "cancel":
                self.cancel_decoration()
            elif action == "move" and self.selected_piece():
                self.moving = True
            elif action == "remove" and self.selected_piece():
                e.remove_display(self.display_selected)
                self.cancel_decoration()
                return ("note", "Decoration removed.")
            elif action == "place" and e.can_place(value):
                self.cancel_decoration()
                self.placing = value
                return ("note", "Click the garden to place it.")
        elif page == "treasure":
            if action == "snail":
                return ("open", "snail")
            if action == "search":
                return ("note", e.search(value))
        elif page == "festival":
            if action == "begin" and e.start_festival():
                return ("note", "The festival is open!")
            if action == "finish" and e.close_festival():
                return ("note", "Festival prizes collected!")
            if action == "bunting" and e.buy_bunting():
                return ("note", "Bunting is available in Garden Showcase.")
            if action == "entry" and e.enter_bouquet(value):
                return ("note", "Bouquet stamp earned!")
            if action == "bouquet":
                return ("open", "bouquet")
            if action == "trial":
                return ("trial", value)
        elif page == "automation":
            if action == "zones":
                return ("open", "zones")
            if action == "buy" and e.buy_automation():
                return ("note", "Replanting controls unlocked!")
            if action == "pot":
                self.pot, self.queue_mode = value, False
            elif action == "pots":
                self.pot = None
            elif action == "toggle":
                e.toggle_auto(self.pot)
            elif action == "toggle_mode":
                self.queue_mode = not self.queue_mode
            elif action == "clear_queue":
                e.clear_queue(self.pot)
            elif action == "seed":
                changed = e.queue_seed(self.pot, value) if self.queue_mode else e.set_preset(self.pot, value)
                if changed:
                    return ("note", "Seed queued" if self.queue_mode else "Preset saved")
        elif page == "moon" and action == "moon_pot":
            return ("moon_pot", 3)
        return None

    def click_scene(self, page, x, y):
        if page == "showcase":
            if self.placing is not None:
                if self.e.place(self.placing, x, y):
                    return None
                if len(self.e.displays) >= DISPLAY_LIMIT:
                    return f"The garden holds up to {DISPLAY_LIMIT} decorations."
                return "Choose an open spot on the ground."
            if self.moving and self.selected_piece():
                if self.e.move_display(self.display_selected, x, y):
                    self.moving = False
                    return "Decoration moved."
                return "Choose an open spot on the ground."
            self.display_selected = self.display_at(x, y)
        elif page == "family" and self.flower:
            for rect, parent in zip(PARENTS, self.e.lineage.get(self.flower, ())):
                if rect.collidepoint(x, y) and parent in self.yard.hybrids:
                    self.flower = parent
                    break
        elif page == "treasure" and self.e.has_map():
            for i, rect in enumerate(MAP_SPOTS):
                if rect.collidepoint(x, y):
                    return self.e.search(i)
        return None

    def cancel_decoration(self):
        self.placing = None
        self.moving = False
        self.display_selected = None

    def selected_piece(self):
        index = self.display_selected
        return self.e.displays[index] if index is not None and 0 <= index < len(self.e.displays) else None

    def display_at(self, x, y):
        hits = [((x-xx)**2 + (y-yy+7)**2, i) for i, (_, xx, yy) in enumerate(self.e.displays)
                if abs(x-xx) <= 18 and yy-27 <= y <= yy+11]
        return min(hits)[1] if hits else None

    def draw_decoration_tools(self, scene, pointer, tick):
        selected = self.selected_piece()
        if selected:
            _, x, y = selected
            paint.ellipse(scene, "#fff1bf", (x-21, y-7, 42, 15), 2)
        x, y = pointer
        key = self.placing or (selected[0] if self.moving and selected else None)
        if key:
            left, top, right, bottom = DISPLAY_BOUNDS
            if left <= x <= right and top <= y <= bottom:
                valid = self.e.space_for(x, y, self.display_selected if self.moving else None)
                if not self.moving:
                    valid = valid and len(self.e.displays) < DISPLAY_LIMIT
                if valid:
                    draw_piece(scene, self.yard, key, x, y, tick, .76)
                paint.ellipse(scene, "#e6f0c3" if valid else "#ca8a76", (x-19, y-6, 38, 13), 2)

    def draw(self, page, scene, label, tick):
        e, y = self.e, self.yard
        title, detail, color = ESTATE_PAGES[page]
        scene.fill(color)
        label(title, (186, 24), "title", anchor="center")
        if page == "family" and self.flower:
            key = self.flower
            bloom(scene, 186, 73, key, 1.45, yard=y)
            label(y.flower_info(key)[0], (186, 99), "row", anchor="center")
            for rect, parent in zip(PARENTS, e.lineage.get(key, ())):
                paint.rect(scene, "#f3e9f3", rect, border_radius=10)
                bloom(scene, rect.centerx, rect.y+27, parent, 1.15, yard=y)
                label(y.flower_info(parent)[0][:18], (rect.centerx, rect.bottom-14), "small", anchor="center")
            if key not in e.lineage:
                label("An earlier hybrid with no recorded parents", (186, 151), anchor="center")
        elif page == "treasure" and e.has_map():
            label(f"Look under the {TREASURE_SPOTS[e.clue()]}", (186, 64), "row", anchor="center")
            for i, (rect, item) in enumerate(zip(MAP_SPOTS, ("stones", "lantern", "bed", "pebble"))):
                paint.rect(scene, "#f7eed4", rect, border_radius=10)
                draw_piece(scene, y, item, rect.centerx, rect.centery+5, tick, .84)
                label(TREASURE_SPOTS[i], (rect.centerx, rect.bottom-9), anchor="center")
        elif page == "festival":
            for x in (62, 186, 310):
                draw_piece(scene, y, "bunting", x, 111, tick, 1.45)
            label("Festival open" if e.festival_open else "Start whenever you like", (186, 160), "row", anchor="center")
            if e.festival_open:
                label(f"{len(e.festival_marks)}/2 stamps earned", (186, 184), anchor="center")
        elif page == "automation":
            n = len(e.garden.plots)
            for i in range(n):
                x = (i+1)*WIDTH/(n+1)
                oval(scene, "#e8f1e6", x, 111, 29, 29)
                if i in e.auto_pots:
                    sparkle(scene, "#76a585", x, 111, 11 + math.sin(tick*4+i))
                label(str(i+1), (x, 153), "button", anchor="center")
            label(f"{count(len(e.auto_pots))} pots set to replant", (186, 179), "row", anchor="center")
        elif page == "moon":
            oval(scene, "#e8ecf5", 186, 106, 37, 37)
            oval(scene, "#babfe0", 200, 94, 31, 32)
            for x, yy in ((115, 93), (247, 118), (265, 68)):
                sparkle(scene, "#f7eee9", x, yy, 4 + math.sin(tick*3+x))
            label("Your fourth garden pot is open", (186, 166), "row", anchor="center")
        else:
            for i in range(3):
                bloom(scene, 112+i*74, 108+math.sin(tick*2+i)*3, ("daisy", "tulip", "lavender")[i], 1.8, yard=y)
            label(detail, (186, 166), "row", anchor="center")
