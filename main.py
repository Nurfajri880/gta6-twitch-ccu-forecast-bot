"""GTA VI launch-day Twitch viewer forecast (gta6-twitch-ccu-forecast-01).

Forecasts, for each hour 2..24 of the release day, five quantiles of that
hour's concurrent Twitch viewers in the Grand Theft Auto VI category.

Method (empirical launch-day shape, conditioned on the first hour):
  Every past big launch in the case's `comparables` has a full launch-day
  curve (hourly viewers from 14 days before to 3 days after release).  For
  each comparable we form the log-ratio of every hour to that launch's hour 1:

      r_h = ln(viewers_h / viewers_1),  h = 2..24.

  Hour 1 already encodes the launch's scale and how far the rolling
  midnight-local unlock had got by 00:00 UTC, so the ratio is the shape and
  hour 1's print is the level.  The forecast for hour h is hour 1's print
  times the empirical quantiles of r_h across the comparables that resemble
  this launch:

      q_tau(h) = p1 * exp(quantile_tau({r_h})),  tau in 0.05/0.25/0.5/0.75/0.95.

  The pool is every comparable with a full launch-day curve, except the
  early-access launches and weak analogues named in EXCLUDED_NAMES (their
  launch day is flat for the wrong reason: their real peak fell on the
  early-access day).  No launch is dropped for being small or for exploding:
  the conditioning is done by a weight, not a filter.  Each comparable's
  log-ratio is weighted by a Gaussian kernel on the distance between its
  log(hour 1) and this case's log(hour-1 print), bandwidth 1.0 in log units,
  so a huge launch is compared mostly with huge launches and a tiny one
  mostly with tiny ones, and the transition between scales is smooth.  That
  is what the scale law demands: a huge hour 1 means a flat day (the
  morning dip to about half, then a recovery), a tiny hour 1 means a day
  that climbs tens to hundreds of times, and one median shape for all
  would be badly wrong for both.

  The quantiles are the weighted quantiles of those log-ratios (linear
  interpolation on the cumulative weight).  No fitted parameters, no
  network, no randomness: the same input always yields the same bytes.

  What the program must do (per the rules):
  - read every <id>.in in the input directory (the grader runs one case at
    a time, with only that case's file there);
  - write <id>.out to the output directory: {"hours": [{"hour": h,
    "q": [q05, q25, q50, q75, q95]}, ...]}, exactly 23 rows, hours 2..24
    each once, each q five finite numbers above 0 and at most 1e9,
    non-decreasing, at most 65,536 bytes.

  Outside the grader's container, MAKEFUN_INPUT_DIR and MAKEFUN_OUTPUT_DIR
  stand in for /input and /output:
      mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py

  The grader runs `python3 -P -s /bot/main.py` (PYTHONHASHSEED=0) in
  python:3.13-slim, standard library only.
"""

import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first, so an
# `import model` finds a model.py shipped beside this file (none is shipped;
# this file is self-contained).
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The quantile levels the contest scores, in the order each row lists them.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]

# The shape of a launch day is governed by hour 1's size (the scale law:
# corr(log hour1, log peak ratio) is about -0.94; a huge hour 1 means a flat
# day, a tiny one a day that explodes).  So each comparable is weighted by
# how close its log(hour 1) is to this case's log(hour-1 print), with a
# Gaussian kernel of this bandwidth (in natural-log units, about a factor
# e^1.0 = 2.7 either way at one bandwidth).
BANDWIDTH = 1.0
MIN_POOL = 5

# Launches whose launch-day shape must not be learned from (research):
# the 9 early-access launches, whose real peak fell on the early-access day
# (so their launch day is flat for the wrong reason), and the 2 weak
# analogues.  GTA VI has no early access.
EXCLUDED_NAMES = frozenset([
    "Forza Horizon 5",
    "Hogwarts Legacy",
    "Diablo IV",
    "Starfield",
    "HELLDIVERS 2",
    "Marvel Rivals",
    "Assassin's Creed Shadows",
    "DOOM: The Dark Ages",
    "Death Stranding 2: On the Beach",
    "Forza Horizon 6",
    "007 First Light",
])


def round2(x):
    """x rounded to 2 decimals, half up, as JavaScript's Math.round(x*100)/100.

    A whole number comes back as an int, so json.dumps writes 1240 where
    JavaScript writes 1240 (not 1240.0).
    """
    scaled = x * 100.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100.0
    return int(value) if value == int(value) else value


def parse_time(text):
    """An ISO 8601 UTC timestamp into an aware datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def launch_day_curve(comparable):
    """A comparable's launch-day hourly viewers, {hour: viewers} for 1..24.

    Returns None when the comparable has no usable launch day (no hour-1
    point, or fewer than 20 of the 23 hours 2..24).  The Grand Theft Auto VI
    pre-release comparable has no launch day at all and is dropped here.
    """
    try:
        day_start = parse_time(comparable["day_start"])
    except (KeyError, ValueError, TypeError):
        return None
    by_hour = {}
    for point in comparable.get("hourly") or []:
        try:
            at = parse_time(point["from"])
            viewers = float(point["viewers"])
        except (KeyError, ValueError, TypeError):
            continue
        if day_start <= at < day_start + timedelta(hours=24):
            hour = int((at - day_start).total_seconds() // 3600) + 1
            if 1 <= hour <= 24 and viewers > 0:
                by_hour[hour] = viewers
    if 1 not in by_hour:
        return None
    if sum(1 for h in range(2, 25) if h in by_hour) < 20:
        return None
    return by_hour


def weighted_quantile(pairs, level):
    """The weighted quantile of (value, weight) pairs at `level`.

    Values are sorted; the quantile is the value where the cumulative
    weight first reaches `level` of the total weight, linearly interpolated
    between the two bracketing values.  A single pair returns its value.
    """
    ordered = sorted(pairs, key=lambda p: p[0])
    total = sum(w for _, w in ordered)
    if total <= 0:
        raise ValueError("weighted quantile with no positive weight")
    if len(ordered) == 1:
        return ordered[0][0]
    target = level * total
    acc = 0.0
    for i, (value, weight) in enumerate(ordered):
        prev = acc
        acc += weight
        if acc >= target:
            if i == 0 or prev >= target:
                return value
            # Interpolate between this value and the previous one.
            span = acc - prev
            frac = (target - prev) / span if span > 0 else 0.0
            return ordered[i - 1][0] * (1.0 - frac) + value * frac
    return ordered[-1][0]


def comparable_pool(case, p1):
    """The comparables usable for this case, as (hour1, {hour: viewers}) pairs.

    Every comparable with a full launch-day curve is usable, whatever its
    scale: the kernel in hour_quantiles does the conditioning, so a tiny
    hour-1 launch still learns from the tiny launches that explode, and a
    huge one from the huge launches that stay flat.  Only the launches in
    EXCLUDED_NAMES are dropped outright (early-access contamination and weak
    analogues).  A comparable with no launch day at all (the GTA VI
    pre-release comparable) is dropped by launch_day_curve.
    """
    usable = []
    for comp in case.get("comparables") or []:
        if comp.get("name") in EXCLUDED_NAMES:
            continue
        curve = launch_day_curve(comp)
        if curve is None:
            continue
        usable.append((curve[1], curve))
    return usable


def hour_quantiles(pool, p1, hour):
    """The five forecast quantiles for one hour, from the pool's log-ratios.

    Each comparable's log-ratio is weighted by a Gaussian kernel on the
    distance between its log(hour 1) and this case's log(hour-1 print):
    launches at the same scale dominate, launches at a very different scale
    count for almost nothing.  The quantiles are the weighted quantiles of
    those log-ratios, exponentiated back and scaled by hour 1's print.
    """
    log_p1 = math.log(max(1.0, p1))
    pairs = []
    for h1, curve in pool:
        if hour not in curve:
            continue
        dist = math.log(max(1.0, h1)) - log_p1
        weight = math.exp(-0.5 * (dist / BANDWIDTH) ** 2)
        pairs.append((math.log(curve[hour] / h1), weight))
    if not pairs:
        # No comparable has this hour: fall back to hour 1's print, flat.
        return [round2(p1)] * 5
    out = []
    for level in LEVELS:
        value = p1 * math.exp(weighted_quantile(pairs, level))
        out.append(round2(value))
    # Enforce non-decreasing and the contest's bounds, in that order.
    for i in range(1, len(out)):
        if out[i] < out[i - 1]:
            out[i] = out[i - 1]
    return [max(1, min(1e9, v)) for v in out]


def forecast_case(case, name):
    """The forecast object for one case dict."""
    if case.get("levels") != LEVELS:
        raise ValueError(f"{name} asks for levels {case.get('levels')}, not {LEVELS}")
    known = case.get("known") or []
    first = next((k for k in known if k.get("hour") == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1.0, float(first["viewers"]))
    pool = comparable_pool(case, p1)
    if not pool:
        raise ValueError(f"{name} has no usable comparables")
    hours = []
    for row in case.get("forecast") or []:
        hour = int(row["hour"])
        hours.append({"hour": hour, "q": hour_quantiles(pool, p1, hour)})
    hours.sort(key=lambda r: r["hour"])
    return {"hours": hours}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        text = json.dumps(forecast, separators=(",", ":")) + "\n"
        (OUTPUT_DIR / f"{path.stem}.out").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
