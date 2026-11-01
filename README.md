# nlhe-pokerbot

A no-limit Texas hold'em tournament bot in pure Python that decides in well under 1 ms, plus a local 8-seat sit-and-go simulator to test it.

Built as practice for timed bot-building competitions, where each decision has a hard 1 ms limit and the bot runs offline in a sandbox.

## Results

300 simulated tables, 8 seats each, 2,000-chip stacks, blinds from 10/20 rising every 25 hands, 200-hand cap with ICM payout for survivors, payouts 50/30/20:

| Bot | Avg payout | vs fair share (12.5) |
|---|---|---|
| **Agent (this bot)** | **27.7** | **2.2x** |
| TightPassive (top 15% of hands, never raises) | 15.8 | 1.3x |
| Maniac (all-in every hand) | 4.3 | 0.3x |
| RandomBot | 3.7 | 0.3x |
| CallingStation | 1.4 | 0.1x |

Decision time: median about 7 µs, 99th percentile about 290 µs. A handful of decisions in 70,000 ran past 1 ms; a trivial operation on the same machine showed the same spikes, so they come from host scheduling, not the bot.

These opponents are weak on purpose. Beating them shows the bot is sound, not that it would beat strong bots.

## How it decides

| Situation | Approach |
|---|---|
| Preflop, ≤ 12 big blinds | Push/fold. The shove range widens as the stack shrinks and fewer players are left to act. Calling an all-in requires equity above pot odds plus an **ICM risk premium**. |
| Preflop, deeper | Open-raise 2.5 bb with a range that depends on how many players act after us; re-raise only premium hands; call when equity clears the price. |
| Postflop | **Monte Carlo equity** against the opponents still in the hand, stopped by a 250 µs time budget. Bet for value, call on pot odds, otherwise check or fold. |

Speed comes from three choices:

- **Precomputed preflop table:** equity of all 169 starting hands against 1 to 7 opponents, built once ([`scripts/build_preflop_table.py`](scripts/build_preflop_table.py)). Lookups are O(1). Values match published equities within about 1%.
- **Bit-mask hand evaluator:** scores any 5 to 7 cards in about 4 µs in CPython ([`pokerbot/cards.py`](pokerbot/cards.py)).
- **Bounded work:** postflop sampling stops at its time budget, exact ICM runs only with 5 or fewer players left, and garbage collection is paused during a decision.

## Run it

Python 3.9+, no dependencies.

```bash
python simulate.py 300        # 300 tournaments, prints results and timing
python tests/test_core.py     # evaluator, ICM and engine checks
python -m scripts.build_preflop_table 3000   # rebuild the preflop table (~1 min)
```

## Files

```
pokerbot/agent.py        the bot
pokerbot/cards.py        card parsing and the hand evaluator
pokerbot/preflop.py      preflop equity and percentile lookups
pokerbot/icm.py          Independent Chip Model and risk premium
pokerbot/engine.py       sit-and-go simulator (side pots, blinds, 1 ms limit, ICM payout)
pokerbot/baselines.py    test opponents
simulate.py              tournament runner
```

## Limitations

- Opponents are not modeled: the bot plays the same against everyone.
- Postflop equity assumes opponents hold random hands, which overrates our hands when someone bets big.
- Python makes 1 ms tight. Under a slower grader, lower `POSTFLOP_BUDGET` in `agent.py`.

## Credits

Written by Taewoo Lim with Claude (Anthropic) as an AI pair programmer.
