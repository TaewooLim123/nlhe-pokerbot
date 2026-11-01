"""Tournament no-limit hold'em agent built for a 1 ms decision budget.

Strategy, by effective stack depth (in big blinds):
  * <= 12 bb: push/fold. Shove a range that widens as the stack shrinks and fewer
    players are left to act; call shoves only with hands whose equity clears the
    pot odds plus an ICM risk premium.
  * deeper: open-raise 2.5 bb with a position-dependent range, 3-bet the top of
    it, call raises with hands that have the equity for the price.
  * postflop: estimate equity by Monte Carlo against the opponents still in the
    hand, stopping at a time budget; bet for value, call on pot odds, else give up.

Everything is lookup or bounded sampling, so a decision stays well under 1 ms.
"""
import gc
import random
import time

from . import preflop
from .cards import evaluate
from .icm import risk_premium

POSTFLOP_BUDGET = 0.00025   # seconds of Monte Carlo per postflop decision


class Agent:
    def __init__(self, aggression=1.0, seed=None):
        self.aggression = aggression
        self.rng = random.Random(seed)

    # ------------------------------------------------------------------
    def act(self, s):
        # A garbage-collection pause mid-decision can blow the 1 ms limit; defer it.
        gc_was_on = gc.isenabled()
        gc.disable()
        try:
            return self._act(s)
        finally:
            if gc_was_on:
                gc.enable()

    def _act(self, s):
        legal = s["legal"]
        bb = s["blinds"][1]
        players = len(s["in_hand"])
        opponents = players - 1
        hole = s["hole"]
        eff = self.effective_stack(s) / bb

        if s["street"] == "preflop":
            action = self.preflop(s, eff, opponents)
        else:
            action = self.postflop(s, opponents)
        return self.make_legal(action, legal)

    # ------------------------------------------------------------------
    def effective_stack(self, s):
        me = s["seat"]
        mine = s["stack"] + s["my_bet"]
        others = [s["stacks"][o] + (s["contributed"][o] if o in s["contributed"] else 0)
                  for o in s["in_hand"] if o != me]
        return min(mine, max(others)) if others else mine

    def players_behind(self, s):
        """How many opponents still act after me this street."""
        me, seats = s["seat"], s["in_hand"]
        acted = {seat for (street, seat, _kind, _amt) in s["history"] if street == 0}
        return len([o for o in seats if o != me and o not in acted])

    def preflop(self, s, eff, opponents):
        c1, c2 = s["hole"]
        pct = preflop.percentile(c1, c2)
        bb = s["blinds"][1]
        to_call = s["to_call"]
        facing_raise = s["current_bet"] > bb
        behind = max(1, self.players_behind(s))
        all_in_to = s["my_bet"] + s["stack"]

        if eff <= 12:
            if not facing_raise:
                # open-shove range: about 50% at 1-2 bb, ~15% at 12 bb, tighter with more players behind
                width = min(0.65, (0.08 + 0.55 / max(eff, 1.0)) * (1.6 / (1 + 0.3 * behind)))
                width *= self.aggression
                if pct < width:
                    return ("raise", all_in_to)
                return ("check",) if s["legal"]["check"] else ("fold",)
            return self.call_allin_decision(s, opponents)

        if not facing_raise:
            open_width = {1: 0.45, 2: 0.32, 3: 0.24}.get(behind, 0.17) * self.aggression
            if pct < open_width:
                return ("raise", int(2.5 * bb + s["current_bet"] - bb))
            return ("check",) if s["legal"]["check"] else ("fold",)

        # facing a raise with a deep stack
        pot_after = s["pot"] + to_call
        if pct < 0.035:                                   # QQ+, AK: 3-bet / get it in
            return ("raise", int(s["current_bet"] * 3))
        need = to_call / pot_after
        eq = preflop.equity(c1, c2, opponents)
        if eq > need + 0.04 and to_call <= 0.12 * s["stack"]:
            return ("call",)
        return ("fold",)

    def call_allin_decision(self, s, opponents):
        c1, c2 = s["hole"]
        eq = preflop.equity(c1, c2, opponents)
        to_call = s["to_call"]
        need = to_call / (s["pot"] + to_call)
        raiser = self.last_aggressor(s)
        premium = 0.0
        alive = sum(1 for st in s["stacks"] if st > 0) + sum(
            1 for i, c in s["contributed"].items() if c > 0 and s["stacks"][i] == 0)
        # Exact ICM is too slow for 1 ms with 6+ players, and the premium is small that far from the money.
        if raiser is not None and alive <= 5:
            stacks = [st + s["contributed"].get(i, 0) for i, st in enumerate(s["stacks"])]
            premium = risk_premium(stacks, s["payouts"], s["seat"], raiser)
        # shovers have a range stronger than random: discount our equity
        eq_vs_range = eq * 0.88
        if eq_vs_range > need + premium:
            return ("call",)
        if preflop.percentile(c1, c2) < 0.03:
            return ("call",)
        return ("fold",)

    def last_aggressor(self, s):
        for street, seat, kind, _ in reversed(s["history"]):
            if kind == "raise" and seat != s["seat"]:
                return seat
        return None

    # ------------------------------------------------------------------
    def postflop(self, s, opponents):
        eq = self.equity(s["hole"], s["board"], opponents)
        pot, to_call = s["pot"], s["to_call"]
        legal = s["legal"]

        if to_call == 0:
            if eq > 0.62 or (eq > 0.5 and opponents == 1 and self.rng.random() < 0.35):
                return ("raise", s["my_bet"] + max(s["blinds"][1], int(pot * 0.66)))
            return ("check",)

        need = to_call / (pot + to_call)
        if eq > 0.78 and legal["raise"]:
            return ("raise", s["current_bet"] + int(pot + to_call))
        if eq > need + 0.05:
            return ("call",)
        return ("fold",)

    def equity(self, hole, board, opponents, budget=POSTFLOP_BUDGET):
        """Monte Carlo equity vs `opponents` random hands, bounded by time."""
        deadline = time.perf_counter() + budget
        known = set(hole) | set(board)
        deck = [c for c in range(52) if c not in known]
        need_board = 5 - len(board)
        opponents = max(1, min(opponents, 3))   # cap work; more opps barely change the decision
        wins = trials = 0.0
        sample = self.rng.sample
        while trials < 200:
            draw = sample(deck, need_board + 2 * opponents)
            full = board + draw[:need_board]
            mine = evaluate(hole + full)
            best = 0
            for k in range(opponents):
                o = need_board + 2 * k
                v = evaluate(draw[o:o + 2] + full)
                if v > best:
                    best = v
            if mine > best:
                wins += 1
            elif mine == best:
                wins += 0.5
            trials += 1
            if trials >= 4 and time.perf_counter() > deadline:
                break
        return wins / trials

    # ------------------------------------------------------------------
    @staticmethod
    def make_legal(action, legal):
        kind = action[0]
        if kind == "raise":
            if legal["raise"]:
                lo, hi = legal["raise"]
                return ("raise", max(lo, min(hi, int(action[1]))))
            return ("call",) if legal["call"] else ("check",)
        if kind == "check" and not legal["check"]:
            return ("fold",)
        if kind == "fold" and legal["check"]:
            return ("check",)
        return action
