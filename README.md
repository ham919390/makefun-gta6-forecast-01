# makefun-gta6-forecast-01

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/ham919390/makefun-gta6-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/ham919390/makefun-gta6-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecasts Grand Theft Auto VI's Twitch category viewers for each hour of release day
(2026-11-19 UTC), as five quantiles per hour, from the only thing known at the deadline:
hour 1's count and the hourly curves of past big launches shipped inside the case file.

## Method

A console game unlocking at midnight local time rolls around the planet, so a launch day's
shape — measured relative to its own first hour — is stable across launches: the
already-unlocked regions carry hour 1, the US unlock lands a few hours in, and the peak
usually arrives in the transatlantic evening. `main.py` therefore:

1. takes every comparable in the case whose release day is essentially complete and whose
   hour 1 is a real launch hour (at least 3% of its day's peak — this drops simultaneous
   global unlocks, whose hour 1 is pre-launch silence), and forms its log-ratio curve
   `L(h) = ln(viewers(h) / viewers(1))`;
2. weights each curve by similarity to this launch: Gaussian kernels on hour-1 viewers
   (width 1.0 in log units), hour-1 channels (1.5) and the pre-midnight ramp ratio (0.75),
   with fixed discounts for comparables the case notes flag as weak (x0.25) or
   early-access contaminated (x0.45);
3. predicts each hour's quantiles by blending the curves' weighted empirical quantiles
   with a weighted normal fit around the empirical median, in log space, scaled by
   hour 1's print.

Constants were chosen by leave-one-out scoring over the practice cases' comparables with
the contest's own pinball loss: about 0.265, against the persistence baseline's 0.360.
If a case's data is unusable the program falls back to that baseline rather than crash.
Standard library only; deterministic; runs in well under a second per case.

Layout: `main.py` (the entry), `LICENSE` (MIT), `.makefun/owner.json` (the entrant
wallet claim file).

## Run it

```sh
MAKEFUN_INPUT_DIR=<case-dir> MAKEFUN_OUTPUT_DIR=<out-dir> python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=ej1tk366&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
