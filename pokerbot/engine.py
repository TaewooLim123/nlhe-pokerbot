"""Local no-limit hold'em sit-and-go simulator.

Mirrors the No Limit tournament format as published in its rules: 8 seats,
2,000-chip stacks, blinds from 10/20 rising every 25 hands, and a 200-hand cap
after which survivors are paid by ICM. The real event ships its own engine and
agent template; this one exists to test strategies locally.

A bot is any object with act(state) -> action, where action is one of
("fold",), ("check",), ("call",), ("raise", total_bet_this_street).
Illegal actions, exceptions and slow decisions are treated like the real event
treats them: check if possible, otherwise fold.
"""
import random
import time

from .cards import evaluate
from .icm import icm

BLIND_LEVELS = [(10, 20), (15, 30), (25, 50), (40, 80), (60, 120), (100, 200),
                (150, 300), (250, 500), (400, 800), (600, 1200)]


class Table:
    def __init__(self, bots, stack=2000, hands_per_level=25, max_hands=200,
                 payouts=(50, 30, 20), time_limit=0.001, seed=None):
        self.bots = bots
        self.n = len(bots)
        self.stacks = [stack] * self.n
        self.hands_per_level = hands_per_level
        self.max_hands = max_hands
        self.payouts = list(payouts)
        self.time_limit = time_limit
        self.rng = random.Random(seed)
        self.button = self.rng.randrange(self.n)
        self.hand_no = 0
        self.bust_order = []          # seats in the order they busted
        self.timeouts = [0] * self.n
        self.errors = [0] * self.n
        self.decision_times = [[] for _ in range(self.n)]

    # ---- tournament ------------------------------------------------------
    def alive(self):
        return [i for i in range(self.n) if self.stacks[i] > 0]

    def run(self):
        while len(self.alive()) > 1 and self.hand_no < self.max_hands:
            self.play_hand()
        return self.results()

    def results(self):
        """Expected payout share per seat (sums to sum(payouts))."""
        alive = self.alive()
        prize = [0.0] * self.n
        places_left = len(alive)
        # busted players: last to bust takes the best remaining place
        for rank_from_bottom, seat in enumerate(self.bust_order):
            place = self.n - 1 - rank_from_bottom
            if place < len(self.payouts):
                prize[seat] = self.payouts[place]
        if len(alive) == 1:
            prize[alive[0]] = self.payouts[0]
        else:
            ev = icm([self.stacks[i] for i in alive], self.payouts[:places_left])
            for seat, v in zip(alive, ev):
                prize[seat] = v
        return prize

    # ---- one hand --------------------------------------------------------
    def next_alive(self, seat):
        for k in range(1, self.n + 1):
            s = (seat + k) % self.n
            if self.stacks[s] > 0:
                return s
        return seat

    def play_hand(self):
        level = min(self.hand_no // self.hands_per_level, len(BLIND_LEVELS) - 1)
        sb_amt, bb_amt = BLIND_LEVELS[level]
        self.hand_no += 1
        alive = self.alive()
        self.button = self.next_alive(self.button)
        if len(alive) == 2:
            sb, bb = self.button, self.next_alive(self.button)
        else:
            sb = self.next_alive(self.button)
            bb = self.next_alive(sb)

        deck = list(range(52))
        self.rng.shuffle(deck)
        hole = {s: [deck.pop(), deck.pop()] for s in alive}
        board_all = [deck.pop() for _ in range(5)]

        in_hand = set(alive)
        contributed = {s: 0 for s in alive}
        start_stacks = {s: self.stacks[s] for s in alive}

        def put(seat, amount):
            amount = min(amount, self.stacks[seat])
            self.stacks[seat] -= amount
            contributed[seat] += amount
            return amount

        street_bets = {s: 0 for s in alive}
        street_bets[sb] = put(sb, sb_amt)
        street_bets[bb] = put(bb, bb_amt)
        history = []

        for street, n_board in enumerate((0, 3, 4, 5)):
            board = board_all[:n_board]
            if street > 0:
                street_bets = {s: 0 for s in alive}
                first = self.next_alive(self.button)
            else:
                first = self.next_alive(bb)
            can_act = [s for s in in_hand if self.stacks[s] > 0]
            if len(in_hand) > 1 and (len(can_act) > 1 or
                                     any(street_bets[s] < max(street_bets.values()) for s in can_act)):
                self.betting_round(street, board, first, in_hand, street_bets, contributed,
                                   hole, put, bb_amt, history, (sb_amt, bb_amt))
            if len(in_hand) == 1:
                break

        self.award(in_hand, contributed, hole, board_all)
        for s in alive:
            if self.stacks[s] == 0 and start_stacks[s] > 0:
                self.bust_order.append(s)
        # players who bust in the same hand: the one who started with more places higher
        busted_now = [s for s in alive if self.stacks[s] == 0]
        if len(busted_now) > 1:
            k = len(busted_now)
            tail = sorted(self.bust_order[-k:], key=lambda s: start_stacks[s])
            self.bust_order[-k:] = tail

    def betting_round(self, street, board, first, in_hand, street_bets, contributed,
                      hole, put, bb_amt, history, blinds):
        current = max(street_bets.values())
        min_raise = bb_amt
        order = []
        s = first
        for _ in range(self.n):
            if s in in_hand:
                order.append(s)
            s = self.next_alive(s)
            if s == first:
                break
        to_act = [s for s in order if self.stacks[s] > 0]
        while to_act and len(in_hand) > 1:
            seat = to_act.pop(0)
            if seat not in in_hand or self.stacks[seat] == 0:
                continue
            others_can_act = [s for s in in_hand if s != seat and self.stacks[s] > 0]
            to_call = current - street_bets[seat]
            if to_call == 0 and not others_can_act:
                continue
            state = {
                "seat": seat,
                "hole": list(hole[seat]),
                "board": list(board),
                "street": ("preflop", "flop", "turn", "river")[street],
                "pot": sum(contributed.values()),
                "to_call": min(to_call, self.stacks[seat]),
                "current_bet": current,
                "my_bet": street_bets[seat],
                "min_raise_to": current + min_raise,
                "stack": self.stacks[seat],
                "stacks": list(self.stacks),
                "contributed": dict(contributed),
                "in_hand": sorted(in_hand),
                "button": self.button,
                "blinds": blinds,
                "hand_no": self.hand_no,
                "payouts": list(self.payouts),
                "history": list(history),
                "legal": self.legal(to_call, seat, current, min_raise, others_can_act, street_bets),
            }
            action = self.ask(seat, state)
            kind = action[0]
            if kind == "fold":
                in_hand.discard(seat)
            elif kind == "check":
                pass
            elif kind == "call":
                street_bets[seat] += put(seat, to_call)
            elif kind == "raise":
                target = action[1]
                added = put(seat, target - street_bets[seat])
                street_bets[seat] += added
                if street_bets[seat] > current:
                    raise_size = street_bets[seat] - current
                    if raise_size >= min_raise:   # full raise reopens action
                        min_raise = raise_size
                    current = street_bets[seat]
                    to_act = [s for s in order[order.index(seat) + 1:] + order[:order.index(seat)]
                              if s in in_hand and self.stacks[s] > 0]
            history.append((street, seat, kind, street_bets[seat]))

    def legal(self, to_call, seat, current, min_raise, others_can_act, street_bets):
        stack = self.stacks[seat]
        legal = {"fold": to_call > 0, "check": to_call == 0, "call": to_call > 0}
        max_to = street_bets[seat] + stack
        if others_can_act and stack > to_call:
            legal["raise"] = (min(current + min_raise, max_to), max_to)
        else:
            legal["raise"] = None
        return legal

    def ask(self, seat, state):
        legal = state["legal"]
        fallback = ("check",) if legal["check"] else ("fold",)
        t0 = time.perf_counter()
        try:
            action = self.bots[seat].act(state)
        except Exception:
            self.errors[seat] += 1
            return fallback
        dt = time.perf_counter() - t0
        self.decision_times[seat].append(dt)
        if dt > self.time_limit:
            self.timeouts[seat] += 1
            return fallback
        if not isinstance(action, tuple) or not action:
            return fallback
        kind = action[0]
        if kind in ("fold", "check", "call") and legal.get(kind):
            return (kind,)
        if kind == "fold":          # folding when you could check: just check
            return ("check",)
        if kind == "raise" and legal["raise"]:
            lo, hi = legal["raise"]
            return ("raise", int(max(lo, min(hi, action[1]))))
        if kind == "raise" and legal["call"]:
            return ("call",)
        return fallback

    def award(self, in_hand, contributed, hole, board):
        if len(in_hand) == 1:
            winner = next(iter(in_hand))
            self.stacks[winner] += sum(contributed.values())
            return
        scores = {s: evaluate(hole[s] + board) for s in in_hand}
        levels = sorted(set(contributed[s] for s in contributed if contributed[s] > 0))
        prev = 0
        for lvl in levels:
            pot = sum(min(c, lvl) - min(c, prev) for c in contributed.values())
            eligible = [s for s in in_hand if contributed[s] >= lvl]
            if not eligible:          # everyone at this level folded: give back
                eligible = [s for s in contributed if contributed[s] >= lvl]
                best = eligible
            else:
                top = max(scores[s] for s in eligible)
                best = [s for s in eligible if scores[s] == top]
            share, rem = divmod(pot, len(best))
            for s in sorted(best, key=lambda x: (x - self.button - 1) % self.n):
                self.stacks[s] += share + (1 if rem > 0 else 0)
                rem -= 1
            prev = lvl
