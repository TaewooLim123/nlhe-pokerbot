"""Cards and a fast 5-7 card hand evaluator.

A card is an int 0..51: rank = card // 4 (0 = deuce ... 12 = ace), suit = card % 4.
evaluate() returns an int; higher is better. It runs in roughly 10-20 microseconds
for 7 cards in CPython, well inside a 1 ms decision budget.
"""

RANKS = "23456789TJQKA"
SUITS = "cdhs"

HIGH_CARD, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, FULL_HOUSE, QUADS, STRAIGHT_FLUSH = range(9)
CATEGORY_NAMES = ["High card", "Pair", "Two pair", "Trips", "Straight", "Flush",
                  "Full house", "Quads", "Straight flush"]

# 5-bit windows for straights, best first; the last one is the wheel (A-2-3-4-5).
_STRAIGHTS = [(0b11111 << lo, lo + 4) for lo in range(8, -1, -1)] + [(0b1000000001111, 3)]


def card(text):
    """'As' -> 51, 'Td' -> 33."""
    return RANKS.index(text[0].upper()) * 4 + SUITS.index(text[1].lower())


def cards(text):
    """'As Kd' or 'AsKd' -> [51, 46]."""
    text = text.replace(" ", "")
    return [card(text[i:i + 2]) for i in range(0, len(text), 2)]


def to_str(c):
    return RANKS[c // 4] + SUITS[c % 4]


def _straight_high(mask):
    for window, high in _STRAIGHTS:
        if mask & window == window:
            return high
    return -1


def _score(category, kickers):
    v = category
    for k in kickers[:5]:
        v = v * 16 + k
    for _ in range(5 - min(5, len(kickers))):
        v *= 16
    return v


def evaluate(hand):
    """Score the best 5-card hand from 5-7 cards."""
    counts = [0] * 13
    suit_masks = [0, 0, 0, 0]
    suit_counts = [0, 0, 0, 0]
    rank_mask = 0
    for c in hand:
        r, s = c >> 2, c & 3
        counts[r] += 1
        suit_masks[s] |= 1 << r
        suit_counts[s] += 1
        rank_mask |= 1 << r

    for s in range(4):
        if suit_counts[s] >= 5:
            fmask = suit_masks[s]
            sf = _straight_high(fmask)
            if sf >= 0:
                return _score(STRAIGHT_FLUSH, [sf])
            flush_ranks = [r for r in range(12, -1, -1) if fmask >> r & 1]
            best_flush = _score(FLUSH, flush_ranks)
            break
    else:
        best_flush = None

    quads, trips, pairs, singles = [], [], [], []
    for r in range(12, -1, -1):
        n = counts[r]
        if n == 4:
            quads.append(r)
        elif n == 3:
            trips.append(r)
        elif n == 2:
            pairs.append(r)
        elif n == 1:
            singles.append(r)

    if quads:
        q = quads[0]
        kicker = max(r for r in range(13) if counts[r] and r != q)
        return _score(QUADS, [q, kicker])
    if trips and (len(trips) > 1 or pairs):
        t = trips[0]
        p = max(trips[1:] + pairs)
        return _score(FULL_HOUSE, [t, p])
    if best_flush is not None:
        return best_flush
    st = _straight_high(rank_mask)
    if st >= 0:
        return _score(STRAIGHT, [st])
    if trips:
        return _score(TRIPS, [trips[0]] + singles[:2])
    if len(pairs) >= 2:
        kick = max(pairs[2:] + singles[:1]) if (pairs[2:] or singles) else 0
        return _score(TWO_PAIR, [pairs[0], pairs[1], kick])
    if pairs:
        return _score(PAIR, [pairs[0]] + singles[:3])
    return _score(HIGH_CARD, singles[:5])


def category(score):
    return score >> 20
