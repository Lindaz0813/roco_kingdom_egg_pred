"""
Egg hatch prediction algorithm.

Rule: pokemon_stat ≈ egg_stat × multiplier, where multiplier ∈ [2.4, 2.8] (±0.03 tolerance)

Scoring:
  1. Overlap ratio between expected range and pokemon's stat range (60%)
  2. Gaussian fit of the expected center within the pokemon's range (40%)
  3. Observation boost — two layers:
     a. LOCAL boost: confirmed observations for similar eggs (within 20% tolerance)
        — weighted by closeness, multiplied into the base score with high gain
     b. GLOBAL prior: total confirmation count across all eggs
        — gives a small lift to frequently-confirmed pokemon
     Confirmed pokemon that have zero base overlap are still injected at a
     meaningful minimum score so they always appear in results.
"""

import math

MULT_MIN  = 2.4
MULT_MAX  = 3.5
MULT_MID  = (MULT_MIN + MULT_MAX) / 2   # 2.95
TOLERANCE = 0.03  # ±0.03 M/KG leniency on each edge of the expected range

# How much a single perfect local observation multiplies the base score
LOCAL_BOOST_GAIN   = 5.0   # score *= (1 + accumulated * LOCAL_BOOST_GAIN)
# Small lift per global confirmation (independent of egg similarity)
GLOBAL_BOOST_GAIN  = 0.3   # score *= (1 + count * GLOBAL_BOOST_GAIN)
# Similarity window for local observations (fraction of egg stat)
SIM_TOLERANCE      = 0.20  # 20%


def overlap(a_min: float, a_max: float, b_min: float, b_max: float) -> float:
    return max(0.0, min(a_max, b_max) - max(a_min, b_min))


def gaussian_score(value: float, range_min: float, range_max: float,
                   sigma_factor: float = 0.5) -> float:
    center = (range_min + range_max) / 2
    width  = range_max - range_min
    sigma  = max(width * sigma_factor, 0.01)
    if range_min <= value <= range_max:
        return math.exp(-0.5 * ((value - center) / sigma) ** 2)
    dist = min(abs(value - range_min), abs(value - range_max))
    return math.exp(-0.5 * (dist / sigma) ** 2)


def predict(
    egg_size: float,
    egg_weight: float,
    pokemon_data: list,
    observations: list,
    top_n: int = 10,
) -> list:
    # ------------------------------------------------------------------ #
    # 1. Expected stat ranges
    # ------------------------------------------------------------------ #
    exp_size_min    = egg_size   * MULT_MIN - TOLERANCE
    exp_size_max    = egg_size   * MULT_MAX + TOLERANCE
    exp_weight_min  = egg_weight * MULT_MIN - TOLERANCE
    exp_weight_max  = egg_weight * MULT_MAX + TOLERANCE
    exp_size_center = egg_size   * MULT_MID
    exp_wt_center   = egg_weight * MULT_MID

    hatchable = [p for p in pokemon_data if p.get("is_hatchable", True)]

    # ------------------------------------------------------------------ #
    # 2. Base scores from stat overlap
    # ------------------------------------------------------------------ #
    raw_scores: dict = {}

    exp_s_span = exp_size_max   - exp_size_min
    exp_w_span = exp_weight_max - exp_weight_min

    for p in hatchable:
        s_min, s_max = p["size_min"],   p["size_max"]
        w_min, w_max = p["weight_min"], p["weight_max"]

        s_ov = overlap(exp_size_min,   exp_size_max,   s_min, s_max)
        w_ov = overlap(exp_weight_min, exp_weight_max, w_min, w_max)

        if s_ov <= 0 and w_ov <= 0:
            continue

        s_ratio = s_ov / exp_s_span if exp_s_span > 0 else (1.0 if s_ov > 0 else 0.0)
        w_ratio = w_ov / exp_w_span if exp_w_span > 0 else (1.0 if w_ov > 0 else 0.0)

        s_gauss = gaussian_score(exp_size_center, s_min, s_max)
        w_gauss = gaussian_score(exp_wt_center,   w_min, w_max)

        s_score = 0.6 * s_ratio + 0.4 * s_gauss
        w_score = 0.6 * w_ratio + 0.4 * w_gauss

        if s_ov > 0 and w_ov > 0:
            base = (s_score + w_score) / 2
        elif s_ov > 0:
            base = s_score * 0.3
        else:
            base = w_score * 0.3

        raw_scores[p["name"]] = base

    # ------------------------------------------------------------------ #
    # 3. Observation boosts
    # ------------------------------------------------------------------ #
    size_tol   = egg_size   * SIM_TOLERANCE
    weight_tol = egg_weight * SIM_TOLERANCE

    # 3a. Local boost — similar eggs only
    local_boosts:  dict = {}
    # 3b. Global prior — all confirmations
    global_counts: dict = {}

    for obs in observations:
        name = obs.get("pokemon", "")
        if not name:
            continue

        global_counts[name] = global_counts.get(name, 0) + 1

        obs_size   = obs.get("egg_size",   0)
        obs_weight = obs.get("egg_weight", 0)

        if (abs(obs_size   - egg_size)   <= size_tol and
                abs(obs_weight - egg_weight) <= weight_tol):
            s_close = 1.0 - abs(obs_size   - egg_size)   / (size_tol   + 1e-9)
            w_close = 1.0 - abs(obs_weight - egg_weight) / (weight_tol + 1e-9)
            closeness = (s_close + w_close) / 2
            local_boosts[name] = local_boosts.get(name, 0) + closeness

    # Find max base score so we can give confirmed-but-no-overlap entries
    # a meaningful floor score
    max_base = max(raw_scores.values()) if raw_scores else 1.0

    # Apply local boost
    for name, boost in local_boosts.items():
        if name in raw_scores:
            raw_scores[name] *= (1 + boost * LOCAL_BOOST_GAIN)
        else:
            # Confirmed for a similar egg but no stat overlap — inject at floor
            raw_scores[name] = max_base * 0.4 * min(boost, 1.0)

    # Apply global prior (only to pokemon already in the result set)
    for name, count in global_counts.items():
        if name in raw_scores:
            raw_scores[name] *= (1 + count * GLOBAL_BOOST_GAIN)

    if not raw_scores:
        return []

    # ------------------------------------------------------------------ #
    # 4. Normalise → percentages
    # ------------------------------------------------------------------ #
    total = sum(raw_scores.values())
    results = []
    for p in hatchable:
        name = p["name"]
        if name not in raw_scores:
            continue
        pct = round((raw_scores[name] / total) * 100, 1)
        if pct < 0.1:
            continue
        results.append({
            "name":            name,
            "probability":     pct,
            "size_range":      f"{p['size_min']}~{p['size_max']}M",
            "weight_range":    f"{p['weight_min']}~{p['weight_max']}KG",
            "confirmed_count": global_counts.get(name, 0),
        })

    results.sort(key=lambda x: -x["probability"])
    return results[:top_n]
