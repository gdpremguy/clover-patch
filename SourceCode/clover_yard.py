import math
from dataclasses import replace

import pygame as pg

from clover_estate import ESTATE_PAGES, EstateView
from clover_render import paint
from clover_scene import WIDTH, bloom, generated_bloom, oval, sparkle
from number_display import format_count
from yard import CROP_KEYS, DECOR, FLOWERS, HATS, MOONLACE_VISITS, ORDERS, RARE_SEEDS, STICKERS, SUN_CROWN_HARVESTS, WEATHER, ZONES


PAGES = {
    "breed": ("Hybrid Maker", "Turn two harvested plants into a seed", "#dbc1d9"),
    "projects": ESTATE_PAGES["projects"],
    "stickers": ("Sticker Book", "Collect flowers, visitors, and rare finds", "#f6dfac"),
    "rares": ("Rare Finds", "Track rare blooms and hidden rewards", "#c0cbdc"),
    "shed": ("Garden Shed", "Decorate with your ticket prizes", "#e9c6ad"),
    "market": ("Market Day", "Fill animal neighbors’ flower orders", "#f1c4bb"),
    "weather": ("Weather", "See what’s changing in your garden", "#c5dcd8"),
    "snail": ("Pet Snail", "A little helper who finds seeds", "#cbd7b0"),
    "bouquet": ("Bouquet Bench", "Arrange your blooms and save them", "#eac4d8"),
    "zones": ("Garden Expansion", "Grow new plants and unlock fishing", "#c4dac6"),
}
YARD_PAGES = PAGES | ESTATE_PAGES
SLOTS = tuple(pg.Rect(71 + 77 * i, 68, 76, 108) for i in range(3))
PARENT_CARDS = tuple(pg.Rect(75 + 84 * i, 76, 58, 70) for i in range(2))


def row(key, name, detail, action, enabled=True, swatch=None):
    return key, name, detail, action, enabled, swatch


def draw_snail(surface, x, y, hat, size=1):
    oval(surface, "#d1ae81", x+6*size, y, 16*size, 4*size)
    oval(surface, "#d1ae81", x+16*size, y-5*size, 6*size, 6*size)
    oval(surface, "#a97666", x, y-6*size, 11*size, 10*size)
    paint.arc(surface, "#ebbb93", (x-8*size, y-13*size, 16*size, 15*size), .5, 4.9, max(1, round(size)))
    for dx in (13, 18):
        paint.line(surface, "#624b42", (x+dx*size, y-7*size), (x+(dx-1)*size, y-13*size), max(1, round(size)))
        oval(surface, "#624b42", x+(dx-1)*size, y-13*size, size, size)
    if hat == "leaf":
        oval(surface, "#759667", x+15*size, y-12*size, 6*size, 2*size)
    elif hat == "bow":
        for dx in (11, 18):
            oval(surface, "#e98da0", x+dx*size, y-10*size, 3*size, 2*size)


class YardView:
    def __init__(self, yard):
        self.yard = yard
        self.page = None
        self.parents = []
        self.preview = None
        self.draft = ["", "", ""]
        self.slot = 0
        self.drag_slot = None
        self.gallery_index = None
        self.editing = False
        self.edit_target = None
        self.select_name = False
        self.name = ""
        self.message = None
        self.projects = EstateView(yard)

    def leave(self):
        if self.editing:
            pg.key.stop_text_input()
        self.editing = False
        self.edit_target = None
        self.page = None
        self.drag_slot = None
        self.message = None

    def notify(self, text, tick):
        if text:
            self.message = text, tick + 2.8

    def rows(self, now):
        y, page = self.yard, self.page
        if page is None:
            for key, (title, detail, shade) in PAGES.items():
                yield row(key, title, detail, "Open", swatch=shade)
        elif page in ESTATE_PAGES:
            yield from self.projects.rows(page)
        elif page == "breed":
            preview = self.preview if y.can_breed(self.parents) else None
            detail = f"{preview.name} · {preview.traits.petals} petals" if preview else "Choose two different harvested plants"
            yield row("cross", "Make a hybrid seed",
                      detail, "Make seed", preview is not None, preview.traits.color if preview else None)
            if preview:
                form = f"{preview.traits.layers} {'layer' if preview.traits.layers == 1 else 'layers'}"
                yield row("reroll", "Preview another cross", f"{form} · {preview.traits.pattern.title()} petals", "Reroll")
                yield row("rename", "Name your hybrid", preview.name, "Name")
            for key in y.flower_keys():
                name, color = y.flower_info(key)
                chosen = key in self.parents
                count = y.flowers.get(key, 0)
                if count or chosen:
                    yield row(key, name, f"In basket: {format_count(count)}", "Remove" if chosen else "Choose", True, color)
            if not y.flowers:
                yield row("empty", "Basket is empty", "Harvest plants from your garden pots first", "No plants", False)
        elif page == "stickers":
            reward = y.sticker_reward()
            yield row("claim", f"{format_count(len(y.stickers))} stickers found", "Prize every four discoveries",
                      f"Claim +{format_count(reward)}" if reward else "Collecting", bool(reward))
            for key, (name, hint, color) in y.sticker_entries():
                found = key in y.stickers
                yield row(key, name if found else "Undiscovered", "In your book" if found else hint,
                           "Found" if found else "Missing", False, color if found else "#deceba")
        elif page == "rares":
            for key, hint in RARE_SEEDS.items():
                name, color = FLOWERS[key]
                if key == "sun_crown":
                    hint = f"{min(SUN_CROWN_HARVESTS, y.garden.stats['flowers'])}/{SUN_CROWN_HARVESTS} harvests"
                elif key == "moonlace":
                    hint = f"{min(MOONLACE_VISITS, y.garden.stats['moths'])}/{MOONLACE_VISITS} fog moths greeted"
                grown = key in y.stickers
                found = key in y.rare_seeds_found
                yield row(key, name, "You can now buy seeds for any pot" if grown else "Plant this seed in any pot" if found else hint,
                          "Grown" if grown else "Seed found" if found else "Missing", False, color)
            name, hint, color = STICKERS["silver_pearl"]
            found = "silver_pearl" in y.stickers
            yield row("silver_pearl", name, "In your sticker book" if found else hint, "Found" if found else "Missing", False, color)
            active = y.garden.style_key == "aurora"
            count = len(RARE_SEEDS.keys() & y.stickers)
            yield row("aurora", "Aurora Garden", f"{count}/{len(RARE_SEEDS)} rare plants grown",
                      "Equipped" if active else "Equip" if y.aurora_ready() else "Locked", y.garden.can_equip("aurora"), "#91b8d0")
        elif page == "shed":
            for key, (name, slot, price) in DECOR.items():
                owned = key in y.decor
                active = y.room.get(slot) == key
                yield row(key, name, slot.title(), "Put away" if active else "Place" if owned else f"{price} tickets",
                          owned or y.garden.tickets >= price)
        elif page == "market":
            day, today = y.active_orders(now)
            for key in today:
                name, needs, reward = ORDERS[key]
                filled = day == y.market_day and key in y.orders_filled
                detail = " · ".join(f"{min(y.flowers.get(k, 0), n)}/{n} {FLOWERS[k][0].lower()}" for k, n in needs.items())
                yield row(key, name, detail, "Sold" if filled else f"Sell +{format_count(reward)}", not filled and y.have_flowers(needs))
        elif page == "weather":
            weather, seconds = y.weather(now)
            for key, detail in WEATHER.items():
                yield row(key, key, detail, f"{seconds}s left" if weather == key else "Forecast", False)
        elif page == "snail":
            if not y.snail:
                yield row("name", "Adopt a snail", "Your snail can find free seeds.", "Adopt")
            else:
                seconds = max(0, math.ceil(y.snail_due - now))
                yield row("gift", y.snail, f"Looking for seeds: {seconds}s" if seconds else "A seed is ready",
                          "Searching" if seconds else "Collect", not seconds)
                yield row("name", "Name tag", "Give your snail a new name", "Rename")
                for key, (name, price) in HATS.items():
                    owned = key in y.hats
                    yield row(key, name, "Snail accessory", "Remove" if y.hat == key else "Wear" if owned else f"{price} tickets",
                              owned or y.garden.tickets >= price)
        elif page == "bouquet":
            yield row("save", "Save bouquet", f"Editing spot {self.slot + 1}", "Save", any(self.draft) and tuple(self.draft) not in y.bouquets)
            n = len(y.bouquets)
            yield row("gallery", "Bouquet gallery", f"{n} saved", "Next" if self.gallery_index is not None else "View", n > 0)
            yield row("clear", "Empty this spot", "Click a spot above to select it", "Clear", bool(self.draft[self.slot]))
            for key in y.flower_keys():
                if key in y.stickers:
                    name, color = y.flower_info(key)
                    yield row(key, name, "Add to your arrangement", "Place", swatch=color)
        elif page == "zones":
            for key, (name, flower, unlock, *_) in ZONES.items():
                color = FLOWERS[flower][1]
                if key not in y.zones:
                    yield row(key, name, "Lily seeds and Pond Fishing" if key == "pond" else f"Unlocks {FLOWERS[flower][0].lower()} seeds",
                              f"{unlock} clover", y.garden.clover >= unlock, color)
                else:
                    detail = "Moves to a garden pot when one opens" if key in y.pending_plants else "Seeds available in garden pots"
                    yield row(key, name, detail, "Unlocked", False, color)

    def activate(self, key, now, tick):
        y = self.yard
        if self.page is None:
            self.page = key
            return
        if self.page in ESTATE_PAGES:
            result = self.projects.action(self.page, key)
            if result:
                action, value = result
                if action == "open":
                    self.page = value
                    self.message = None
                elif action == "note":
                    self.notify(value, tick)
                else:
                    return result
            return None
        if self.page == "breed":
            if key == "cross":
                hybrid = y.breed(self.parents, self.preview)
                if hybrid:
                    self.parents.clear()
                    self.preview = None
                    self.notify(f"{y.flower_info(hybrid)[0]} seed added to your bag", tick)
            elif key == "reroll":
                self.preview = y.preview_hybrid(self.parents)
            elif key == "rename" and self.preview:
                self.begin_edit("hybrid", self.preview.name)
            elif y.is_flower(key):
                if key in self.parents:
                    self.parents.remove(key)
                elif len(self.parents) < 2:
                    self.parents.append(key)
                else:
                    self.parents = [self.parents[-1], key]
                self.preview = y.preview_hybrid(self.parents)
        elif self.page == "stickers":
            reward = y.claim_stickers()
            self.notify(f"+{format_count(reward)} clover" if reward else "", tick)
        elif self.page == "rares":
            if key == "aurora" and y.garden.choose_style(key):
                self.notify("Aurora Garden equipped", tick)
        elif self.page == "shed":
            self.notify(y.buy_decor(key), tick)
        elif self.page == "market":
            reward = y.sell_order(key, now)
            self.notify(f"Order delivered  ·  +{format_count(reward)} clover" if reward else "", tick)
        elif self.page == "zones":
            self.notify(y.unlock_zone(key), tick)
        elif self.page == "snail":
            if key == "name":
                self.begin_edit("snail", y.snail or "Pebble")
            elif key == "gift":
                self.notify(y.gift(now), tick)
            elif y.buy_hat(key):
                self.notify("Outfit changed", tick)
        elif self.page == "bouquet":
            if key == "save":
                if y.save_bouquet(self.draft):
                    self.gallery_index = None
                    self.notify("Bouquet saved", tick)
            elif key == "gallery" and y.bouquets:
                self.gallery_index = 0 if self.gallery_index is None else (self.gallery_index + 1) % len(y.bouquets)
            elif key == "clear":
                self.edit_bouquet()
                self.draft[self.slot] = ""
            elif y.is_flower(key):
                self.edit_bouquet()
                self.draft[self.slot] = key
                self.slot = (self.slot + 1) % len(self.draft)

    def edit_bouquet(self):
        if self.gallery_index is not None:
            self.draft[:] = self.yard.bouquets[self.gallery_index]
            self.gallery_index = None

    def click_scene(self, x, y, tick=0):
        if self.page in ESTATE_PAGES:
            self.notify(self.projects.click_scene(self.page, x, y), tick)
            return
        if self.page == "breed":
            for index, rect in enumerate(PARENT_CARDS):
                if rect.collidepoint(x, y) and index < len(self.parents):
                    self.parents.pop(index)
                    self.preview = None
                    break
        elif self.page == "bouquet":
            for index, rect in enumerate(SLOTS):
                if rect.collidepoint(x, y):
                    self.edit_bouquet()
                    self.slot = index
                    self.drag_slot = index if self.draft[index] else None
                    break

    def release_scene(self, x, y):
        source, self.drag_slot = self.drag_slot, None
        if self.page != "bouquet" or source is None:
            return
        for target, rect in enumerate(SLOTS):
            if rect.collidepoint(x, y) and target != source:
                self.draft[source], self.draft[target] = self.draft[target], self.draft[source]
                self.slot = target
                break

    def begin_edit(self, target, name):
        self.name = name
        self.editing = True
        self.edit_target = target
        self.select_name = True
        pg.key.start_text_input()

    def on_text(self, event, now, tick):
        if event.type == pg.TEXTINPUT:
            limit = 24 if self.edit_target == "hybrid" else 18
            typed = "".join(c for c in event.text if c.isprintable())
            if typed:
                self.name = (("" if self.select_name else self.name) + typed)[:limit]
                self.select_name = False
        elif event.type == pg.KEYDOWN:
            if event.key == pg.K_BACKSPACE:
                self.name = "" if self.select_name else self.name[:-1]
                self.select_name = False
            elif event.key == pg.K_a and getattr(event, "mod", 0) & pg.KMOD_CTRL:
                self.select_name = True
            elif event.key in (pg.K_RETURN, pg.K_KP_ENTER):
                if self.edit_target == "hybrid" and self.preview and self.name.strip():
                    self.preview = replace(self.preview, name=self.name.strip())
                    self.editing = False
                elif self.edit_target == "snail" and self.yard.set_snail(self.name, now):
                    self.notify("Meet " + self.yard.snail + "!", tick)
                    self.editing = False
            elif event.key == pg.K_ESCAPE:
                self.editing = False
            if not self.editing:
                self.edit_target = None
                pg.key.stop_text_input()

    def draw(self, scene, label, now, tick):
        y, page = self.yard, self.page
        if page in ESTATE_PAGES:
            self.projects.draw(page, scene, label, tick)
            self.draw_message(scene, label, tick)
            return
        title, _, color = PAGES[page]
        scene.fill(color)
        label(title, (WIDTH / 2, 24), "title", anchor="center")
        if page == "breed":
            for i, rect in enumerate(PARENT_CARDS):
                px = rect.centerx
                paint.rect(scene, "#f5e7ee", rect, border_radius=12)
                if i < len(self.parents):
                    bloom(scene, px, 110, self.parents[i], 1.55, yard=y)
                else:
                    label("+", (px, 111), "row", anchor="center")
            paint.line(scene, "#987494", (221, 111), (246, 111), 2)
            if self.preview:
                generated_bloom(scene, 280, 111, self.preview.traits, 2.48)
                label("Seed preview", (280, 155), anchor="center")
            else:
                label("?", (280, 111), "title", anchor="center")
            if self.editing:
                paint.rect(scene, "#e5dfed" if self.select_name else "#fff6df", (52, 172, 268, 29), border_radius=8)
                label(self.name + ("|" if not self.select_name and int(tick * 2) % 2 else ""), (186, 186), "row", anchor="center")
                label("Enter to save  ·  Esc to cancel", (186, 208), anchor="center")
        elif page == "stickers":
            paint.rect(scene, "#fff5dd", (50, 53, 272, 120), border_radius=10)
            paint.line(scene, "#ead8b7", (186, 55), (186, 171), 2)
            records = list(y.sticker_entries())
            records.sort(key=lambda entry: (entry[0] not in y.stickers, entry[0] not in y.hybrids))
            for i, (key, (_, _, shade)) in enumerate(records[:18]):
                px = 70 + (i % 6) * 46 + (10 if i % 6 >= 3 else 0)
                py = 75 + i // 6 * 37
                oval(scene, "#edddc1", px, py, 12, 12)
                if key in y.stickers:
                    if y.is_flower(key):
                        bloom(scene, px, py, key, .7, yard=y)
                    else:
                        sparkle(scene, shade, px, py, 10)
            label(f"{format_count(len(y.stickers))} found", (186, 191), "row", anchor="center")
        elif page == "rares":
            scene.fill("#c9d5e3")
            label(title, (186, 24), "title", anchor="center")
            keys = (*RARE_SEEDS, "silver_pearl")
            found = y.rare_finds()
            for index, key in enumerate(keys):
                px = 54 + index * 88
                phase = tick * 2 + index * .95
                cy = 111 + math.sin(phase) * (3 if key in found else 0)
                paint.rect(scene, "#e9edf1" if key in found else "#bccbdb", (px - 34, 69, 68, 84), border_radius=12)
                if key in found:
                    if key in RARE_SEEDS:
                        bloom(scene, px, cy, key, 1.32)
                    else:
                        oval(scene, "#b7bed6", px, cy, 15, 14)
                        oval(scene, "#e9edf6", px - 2, cy - 2, 11, 10)
                        sparkle(scene, "#ffffff", px + 4, cy - 6, 5)
                    sparkle(scene, "#fcf1c9", px + 20, cy - 21, 3 + math.sin(phase * 2))
                else:
                    label("?", (px, 111), "title", "#536980", "center")
            count = len(found.intersection(keys))
            label(f"{count}/{len(keys)} rare finds", (186, 180), "row", anchor="center")
        elif page == "shed":
            scene.fill("#ead1b7")
            label(title, (186, 24), "title", anchor="center")
            paint.rect(scene, "#c59572", (0, 163, WIDTH, 60))
            paint.rect(scene, "#a87861", (56, 131, 121, 9), border_radius=3)
            paint.rect(scene, "#b98f7b", (219, 57, 79, 73), border_radius=8, width=3)
            if y.room.get("wall") == "print":
                paint.rect(scene, "#fff2da", (228, 66, 61, 55), border_radius=5)
                bloom(scene, 259, 92, "peach", 2)
            elif y.room.get("wall") == "flag":
                for dx in range(237, 286, 16):
                    sparkle(scene, "#e6aa7c", dx, 90 + (12 if dx == 253 else 0), 8)
            if y.room.get("shelf") == "mushroom":
                bloom(scene, 111, 119, "mushroom", 2)
            elif y.room.get("shelf") == "cup":
                paint.rect(scene, "#bc894c", (99, 115, 24, 13), border_radius=3)
                oval(scene, "#f9cd72", 111, 105, 17, 14)
                sparkle(scene, "#fff0b5", 113, 104, 8)
            if y.room.get("floor") == "rug":
                oval(scene, "#a57382", 188, 191, 77, 18)
                for dx in range(141, 239, 19):
                    oval(scene, "#deb58f", dx, 191, 7, 8)
        elif page == "market":
            paint.rect(scene, "#9c6a61", (73, 96, 7, 77))
            paint.rect(scene, "#9c6a61", (293, 96, 7, 77))
            for i in range(7):
                x = 56 + i * 37
                paint.polygon(scene, "#b66f77" if i % 2 == 0 else "#fff2dc",
                                [(x+10, 57), (x+47, 57), (x+37, 98), (x, 98)])
            paint.rect(scene, "#bb8169", (62, 146, 250, 35), border_radius=6)
            for i, k in enumerate(CROP_KEYS):
                bloom(scene, 111 + i * 73, 137, k, 2)
            label("Orders change each day", (186, 198), anchor="center")
        elif page == "weather":
            weather, seconds = y.weather(now)
            if weather == "Sun":
                oval(scene, "#efad61", 186, 98, 26, 26)
                for i in range(8):
                    a = i * math.tau / 8
                    paint.line(scene, "#efad61", (186+32*math.cos(a), 98+32*math.sin(a)),
                                 (186+40*math.cos(a), 98+40*math.sin(a)), 3)
            elif weather == "Rain":
                for dx, dy in ((-21, 1), (0, -9), (23, 2)):
                    oval(scene, "#eaf2e8", 186+dx, 87+dy, 20, 16)
                for dx in range(155, 224, 13):
                    oval(scene, "#689ca6", dx+math.sin(tick*6)*3, 113+math.sin(tick*6+dx)*7, 2, 6)
            else:
                for i in range(5):
                    oval(scene, "#e8ede3", 173 + math.sin(tick + i)*23, 77 + i*11, 52, 3)
            label(f"{weather}  ·  {seconds}s left", (186, 155), "row", anchor="center")
            label(WEATHER[weather], (186, 178), anchor="center")
        elif page == "snail":
            oval(scene, "#aabc92", 186, 153, 104, 12)
            draw_snail(scene, 178 + 11*math.sin(tick*1.35), 145, y.hat, 3.4)
            if self.editing:
                paint.rect(scene, "#e6ebd9" if self.select_name else "#fff6df", (72, 165, 228, 33), border_radius=8)
                label(self.name + ("|" if not self.select_name and int(tick * 2) % 2 else ""), (186, 181), "row", anchor="center")
                label("Enter to save  ·  Esc to cancel", (186, 207), anchor="center")
            else:
                label(y.snail or "Waiting for a name", (186, 182), "row", anchor="center")
        elif page == "bouquet":
            flowers = y.bouquets[self.gallery_index] if self.gallery_index is not None else self.draft
            for i, pos in enumerate(SLOTS):
                active = self.gallery_index is None and i == self.slot
                paint.rect(scene, "#fff0e6" if active else "#f5dfde", pos.inflate(-6, 0), border_radius=12)
            for i, pos in enumerate(SLOTS):
                x = pos.centerx
                if flowers[i]:
                    paint.line(scene, "#75906e", (186, 168), (x, 101), 3)
                    bloom(scene, x, 96, flowers[i], 1.9, yard=y)
                else:
                    label("+", (x, 128), "row", anchor="center")
            oval(scene, "#bd8790", 186, 167, 14, 6)
            label(f"Bouquet {self.gallery_index + 1} / {len(y.bouquets)}" if self.gallery_index is not None else
                  "Choose a spot or drag a flower to swap it", (186, 191), anchor="center")
        elif page == "zones":
            for i, (key, (name, flower, *_)) in enumerate(ZONES.items()):
                px = 65 + 121*i
                paint.rect(scene, "#e7ebd6" if key in y.zones else "#b5c8b3", (px-50, 66, 100, 99), border_radius=10)
                bloom(scene, px, 113, flower, 2.2)
                label(name, (px, 147), "small", anchor="center")
            label(f"{len(y.zones)} / {len(ZONES)} corners open", (186, 192), anchor="center")
        self.draw_message(scene, label, tick)

    def draw_message(self, scene, label, tick):
        if self.message and tick < self.message[1] and not self.editing:
            paint.rect(scene, "#fff6e7", (26, 195, 320, 23), border_radius=8)
            label(self.message[0], (186, 206), "button", anchor="center")
