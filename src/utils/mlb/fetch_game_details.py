import logging
import pandas as pd
from utils.config_loader import load_config
from utils.helpers import RatingCalculator, FeatureConfigLoader
from utils.mlb.get_mlb_player_stats import lookup_stats


def fetch_game_details(game, df_pitch, df_bat, features_cfg):
    game_id = game["gamePk"]
    probables = game.get("probablePitchers", {})
    lineups = game.get("previewBattingOrders", {})

    rating_calculator = RatingCalculator(features_cfg)
    pitchers = []
    batters_list = []

    for side in ("away", "home"):
        prob = probables.get(side)
        lineup = lineups.get(side, [])
        game[f"{side}_pitcher_score"] = None
        game[f"{side}_batter_score"] = None

        # --- Pitcher Score ---
        if prob:
            pstats = lookup_stats(
                prob['id'], prob['fullName'], df_pitch, "pitching")
            pscore = rating_calculator.compute_score(pstats)
            game[f"{side}_pitcher_score"] = pscore

            pitchers.append({
                "game_id": game_id,
                "side": side,
                "id": prob["id"],
                "name": prob["fullName"],
                "team": game[f"{side}Team"]["team"]["abbreviation"],
                "score": pscore
            })

        # --- Batter Score ---
        batter_stats = []
        for b in lineup:
            pid = b.get("id")
            bstats = lookup_stats(pid, b.get("name", ""),
                                  df_bat, "hitting") if pid else {}
            batter_stats.append(bstats)

            batters_list.append({
                "game_id": game_id,
                "side": side,
                "id": pid,
                "name": b.get("name", ""),
                "team": game[f"{side}Team"]["team"]["abbreviation"],
            })

        # Aggregate top-of-lineup hitter stats and score
        if batter_stats:
            avg_batter_features = {}
            for k in set().union(*[bs.keys() for bs in batter_stats]):
                try:
                    values = [float(bs[k]) for bs in batter_stats if k in bs]
                    avg_batter_features[k] = sum(values) / len(values)
                except Exception:
                    continue

            bscore = rating_calculator.compute_score(avg_batter_features)
            game[f"{side}_batter_score"] = bscore

    return pitchers, batters_list
