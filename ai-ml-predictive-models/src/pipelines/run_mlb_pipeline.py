# run_mlb_pipeline.py
import sys
from pathlib import Path
import requests
from datetime import datetime
import json
import csv
import os
import logging

sys.path.append(str(Path(__file__).resolve().parents[2]))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"
with open(CONFIG_PATH) as f:
    config = json.load(f)

RAW_DATA_DIR = Path(config["sports_baseball_mlb_raw_data_output_dir"]).resolve()
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

def fetch_mlb_schedule(date_str):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&hydrate=probablePitcher"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch schedule for {date_str}")
    data = response.json()
    return data.get("dates", [{}])[0].get("games", [])

def fetch_game_details(game):
    game_id = game.get("gamePk")
    if not game_id:
        return [], []

    url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
    response = requests.get(url)
    if response.status_code != 200:
        logging.warning(f"Failed to fetch boxscore for game {game_id}")
        return [], []
    data = response.json()

    pitchers = []
    batters = []

    for team_type in ["home", "away"]:
        team_info = game.get("teams", {}).get(team_type, {})
        team_box = data.get("teams", {}).get(team_type, {})
        probable_pitcher = team_info.get("probablePitcher")

        if probable_pitcher:
            pitcher_id = probable_pitcher.get("id")
            pitcher_player_id = f"ID{pitcher_id}"
            matched_pitcher = team_box.get("players", {}).get(pitcher_player_id)
            if matched_pitcher:
                pitching_stats = matched_pitcher.get("stats", {}).get("pitching", {})
                pitchers.append({
                    "name": probable_pitcher.get("fullName"),
                    "id": pitcher_id,
                    "team": team_type,
                    "stats": {
                        "era": pitching_stats.get("era"),
                        "whip": pitching_stats.get("whip"),
                        "strikeOutsPer9Inn": pitching_stats.get("strikeOutsPer9Inn"),
                        "baseOnBallsPer9Inn": pitching_stats.get("baseOnBallsPer9Inn"),
                        "firstInningEra": pitching_stats.get("firstInningEra")
                    }
                })
            else:
                logging.info(f"Probable pitcher with ID {pitcher_id} not found in boxscore for {team_type} team in game {game_id}, falling back.")

        if not any(p["team"] == team_type for p in pitchers):
            fallback_pitcher = next((player for player in team_box.get("players", {}).values()
                                     if player.get("position", {}).get("abbreviation") == "P"), None)
            if fallback_pitcher:
                person = fallback_pitcher.get("person", {})
                stats = fallback_pitcher.get("stats", {}).get("pitching", {})
                pitchers.append({
                    "name": person.get("fullName"),
                    "id": person.get("id"),
                    "team": team_type,
                    "stats": {
                        "era": stats.get("era"),
                        "whip": stats.get("whip"),
                        "strikeOutsPer9Inn": stats.get("strikeOutsPer9Inn"),
                        "baseOnBallsPer9Inn": stats.get("baseOnBallsPer9Inn"),
                        "firstInningEra": stats.get("firstInningEra")
                    }
                })
                logging.info(f"Used fallback pitcher for {team_type} team in game {game_id}")

        for player_id, player_data in team_box.get("players", {}).items():
            person = player_data.get("person", {})
            stats = player_data.get("stats", {})
            position = player_data.get("position", {}).get("abbreviation")
            full_name = person.get("fullName")
            if not full_name:
                continue
            if player_data.get("battingOrder") and str(player_data.get("battingOrder")).isdigit():
                batting_order = int(player_data.get("battingOrder"))
                if batting_order <= 300:
                    batting_stats = stats.get("batting", {})
                    batters.append({
                        "name": full_name,
                        "id": person.get("id"),
                        "team": team_type,
                        "order": batting_order,
                        "position": position,
                        "stats": {
                            "obp": batting_stats.get("obp"),
                            "homeRuns": batting_stats.get("homeRuns"),
                            "firstInningOBP": batting_stats.get("firstInningOBP")
                        }
                    })
    batters = sorted(batters, key=lambda x: x["order"])[:6]
    return pitchers, batters

if __name__ == "__main__":
    date_str = datetime.now().strftime("%Y-%m-%d")

    logging.info("Fetching MLB Schedule")
    games = fetch_mlb_schedule(date_str)
    logging.info(f"Fetched {len(games)} games.")

    all_pitchers = []
    all_batters = []

    logging.info("Fetching Details for Each Game")
    for game in games:
        game_id = game.get("gamePk")
        if not game_id:
            continue
        pitchers, batters = fetch_game_details(game)
        for pitcher in pitchers:
            pitcher["game_id"] = game_id
            all_pitchers.append(pitcher)
        for batter in batters:
            batter["game_id"] = game_id
            all_batters.append(batter)

    json_path = RAW_DATA_DIR / "mlb_daily_summary.json"
    with open(json_path, "w") as f:
        json.dump({
            "date": date_str,
            "games": games,
            "pitchers": all_pitchers,
            "batters": all_batters
        }, f, indent=2)
    logging.info(f"Saved combined summary to {json_path}")

    csv_path = RAW_DATA_DIR / "mlb_daily_summary.csv"
    with open(csv_path, "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Game ID", "Player Type", "Team", "Name", "Position", "ERA", "WHIP", "K/9", "BB/9", "1st Inning ERA", "OBP vs Hand", "HR%", "1st Inning OBP"])
        for p in all_pitchers:
            writer.writerow([
                p["game_id"], "Pitcher", p["team"], p["name"], "P",
                p["stats"].get("era"), p["stats"].get("whip"), p["stats"].get("strikeOutsPer9Inn"), p["stats"].get("baseOnBallsPer9Inn"), p["stats"].get("firstInningEra"), "", "", ""
            ])
        for b in all_batters:
            writer.writerow([
                b["game_id"], "Batter", b["team"], b["name"], b["position"],
                "", "", "", "", "",
                b["stats"].get("obp"), b["stats"].get("homeRuns"), b["stats"].get("firstInningOBP")
            ])
    logging.info(f"Saved CSV summary to {csv_path}")
