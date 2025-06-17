def minmax_scale(x, lo, hi):
    if x is None:
        return 0.5
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def pitcher_score(stats):
    b = BOUNDS
    f = {
        "era":    1 - minmax_scale(stats.get("era"),    *b["era"]),
        "whip":   1 - minmax_scale(stats.get("whip"),   *b["whip"]),
        "k_rate": minmax_scale(stats.get("strikeOutsPer9Inn")/9, *b["k_rate"]),
        "bb_rate": 1 - minmax_scale(stats.get("baseOnBallsPer9Inn")/9, *b["bb_rate"]),
        "f1_era": 1 - minmax_scale(stats.get("firstInningEra"), *b["f1_era"])
    }
    return sum(f.values()) / len(f)


def batter_score(feats):
    b = BOUNDS
    f = {
        "obp_vs":        feats["obp_vs"],
        "hr_rate":       minmax_scale(feats["hr_rate"], *b["hr_rate"]),
        "recent_f1_obp": feats["recent_f1_obp"]
    }
    return sum(f.values()) / len(f)


def compute_nrfi_score(pitch_stats, batt_feats, park, weather, team_pct, opp_pct):
    ps = pitcher_score(pitch_stats)
    bs = batter_score(batt_feats)
    pk = (park + weather) / 2
    tm = (team_pct + opp_pct) / 2

    w = WEIGHTS
    return (
        w["pitcher"] * ps +
        w["batter"] * bs +
        w["park"] * pk +
        w["team"] * tm
    )
