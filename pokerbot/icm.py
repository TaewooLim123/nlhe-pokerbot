"""Independent Chip Model (Malmuth-Harville).

icm(stacks, payouts) -> each player's expected share of the prize pool.
Exact recursion; fine for the 8-player tables used here (cached by remaining set).
"""
from functools import lru_cache


def icm(stacks, payouts):
    stacks = tuple(stacks)
    payouts = tuple(payouts)
    n = len(stacks)

    @lru_cache(maxsize=None)
    def rec(remaining, place):
        # remaining: bitmask of players not yet placed; returns tuple of EVs
        ev = [0.0] * n
        if place >= len(payouts) or not remaining:
            return tuple(ev)
        total = sum(stacks[i] for i in range(n) if remaining >> i & 1)
        if total <= 0:
            return tuple(ev)
        for i in range(n):
            if not remaining >> i & 1 or stacks[i] <= 0:
                continue
            p = stacks[i] / total
            ev[i] += p * payouts[place]
            sub = rec(remaining & ~(1 << i), place + 1)
            for j in range(n):
                ev[j] += p * sub[j]
        return tuple(ev)

    alive = 0
    for i, s in enumerate(stacks):
        if s > 0:
            alive |= 1 << i
    return list(rec(alive, 0))


def risk_premium(stacks, payouts, me, villain):
    """Extra equity needed to call an all-in versus a chip-EV call (0 = none).

    Compares my ICM value if I win vs lose a pot against `villain`, against the
    break-even point implied by chip counts alone.
    """
    eff = min(stacks[me], stacks[villain])
    if eff <= 0:
        return 0.0
    now = icm(stacks, payouts)[me]
    win = list(stacks); win[me] += eff; win[villain] -= eff
    lose = list(stacks); lose[me] -= eff; lose[villain] += eff
    ev_win, ev_lose = icm(win, payouts)[me], icm(lose, payouts)[me]
    if ev_win - ev_lose <= 1e-12:
        return 0.0
    icm_breakeven = (now - ev_lose) / (ev_win - ev_lose)
    return max(0.0, icm_breakeven - 0.5)
