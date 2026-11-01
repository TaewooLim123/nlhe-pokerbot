"""Run sit-and-go tournaments and report how each bot does.

python simulate.py [tables] [seed]

Seats: our Agent plus a mix of baseline opponents. Seats are reshuffled every
table so position luck averages out. Payouts default to 50/30/20; points in the
real event are announced at the start of the build phase.
"""
import random
import statistics
import sys

from pokerbot.agent import Agent
from pokerbot.baselines import CallingStation, Maniac, RandomBot, TightPassive
from pokerbot.engine import Table


def lineup(rng):
    return [
        ("Agent", Agent(seed=rng.random())),
        ("Agent", Agent(seed=rng.random())),
        ("RandomBot", RandomBot(seed=rng.random())),
        ("RandomBot", RandomBot(seed=rng.random())),
        ("CallingStation", CallingStation()),
        ("Maniac", Maniac()),
        ("TightPassive", TightPassive()),
        ("TightPassive", TightPassive()),
    ]


def main(tables=200, seed=1):
    rng = random.Random(seed)
    totals, times, timeouts, errors = {}, [], 0, 0
    for t in range(tables):
        seats = lineup(rng)
        rng.shuffle(seats)
        table = Table([bot for _, bot in seats], seed=rng.random())
        prizes = table.run()
        for (name, _), p in zip(seats, prizes):
            totals.setdefault(name, []).append(p)
        for (name, _), dts, to, er in zip(seats, table.decision_times, table.timeouts, table.errors):
            if name == "Agent":
                times += dts
                timeouts += to
                errors += er
    fair = 100 / 8
    print(f"{tables} tables, 8 seats, payouts 50/30/20 (fair share = {fair:.1f} per seat)\n")
    print(f"{'bot':<16}{'avg payout':>11}{'vs fair':>9}")
    for name, vals in sorted(totals.items(), key=lambda kv: -statistics.mean(kv[1])):
        m = statistics.mean(vals)
        print(f"{name:<16}{m:>11.2f}{m / fair:>8.2f}x")
    times.sort()
    if times:
        p = lambda q: times[min(len(times) - 1, int(q * len(times)))] * 1e6
        print(f"\nAgent decisions: {len(times)}, median {p(0.5):.0f} us, "
              f"p99 {p(0.99):.0f} us, max {times[-1] * 1e6:.0f} us")
        print(f"Agent timeouts (>1 ms): {timeouts}, errors: {errors}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200,
         int(sys.argv[2]) if len(sys.argv) > 2 else 1)
