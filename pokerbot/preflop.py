"""Preflop hand strength from a precomputed table.

preflop_equity.json maps each of the 169 starting-hand classes ("AKs", "T9o", "77")
to its all-in equity versus 1..7 random opponents. Build it once with
`python -m scripts.build_preflop_table` (about 2 minutes); lookups are O(1).
"""
import json
import os

from .cards import RANKS

_TABLE_PATH = os.path.join(os.path.dirname(__file__), "preflop_equity.json")
_TABLE = None
_PERCENTILE = None


def hand_class(c1, c2):
    r1, r2 = c1 >> 2, c2 >> 2
    if r1 < r2:
        r1, r2 = r2, r1
    if r1 == r2:
        return RANKS[r1] * 2
    return RANKS[r1] + RANKS[r2] + ("s" if (c1 & 3) == (c2 & 3) else "o")


def _combos(cls):
    return 6 if len(cls) == 2 else (4 if cls[2] == "s" else 12)


def _load():
    global _TABLE, _PERCENTILE
    with open(_TABLE_PATH) as f:
        _TABLE = json.load(f)
    # Percentile rank of each class among all 1326 combos, using heads-up equity:
    # 0.0 = best hand (AA), 1.0 = worst. "Top 15%" means percentile < 0.15.
    order = sorted(_TABLE, key=lambda c: -_TABLE[c][0])
    _PERCENTILE, seen = {}, 0
    for cls in order:
        _PERCENTILE[cls] = seen / 1326
        seen += _combos(cls)


def equity(c1, c2, opponents=1):
    if _TABLE is None:
        _load()
    return _TABLE[hand_class(c1, c2)][max(1, min(7, opponents)) - 1]


def percentile(c1, c2):
    if _PERCENTILE is None:
        _load()
    return _PERCENTILE[hand_class(c1, c2)]
