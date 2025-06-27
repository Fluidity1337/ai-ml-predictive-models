import logging
import logging.config
import sys
import json
import pandas as pd
from pathlib import Path
from utils.config_loader import load_config
from utils.helpers import FeatureConfigLoader
from utils.mlb.lookup_stats import lookup_stats  # If you split out lookup_stats
# OR inline it here if not already modularized


def fetch_game_details(game, df_pitch, df_bat, features_cfg, season):
    game_id = game.get("gamePk")
    logging.debug(f"[Game {game_id}] Processing game details")

    probables = {
        "away": game.get("teams", {}).get("away", {}).get("probablePitcher"),
        "home": game.get("teams", {}).get("home", {}).get("probablePitcher")
    }
    logging.debug(f"[{game_id}] Parsed probables from 'teams': {probables}")

    lineups = game.get("previewBattingOrders", {})

    pitchers, batters_list = [], []

    for side in ("away", "home"):
        logging.debug(f"[{game_id}] Side: {side}")
        prob = probables.get(side)
        lineup = lineups.get(side, [])
        logging.debug(f"[{game_id}] Probable pitcher: {prob}")
        logging.debug(f"[{game_id}] Lineup length: {len(lineup)}")

        # Pitcher stats
        if prob:
            try:
                pstats = lookup_stats(
                    prob['id'], prob['fullName'], df_pitch, "pitching", season=season
                )
                logging.debug(
                    f"[{game_id}] Pitcher stats found for {prob['fullName']}: {bool(pstats)}")
                pitchers.append({
                    "game_id": game_id,
                    "side": side,
                    "id": prob["id"],
                    "name": prob["fullName"],
                    "team": game["teams"][side]["team"]["name"],
                    "stats": pstats
                })
            except Exception as e:
                logging.warning(
                    f"[{game_id}] Failed to compute pitcher score for {prob['fullName']}: {e}")

        # Batter stats
        batter_stats = []
        for b in lineup:
            pid = b.get("id")
            name = b.get("name", "Unknown")
            if not pid:
                logging.warning("Skipping batter with missing ID: %s", name)
                batter_stats.append({})
                continue
            try:
                stats = lookup_stats(
                    pid, name, df_bat, "hitting", season=season)
                logging.debug("Fetched stats for batter %s (ID=%s)", name, pid)
            except Exception as e:
                logging.exception(
                    "Error fetching stats for batter %s (ID=%s): %s", name, pid, e)
                stats = {}
            batter_stats.append(stats)

        batters_list.extend(batter_stats)

    logging.info(
        f"[{game_id}] Final pitcher count: {len(pitchers)}, batter count: {len(batters_list)}")
    return pitchers, batters_list


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    cfg = load_config()
    features_path = cfg["models"]["mlb_rfi"]["feature_definitions_path"]
    with open(features_path, "r", encoding="utf-8") as f:
        features_cfg = json.load(f)

    game = {
        "gamePk": 777341,
        "teams": {
            "away": {
                "team": {"id": 121, "name": "New York Mets"},
                "probablePitcher": {"id": 656849, "fullName": "David Peterson"}
            },
            "home": {
                "team": {"id": 134, "name": "Pittsburgh Pirates"},
                "probablePitcher": {"id": 656605, "fullName": "Mitch Keller"}
            }
        },
        "previewBattingOrders": {
            "away": [
                {"id": 605412, "name": "Brandon Nimmo"},
                {"id": 592567, "name": "Francisco Lindor"},
                {"id": 621446, "name": "Pete Alonso"}
            ],
            "home": [
                {"id": 672284, "name": "Bryan Reynolds"},
                {"id": 666200, "name": "Ke'Bryan Hayes"},
                {"id": 657557, "name": "Jack Suwinski"}
            ]
        }
    }

    df_pitch = pd.DataFrame()
    df_bat = pd.DataFrame()

    ps, bs = fetch_game_details(game, df_pitch, df_bat, features_cfg, "2025")
    print(f"Pitchers: {len(ps)}, Batters: {len(bs)}")


if __name__ == "__main__":
    main()
