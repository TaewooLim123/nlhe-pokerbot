# nlhe-pokerbot

A no-limit Texas hold'em tournament bot in Python, built to decide within a 1 ms limit, plus a local 8-player sit-and-go simulator for testing it.

## Features

- **Bot:** push/fold play when short-stacked, position-based opening ranges, and Monte Carlo equity estimates after the flop.
- **Hand evaluator:** scores 5–7 card hands.
- **Preflop table:** precomputed equity for all 169 starting hands.
- **ICM:** tournament payout model used for all-in decisions near the money.
- **Simulator:** 8-seat tournaments with rising blinds, side pots and a per-decision time limit.

## Tech stack

- Python 3 (standard library only)

## Run

```bash
python simulate.py 300        # run 300 simulated tournaments
python tests/test_core.py     # run the tests
```

Written with Claude as an AI pair programmer.
