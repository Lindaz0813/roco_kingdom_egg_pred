"""
Egg hatch prediction algorithm.

Rule: pokemon_stat ≈ egg_stat × multiplier, where multiplier ∈ [2.5, 2.75]
So for a given egg, the expected pokemon size is in [egg_size×2.5, egg_size×2.75]
and similarly for weight.

Scoring uses overlap ratio between the expected range and each pokemon's stat range,
then applies a Bayesian-style boost from user-confirmed observations.
"""

import math

MULT_MIN = 2.4
MULT_MAX = 2.8
MULT_MID = (MULT_MIN + MULT_MAX) / 2  # 2.6
TOLERANCE = 0.03  # ±0.03 M/KG leniency applied to both edges of the expected range


def overlap(a_min: float, a_max: float, b_min: float, b_max: float) -> float:
    """Length of overlap between two intervals."""
    return max(0.0, min(a_max, b_max) - max(a_min, b_min))


def gaussian_score(value: float, range_min: float, range_max: float, sigma_factor: float = 0.5) -> float:
    """
    Score how well `value` (the predicted center) fits within [range_min, range_max].
    Returns 1.0 if the center is inside the range, decays with distance outside.
    sigma is proportional to the range width.
    """
    center = (range_min + range_max) / 2
    width = range_max - range_min
    sigma = max(width * sigma_factor, 0.01)

    if range_min <= value <= range_max:
        # Inside — score based on proximity to range center
        return math.exp(-0.5 * ((value - center) / sigma) ** 2)
    else:
        # Outside — distance-based penalty
        dist = min(abs(value - range_min), abs(value - range_max))
        return math.exp(-0.5 * (dist / sigma) ** 2)


def predict(
    egg_size: float,
    egg_weight: float,
    pokemon_data: list[dict],
    observations: list[dict],
    top_n: int = 10,
) -> list[dict]:
    """
    Predict which pokemon will hatch from an egg with the given size and weight.

    Returns a list of dicts: [{name, probability, size_range, weight_range, confirmed_count}]
    sorted by probability descending.
    """
    # Expected pokemon stat ranges (expanded by ±TOLERANCE on each edge)
    exp_size_min = egg_size * MULT_MIN - TOLERANCE
    exp_size_max = egg_size * MULT_MAX + TOLERANCE
    exp_weight_min = egg_weight * MULT_MIN - TOLERANCE
    exp_weight_max = egg_weight * MULT_MAX + TOLERANCE
    exp_size_center = egg_size * MULT_MID
    exp_weight_center = egg_weight * MULT_MID

    hatchable = [p for p in pokemon_data if p.get("is_hatchable", True)]

    raw_scores: dict[str, float] = {}

    for p in hatchable:
        s_min, s_max = p["size_min"], p["size_max"]
        w_min, w_max = p["weight_min"], p["weight_max"]

        # Primary: overlap between expected range and pokemon range
        s_overlap = overlap(exp_size_min, exp_size_max, s_min, s_max)
        w_overlap = overlap(exp_weight_min, exp_weight_max, w_min, w_max)

        if s_overlap <= 0 and w_overlap <= 0:
            continue  # No match at all, skip

        # Overlap ratio (0–1)
        exp_s_span = exp_size_max - exp_size_min
        exp_w_span = exp_weight_max - exp_weight_min
        s_ratio = s_overlap / exp_s_span if exp_s_span > 0 else (1.0 if s_overlap > 0 else 0.0)
        w_ratio = w_overlap / exp_w_span if exp_w_span > 0 else (1.0 if w_overlap > 0 else 0.0)

        # Secondary: Gaussian score for how well the predicted center lands in range
        s_gauss = gaussian_score(exp_size_center, s_min, s_max)
        w_gauss = gaussian_score(exp_weight_center, w_min, w_max)

        # Combined score: weight overlap ratio 60%, gaussian fit 40%
        s_score = 0.6 * s_ratio + 0.4 * s_gauss
        w_score = 0.6 * w_ratio + 0.4 * w_gauss

        # Both dimensions must have some evidence
        if s_overlap > 0 and w_overlap > 0:
            base_score = (s_score + w_score) / 2
        elif s_overlap > 0:
            base_score = s_score * 0.3  # Partial match, penalise heavily
        elif w_overlap > 0:
            base_score = w_score * 0.3
        else:
            continue

        raw_scores[p["name"]] = base_score

    # --- Learning boost from confirmed observations ---
    # Count how many times each pokemon was confirmed for similar eggs
    confirmation_boosts: dict[str, float] = {}

    for obs in observations:
        obs_size = obs.get("egg_size", 0)
        obs_weight = obs.get("egg_weight", 0)
        obs_pokemon = obs.get("pokemon", "")

        if not obs_pokemon:
            continue

        # Similarity: use relative tolerance (15% of egg stat)
        size_tol = egg_size * 0.15
        weight_tol = egg_weight * 0.15

        size_match = abs(obs_size - egg_size) <= size_tol
        weight_match = abs(obs_weight - egg_weight) <= weight_tol

        if size_match and weight_match:
            # Closer observations get stronger boost
            size_closeness = 1.0 - abs(obs_size - egg_size) / (size_tol + 1e-9)
            weight_closeness = 1.0 - abs(obs_weight - egg_weight) / (weight_tol + 1e-9)
            boost = (size_closeness + weight_closeness) / 2  # 0–1

            confirmation_boosts[obs_pokemon] = confirmation_boosts.get(obs_pokemon, 0) + boost

    # Apply boosts: multiply base score by (1 + accumulated_boost)
    for pokemon_name, boost in confirmation_boosts.items():
        if pokemon_name in raw_scores:
            raw_scores[pokemon_name] *= (1 + boost)
        else:
            # Pokemon not in base results but was confirmed — add it with minimum score
            # Find it in the hatchable list to get its ranges
            p = next((p for p in hatchable if p["name"] == pokemon_name), None)
            if p:
                raw_scores[pokemon_name] = boost * 0.1

    if not raw_scores:
        return []

    # Count confirmed observations per pokemon for display
    confirmed_counts: dict[str, int] = {}
    for obs in observations:
        obs_pokemon = obs.get("pokemon", "")
        if obs_pokemon:
            confirmed_counts[obs_pokemon] = confirmed_counts.get(obs_pokemon, 0) + 1

    # Normalise to percentages
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
            "name": name,
            "probability": pct,
            "size_range": f"{p['size_min']}~{p['size_max']}M",
            "weight_range": f"{p['weight_min']}~{p['weight_max']}KG",
            "confirmed_count": confirmed_counts.get(name, 0),
        })

    results.sort(key=lambda x: -x["probability"])
    return results[:top_n]
