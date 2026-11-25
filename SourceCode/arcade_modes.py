from dataclasses import dataclass


@dataclass(frozen=True)
class Mode:
    name: str
    numerator: int
    denominator: int
    note: str

    def tickets(self, score):
        return score * self.numerator // self.denominator

    @property
    def rate(self):
        if self.numerator == 1 and self.denominator == 1:
            return "1 ticket per point"
        if self.numerator == 1:
            return f"1 ticket per {self.denominator} points"
        return f"{self.numerator} tickets per {self.denominator} points"


MODES = {
    "easy": Mode("Easy", 1, 4, "More room for mistakes"),
    "medium": Mode("Medium", 1, 3, "Standard rules"),
    "hard": Mode("Hard", 1, 2, "Faster and less forgiving"),
    "endless": Mode("Endless", 2, 5, "Keep going or cash out"),
    "impossible": Mode("Impossible", 1, 1, "Tiny margins. Good luck."),
}
HARD_GOALS = {"petals": 10, "fireflies": 7, "fishing": 6, "hopping": 12, "pop": 10}
