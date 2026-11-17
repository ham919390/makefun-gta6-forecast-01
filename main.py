"""gta6-twitch-ccu-forecast-01 entry: a comparable-launch curve-transfer forecast.

The house baseline assumes every hour of release day repeats hour 1. Real launches do not:
a console game that unlocks at midnight local time rolls around the planet, so by the time
the UTC day opens, New Zealand, Asia and part of Europe are already watching, the United
States unlocks a few hours in, and the day's peak usually lands in the transatlantic evening.
That shape is remarkably stable from one big launch to the next once each day is measured
relative to its own first hour, so this entry learns the shape from the case's own
comparables (past big launches' hourly Twitch counts, shipped inside every case file):

  - each comparable with a genuine first hour (its release day essentially complete and
    hour 1 at least 3% of its day's peak, which excludes simultaneous global unlocks whose
    hour 1 is still pre-launch silence) contributes its log-ratio curve
    L(h) = ln(viewers(h) / viewers(1)) for hours 2..24;
  - a comparable is weighted by how much it resembles this launch: a Gaussian kernel on the
    log of its hour-1 viewers against this case's hour-1 print (big launches move like big
    launches), a wider Gaussian kernel on its hour-1 channel count, a kernel on the
    pre-midnight ramp (the last hour before the UTC day against hour 1), and fixed discounts
    for launches the case notes flag as weak comparables (x0.25) or early-access
    contaminated (x0.45); the case's one non-launch comparable (the game's own category
    history) is excluded;
  - each hour's five quantiles blend the weighted empirical quantiles of the curves with a
    weighted normal fit around the empirical median, in log space, then scale hour 1's
    print by them. Quantiles are rounded to 2 decimals (half up), as the starter rounds.

If anything in a case is unusable (no comparable curve survives, say), the entry falls back
to the house baseline's persistence forecast for that case rather than crashing: an invalid
case costs far more than a plain forecast. Standard library only, no network, deterministic:
two runs write byte-identical files.

How the grader runs it: `python3 -P -s /bot/main.py` (PYTHONHASHSEED=0) in python:3.13-slim.
Outside the grader, MAKEFUN_INPUT_DIR and MAKEFUN_OUTPUT_DIR stand in for /input and /output.
"""

import json
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from statistics import NormalDist

# The grader's -P leaves /bot off sys.path: put it back first, so a module shipped beside
# this file would import. (This entry is a single file; the line costs nothing.)
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The quantile levels the contest scores, in the order each output row lists them.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# The standard normal's quantile at each level.
Z = [NormalDist().inv_cdf(tau) for tau in LEVELS]

# Model constants, tuned by leave-one-out scoring over the practice cases' comparables
# (each comparable in turn forecast from the others, scored with the contest's own pinball
# loss): the transfer scores about 0.265 there against the persistence baseline's 0.360.
SCALE_KERNEL = 1.0    # Gaussian width, in log viewers, for hour-1 size similarity
CHANNEL_KERNEL = 1.5  # Gaussian width, in log channels, for hour-1 channel similarity
PRE_KERNEL = 0.75     # Gaussian width for the pre-midnight ramp ratio, in log units
WEAK_WEIGHT = 0.25    # discount for comparables the notes flag "Tier: weak"
EARLY_ACCESS_WEIGHT = 0.45  # discount for early-access-contaminated launches
MIN_HOUR1_SHARE = 0.03  # hour 1 below this share of the day peak means a pre-launch hour 1
MIN_DAY_HOURS = 20    # a comparable's release day must be at least this complete
MIN_CURVE_HOURS = 18  # and yield at least this many ratio hours


def parse_ts(text):
    """An ISO 8601 UTC timestamp from the case files, as an aware datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def round2(x):
    """x rounded to 2 decimals, half up, as JavaScript's Math.round(x * 100) / 100 rounds it.

    A whole number comes back as an int, so json.dumps writes 1240 where JavaScript writes
    1240 (not 1240.0).
    """
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def day_table(comp):
    """A comparable's release day as {hour: (viewers, channels)}, hours 1..24."""
    start = parse_ts(comp["day_start"])
    table = {}
    for row in comp["hourly"]:
        at = parse_ts(row["from"])
        if start <= at < start + timedelta(hours=24):
            hour = int((at - start).total_seconds() // 3600) + 1
            if row["viewers"] is not None:
                table[hour] = (float(row["viewers"]), row.get("channels"))
    return table


def pre_ratio(comp, table):
    """ln(viewers in the hour before the UTC day / hour 1 viewers) for a comparable, or None."""
    if 1 not in table or table[1][0] <= 0:
        return None
    start = parse_ts(comp["day_start"])
    for row in comp["hourly"]:
        if parse_ts(row["from"]) == start - timedelta(hours=1) and row["viewers"]:
            return math.log(float(row["viewers"]) / table[1][0])
    return None


def comparable_curve(comp, target):
    """One comparable's (log-ratio curve, weight) for this case, or None if unusable.

    `target` carries this case's log hour-1 viewers, log hour-1 channels (or None) and
    pre-midnight ramp ratio (or None), the three things the similarity kernels compare.
    """
    table = day_table(comp)
    if 1 not in table or len(table) < MIN_DAY_HOURS:
        return None
    v1 = table[1][0]
    peak = max(v for v, _ in table.values())
    if v1 <= 0 or peak <= 0 or v1 / peak < MIN_HOUR1_SHARE:
        return None  # hour 1 was pre-launch silence (a simultaneous global unlock)
    curve = {h: math.log(v / v1) for h, (v, _) in table.items() if h >= 2 and v > 0}
    if len(curve) < MIN_CURVE_HOURS:
        return None
    text = (comp.get("unlock") or "").lower()
    if "not a launch" in text:
        return None  # the game's own category history, not a launch
    weight = 1.0
    if "tier: weak" in text:
        weight *= WEAK_WEIGHT
    if "early access" in text or "early-access" in text:
        weight *= EARLY_ACCESS_WEIGHT
    d = math.log(v1) - target["log_v1"]
    weight *= math.exp(-(d * d) / (2 * SCALE_KERNEL ** 2))
    ch1 = table[1][1]
    if target["log_ch1"] is not None and ch1:
        dc = math.log(float(ch1)) - target["log_ch1"]
        weight *= math.exp(-(dc * dc) / (2 * CHANNEL_KERNEL ** 2))
    if target["pre"] is not None:
        own_pre = pre_ratio(comp, table)
        if own_pre is not None:
            dp = own_pre - target["pre"]
            weight *= math.exp(-(dp * dp) / (2 * PRE_KERNEL ** 2))
    return curve, weight


def weighted_quantile(samples, tau):
    """The tau quantile of (value, weight) samples, linearly interpolated."""
    ordered = sorted(samples)
    total = sum(w for _, w in ordered)
    if total <= 0:
        return ordered[len(ordered) // 2][0]
    goal = tau * total
    cum = 0.0
    prev_v, prev_c = ordered[0][0], 0.0
    for v, w in ordered:
        cum += w
        if cum >= goal:
            if cum == w:
                return v
            return prev_v + (goal - prev_c) / w * (v - prev_v)
        prev_v, prev_c = v, cum
    return ordered[-1][0]


def model_quantiles(curves, log_p1):
    """The five log quantiles of every hour 2..24 from the weighted curves."""
    out = {}
    for h in range(2, 25):
        samples = [(curve[h], w) for curve, w in curves if h in curve]
        if not samples:
            out[h] = [log_p1] * len(LEVELS)
            continue
        total_w = sum(w for _, w in samples)
        mu = sum(v * w for v, w in samples) / total_w
        var = sum(w * (v - mu) ** 2 for v, w in samples) / total_w
        sd = math.sqrt(max(var, 1e-9))
        emp = [weighted_quantile(samples, tau) for tau in LEVELS]
        med = emp[len(LEVELS) // 2]
        qs = []
        for i in range(len(LEVELS)):
            normal_q = mu + Z[i] * sd
            qs.append(log_p1 + med + 0.5 * ((emp[i] - med) + (normal_q - med)))
        out[h] = qs
    return out


def baseline_quantiles(log_p1, hours):
    """The house baseline in log space: persistence with a widening random-walk spread."""
    return {h: [log_p1 + z * 0.15 * math.sqrt(h - 1) for z in Z] for h in hours}


def target_features(case, first):
    """This case's own similarity features, from its known row and hourly history."""
    p1 = max(1.0, float(first["viewers"]))
    features = {"log_v1": math.log(p1), "log_ch1": None, "pre": None}
    if first.get("channels"):
        features["log_ch1"] = math.log(float(first["channels"]))
    start = parse_ts(case["day_start"])
    for row in case.get("history_hourly") or []:
        if parse_ts(row["from"]) == start - timedelta(hours=1) and row["viewers"]:
            features["pre"] = math.log(float(row["viewers"]) / p1)
    return features


def forecast_case(case):
    """The forecast object for one case: {"hours": [{hour, q}, ...]} for hours 2..24."""
    first = next((k for k in case["known"] if k["hour"] == 1), None)
    if first is None:
        raise ValueError("case has no hour-1 print")
    p1 = max(1.0, float(first["viewers"]))
    log_p1 = math.log(p1)
    hours = [row["hour"] for row in case["forecast"]]
    try:
        target = target_features(case, first)
        curves = []
        for comp in case["comparables"]:
            got = comparable_curve(comp, target)
            if got is not None:
                curves.append(got)
        if len(curves) < 5:
            raise ValueError("too few usable comparables")
        log_qs = model_quantiles(curves, log_p1)
    except Exception:
        log_qs = baseline_quantiles(log_p1, hours)
    rows = []
    for h in hours:
        qs = [round2(math.exp(v)) for v in log_qs[h]]
        for i in range(1, len(qs)):
            if qs[i] < qs[i - 1]:
                qs[i] = qs[i - 1]
        rows.append({"hour": h, "q": qs})
    return {"hours": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
