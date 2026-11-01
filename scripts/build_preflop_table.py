"""Precompute all-in equity of the 169 starting hands vs 1..7 random opponents.

Run once: python -m scripts.build_preflop_table [trials]
Writes pokerbot/preflop_equity.json. Monte Carlo, so values carry ~1% noise.
"""
import json
import os
import random
import sys
from multiprocessing import Pool

from pokerbot.cards import RANKS, evaluate


def representative(cls):
    hi, lo = RANKS.index(cls[0]), RANKS.index(cls[1])
    if len(cls) == 2:
        return [hi * 4, hi * 4 + 1]
    return [hi * 4, lo * 4 + (0 if cls[2] == "s" else 1)]


def equity_row(args):
    cls, trials = args
    rng = random.Random(hash(cls) & 0xFFFF)
    hero = representative(cls)
    deck = [c for c in range(52) if c not in hero]
    row = []
    for opps in range(1, 8):
        won = 0.0
        need = 5 + 2 * opps
        for _ in range(trials):
            draw = rng.sample(deck, need)
            board = draw[:5]
            mine = evaluate(hero + board)
            best, ties = 0, 0
            for k in range(opps):
                v = evaluate(draw[5 + 2 * k:7 + 2 * k] + board)
                if v > best:
                    best, ties = v, 1
                elif v == best:
                    ties += 1
            if mine > best:
                won += 1
            elif mine == best:
                won += 1 / (ties + 1)
        row.append(round(won / trials, 4))
    return cls, row


def all_classes():
    out = []
    for i in range(12, -1, -1):
        for j in range(i, -1, -1):
            if i == j:
                out.append(RANKS[i] * 2)
            else:
                out += [RANKS[i] + RANKS[j] + "s", RANKS[i] + RANKS[j] + "o"]
    return out


if __name__ == "__main__":
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    with Pool() as pool:
        rows = dict(pool.map(equity_row, [(c, trials) for c in all_classes()]))
    path = os.path.join(os.path.dirname(__file__), "..", "pokerbot", "preflop_equity.json")
    with open(path, "w") as f:
        json.dump(rows, f, indent=0)
    print(f"wrote {len(rows)} hands to {os.path.normpath(path)}")
