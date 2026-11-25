"""Draw in logical coordinates directly onto a pixel-sized surface."""

import pygame as pg


class Canvas:
    def __init__(self, size, pixels, alpha=False):
        self.size = size
        self.pixels = pixels
        self.surface = pg.Surface(pixels, pg.SRCALPHA if alpha else 0)
        self.sx, self.sy = pixels[0] / size[0], pixels[1] / size[1]
        self.scale = min(self.sx, self.sy)

    def point(self, point):
        x, y = point
        return x * self.sx, y * self.sy

    def rect(self, rect):
        x, y, width, height = rect
        left, top = round(x * self.sx), round(y * self.sy)
        return pg.Rect(left, top, round((x + width) * self.sx) - left, round((y + height) * self.sy) - top)

    def units(self, value):
        return max(1, round(value * self.scale)) if value else 0

    def get_rect(self):
        return pg.Rect(0, 0, *self.size)

    def fill(self, color):
        self.surface.fill(color)

    def set_clip(self, rect):
        self.surface.set_clip(None if rect is None else self.rect(rect))

    def blit(self, source, pos, special_flags=0):
        if isinstance(pos, pg.Rect):
            pos = pos.topleft
        if isinstance(source, Canvas):
            source = source.surface
        self.surface.blit(source, tuple(map(round, self.point(pos))), special_flags=special_flags)

    def copy(self):
        result = Canvas(self.size, self.pixels, bool(self.surface.get_flags() & pg.SRCALPHA))
        result.surface = self.surface.copy()
        return result

    def set_alpha(self, alpha):
        self.surface.set_alpha(alpha)

    def text(self, image, pos, anchor):
        self.surface.blit(image, image.get_rect(**{anchor: tuple(map(round, self.point(pos)))}))


class Paint:
    @staticmethod
    def rect(canvas, color, rect, width=0, border_radius=0):
        pg.draw.rect(canvas.surface, color, canvas.rect(rect), canvas.units(width), canvas.units(border_radius))

    @staticmethod
    def ellipse(canvas, color, rect, width=0):
        pg.draw.ellipse(canvas.surface, color, canvas.rect(rect), canvas.units(width))

    @staticmethod
    def polygon(canvas, color, points, width=0):
        pg.draw.polygon(canvas.surface, color, [canvas.point(p) for p in points], canvas.units(width))

    @staticmethod
    def line(canvas, color, start, end, width=1):
        pg.draw.line(canvas.surface, color, canvas.point(start), canvas.point(end), canvas.units(width))

    @staticmethod
    def lines(canvas, color, closed, points, width=1):
        pg.draw.lines(canvas.surface, color, closed, [canvas.point(p) for p in points], canvas.units(width))

    @staticmethod
    def aalines(canvas, color, closed, points):
        pg.draw.aalines(canvas.surface, color, closed, [canvas.point(p) for p in points])

    @staticmethod
    def arc(canvas, color, rect, start, end, width=1):
        pg.draw.arc(canvas.surface, color, canvas.rect(rect), start, end, canvas.units(width))


paint = Paint()
