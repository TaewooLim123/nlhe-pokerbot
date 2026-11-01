"""Simple opponents for testing."""
import random

from . import preflop


def _fallback(legal, prefer):
    for k in prefer:
        if k == "raise" and legal["raise"]:
            return ("raise", legal["raise"][0])
        if k != "raise" and legal.get(k):
            return (k,)
    return ("fold",)


class RandomBot:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)

    def act(self, s):
        legal = s["legal"]
        choices = [k for k in ("fold", "check", "call") if legal.get(k)]
        if legal["raise"]:
            choices.append("raise")
        k = self.rng.choice(choices)
        if k == "raise":
            lo, hi = legal["raise"]
            return ("raise", self.rng.randint(lo, hi))
        return (k,)


class CallingStation:
    def act(self, s):
        return _fallback(s["legal"], ("check", "call"))


class Maniac:
    """Shoves every hand."""
    def act(self, s):
        legal = s["legal"]
        if legal["raise"]:
            return ("raise", legal["raise"][1])
        return _fallback(legal, ("call", "check"))


class TightPassive:
    """Plays the top 15% of hands, never raises."""
    def act(self, s):
        legal = s["legal"]
        if preflop.percentile(*s["hole"]) < 0.15:
            return _fallback(legal, ("check", "call"))
        return _fallback(legal, ("check", "fold"))
