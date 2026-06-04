DOLLARS_PER_POINT = 0.10
POINTS_PER_DOLLAR = {"bronze": 1, "silver": 1, "gold": 1.5, "platinum": 3}
TIER_THRESHOLDS = {"bronze": 0, "silver": 5000, "gold": 10000, "platinum": 25000}


def compute_tier(points_earned_12m: int) -> str:
    if points_earned_12m >= TIER_THRESHOLDS["platinum"]:
        return "platinum"
    elif points_earned_12m >= TIER_THRESHOLDS["gold"]:
        return "gold"
    elif points_earned_12m >= TIER_THRESHOLDS["silver"]:
        return "silver"
    return "bronze"
