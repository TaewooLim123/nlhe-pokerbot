"""Run: python -m pytest -q  (or python tests/test_core.py)"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pokerbot.agent import Agent
from pokerbot.cards import CATEGORY_NAMES, cards, category, evaluate
from pokerbot.engine import Table
from pokerbot.baselines import CallingStation, Maniac, RandomBot, TightPassive
from pokerbot.icm import icm


def cat(text):
    return CATEGORY_NAMES[category(evaluate(cards(text)))]


def test_categories():
    assert cat("As Ks Qs Js Ts 2d 3c") == "Straight flush"
    assert cat("Ah Ad Ac As 2d 3c 4h") == "Quads"
    assert cat("Ah Ad Ac Ks Kd 3c 4h") == "Full house"
    assert cat("2h 5h 9h Jh Kh Ad Ac") == "Flush"
    assert cat("Ah 2d 3c 4s 5h Kd Kc") == "Straight"
    assert cat("7h 7d 7c Ks Qd 3c 2h") == "Trips"
    assert cat("7h 7d 5c 5s Qd Qc 2h") == "Two pair"
    assert cat("7h 7d 5c 4s Qd Jc 2h") == "Pair"
    assert cat("Ah Kd Qc Js 9h 2d 3c") == "High card"


def test_ordering():
    assert evaluate(cards("Ah Ad Kc Qs Jd 3c 2h")) > evaluate(cards("Ah Ad Kc Qs Td 3c 2h"))
    assert evaluate(cards("6h 2d 3c 4s 5h Kd Kc")) > evaluate(cards("Ah 2d 3c 4s 5h Kd Kc"))
    # two pair kicker: third pair can't play, best single card does
    assert evaluate(cards("Ah Ad Kc Ks 2d 2c Qh")) > evaluate(cards("Ah Ad Kc Ks 3d 3c Jh"))


def test_icm_sums_to_pool():
    ev = icm([3000, 2000, 1000], [50, 30, 20])
    assert abs(sum(ev) - 100) < 1e-9
    assert ev[0] > ev[1] > ev[2]


def test_chips_conserved_and_fast():
    bots = [Agent(seed=i) for i in range(2)] + [RandomBot(1), CallingStation(), Maniac(),
                                                TightPassive(), RandomBot(2), TightPassive()]
    t = Table(bots, seed=5)
    t.run()
    assert sum(t.stacks) == 8 * 2000
    assert sum(t.errors) == 0
    agent_times = sorted(t.decision_times[0] + t.decision_times[1])
    assert agent_times[len(agent_times) // 2] < 0.0002   # median well under budget


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
