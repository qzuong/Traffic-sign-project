"""Frozen experimental policies. This module is used only by offline QA."""
RISK_CLASSES = frozenset((*range(11), 12, 13, 14, 15, 16, 17, 32, *range(33, 41)))
NUMERIC_LIMITS = frozenset((0, 1, 2, 3, 4, 5, 7, 8))
POLICIES = ("stable", "margin_only", "selective_speed")

def block(row, policy):
    veto = row["baseline"]
    if policy == "stable":
        return veto
    if (policy == "selective_speed" and veto == "speed_face_unverified"
            and row["pred"] in NUMERIC_LIMITS and row["v_median"] >= 110
            and row["neutral"] >= .65 and row["red"] >= .10 and row["red_sectors"] >= 6
            and .72 <= row["width"]/row["height"] <= 1.35
            and min(row["width"], row["height"]) >= 18 and row["margin"] >= .95):
        veto = None
    if veto is None and row["pred"] in RISK_CLASSES and row["margin"] < .85:
        return "high_risk_margin"
    return veto
