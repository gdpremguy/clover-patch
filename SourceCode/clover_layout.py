import pygame as pg


SIZE = (1100, 760)
NAV = pg.Rect(20, 94, 184, 646)
SCENE = pg.Rect(224, 164, 548, 329)
PICK = pg.Rect(224, 512, 548, 44)
CONTEXT = pg.Rect(224, 580, 548, 160)
PANEL = pg.Rect(790, 94, 290, 646)
DISPLAY_MODE = pg.Rect(934, 23, 146, 34)
LIST = pg.Rect(801, 186, 268, 537)
TRACK = pg.Rect(1062, 188, 5, 532)
REPLAY = pg.Rect(808, 350, 254, 36)
ROW_HEIGHT = 51
GARDEN_TAB, STYLE_TAB, JOURNAL_TAB, PLAY_TAB, YARD_TAB = 1, 2, 3, 4, 5
TAB_PAGE = ("tools", "garden", "styles", "journal", "play", "breed")

NAV_GROUPS = (
    ("Garden", (
        (GARDEN_TAB, None, "Garden & Pots"), (0, None, "Upgrades"),
        (STYLE_TAB, None, "Garden Styles"), (YARD_TAB, "showcase", "Decorate Garden"),
        (YARD_TAB, "zones", "Expansion"), (YARD_TAB, "automation", "Automation"),
        (YARD_TAB, "weather", "Weather"), (YARD_TAB, "moon", "Moon Garden"),
    )),
    ("Flowers", (
        (YARD_TAB, "breed", "Hybrid Maker"), (YARD_TAB, "family", "Hybrid Family Tree"),
        (YARD_TAB, "commissions", "Breeding Challenges"), (YARD_TAB, "bouquet", "Bouquet Bench"),
    )),
    ("Neighbors", (
        (YARD_TAB, "market", "Market Day"), (YARD_TAB, "snail", "Pet Snail"),
        (YARD_TAB, "treasure", "Snail Treasure Maps"), (YARD_TAB, "shed", "Garden Shed"),
    )),
    ("Play", (
        (PLAY_TAB, None, "Minigames"), (YARD_TAB, "festival", "Garden Festivals"),
    )),
    ("Collections", (
        (JOURNAL_TAB, None, "Journal"), (YARD_TAB, "stickers", "Sticker Book"),
        (YARD_TAB, "rares", "Rare Finds"),
    )),
)

NAV_TITLES = {(page or TAB_PAGE[tab]): title for _, links in NAV_GROUPS for tab, page, title in links}

# Panel title, what it does, and the one next step worth calling out.
GUIDES = {
    "garden": ("Your pots", "Choose what grows in each pot.",
               "Click an empty pot to choose a seed. A second click waters a growing flower, and a click on a finished bloom harvests it."),
    "tools": ("Tools for your garden", "Buy upgrades with clover.",
              "The Hand Trowel helps you pick more clover. A Bee Box earns clover on its own, even while you’re looking at another page."),
    "styles": ("Available looks", "Change the look of your whole garden.",
               "Buy a style once and swap back to it for free. Some styles come from tickets or rare discoveries."),
    "showcase": ("Decorations", "Choose an item, then click the garden.",
                 "Place as many copies of an owned item as you like, up to the garden limit. Select an existing decoration to move it or remove it."),
    "zones": ("Places to unlock", "New areas add seeds to your pots.",
              "The Mushroom Nook and Greenhouse unlock new plants. The Lily Pond also opens Pond Fishing in Minigames."),
    "automation": ("Replanting controls", "Set how each pot replants.",
                   "After a manual harvest, enabled pots use their seed queue first, then their preset. Seeds still come from your bag or cost clover."),
    "weather": ("Current forecast", "Weather changes the garden on its own.",
                "Sun helps Bee Boxes, rain waters pots, and lantern moths visit in fog."),
    "moon": ("Your extra pot", "Plant any seed in the Moon Pot.", "The fourth pot also works with your greenhouse automation."),
    "breed": ("Plants in your basket", "Choose two different harvested plants.",
              "Reroll the preview or give it a name. Only making the seed uses up the two parents. Grow the result in any garden pot."),
    "family": ("Your hybrids", "Select a hybrid to see its parents.",
               "Pin favorites to put them near the top of seed lists. Click a parent to trace its own family tree."),
    "commissions": ("Open requests", "Deliver a bloom with the requested traits.",
                    "Open a request to see which flowers in your basket qualify. A preview only counts after you grow and harvest it."),
    "bouquet": ("Arrange a bouquet", "Choose flowers to fill the three spots.",
                "Click a spot to select it, or drag a flower to swap spots. Saving an arrangement doesn’t use any flowers."),
    "market": ("Today’s orders", "Trade flowers for clover.",
               "Each order shows what you have and what the neighbor needs. The available orders change daily."),
    "snail": ("Snail care", "Collect seeds, rename, or try on a hat.",
              "Your snail finds a free seed every so often. Every second gift includes a treasure map."),
    "treasure": ("Treasure map", "Follow the clues from your snail.",
                 "Read the clue, then click the matching spot on the map. The second clue leads to your prize."),
    "shed": ("Shed decorations", "Use tickets to decorate your shed.",
             "Your shed has a wall, shelf, and floor. For decorations in the main garden, go to Decorate Garden."),
    "play": ("Choose a game", "Each game has its own modes and rewards.",
             "Minigames earn tickets. Spend them on styles and decorations or trade them for clover here."),
    "festival": ("Festival activities", "Start a festival whenever you want.",
                 "Enter a bouquet with three different blooms and complete a gold-only minigame to earn the two stamps."),
    "journal": ("Milestones", "Claim rewards for what you’ve done.",
                "Keep planting, growing, and playing to fill out your journal."),
    "stickers": ("Sticker collection", "See what you’ve found and what’s missing.",
                 "Harvest new flowers, greet visitors, and fish for unusual finds. Claim a prize every four discoveries."),
    "rares": ("Rare discoveries", "Track rare seeds and special rewards.",
              "Grow all three rare flowers to unlock the Aurora Garden style."),
}


def nav_rows(moon):
    y = NAV.y + 13
    for group, links in NAV_GROUPS:
        yield None, None, group, pg.Rect(NAV.x + 13, y, NAV.width - 26, 17)
        y += 19
        for tab, page, title in links:
            if page == "moon" and not moon:
                continue
            yield tab, page, title, pg.Rect(NAV.x + 8, y, NAV.width - 16, 23)
            y += 23
        y += 6
