# run_mlb_pipeline.py
import sys
from pathlib import Path
import requests
from datetime import datetime
import json
import csv
import os

# Add the top-level src directory to sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))

RAW_DATA_DIR = Path(__file__).resolve().parent / ".." / ".." / ".." / ".." / ".." / ".." / "data" / "raw"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

def fetch_mlb_schedule(date_str):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch schedule for {date_str}")
    data = response.json()
    return data.get("dates", [])[0].get("games", [])

def fetch_probable_pitchers(date_str):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&hydrate=probablePitcher(stats(gameLog))"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch probable pitchers: {response.status_code}")

    data = response.json()
    games = data.get("dates", [])[0].get("games", [])
    pitchers = []

    for game in games:
        game_id = game.get("gamePk")
        for team_key in ["home", "away"]:
            team_info = game.get(team_key, {})
            team_name = team_info.get("team", {}).get("name")
            pitcher = team_info.get("probablePitcher")
            if pitcher:
                pitchers.append({
                    "gamePk": game_id,
                    "team": team_name,
                    "pitcher_id": pitcher.get("id"),
                    "pitcher_name": pitcher.get("fullName")
                })

    return pitchers

def fetch_starting_lineups(game_id):
    url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch lineup for game {game_id}")
        return None
    data = response.json()

    def get_first_3_batters(team_data):
        batting_order = []
        for player in team_data.get("players", {}).values():
            batting_order_index = player.get("battingOrder")
            if batting_order_index and batting_order_index.isdigit() and int(batting_order_index) <= 3:
                batting_order.append({
                    "name": player.get("person", {}).get("fullName"),
                    "position": player.get("position", {}).get("abbreviation"),
                    "stats": player.get("stats", {}).get("batting", {})
                })
        return batting_order

    home_batters = get_first_3_batters(data.get("teams", {}).get("home", {}))
    away_batters = get_first_3_batters(data.get("teams", {}).get("away", {}))

    return {
        "game_id": game_id,
        "home_batters": home_batters,
        "away_batters": away_batters
    }

if __name__ == "__main__":
    date_str = datetime.now().strftime("%Y-%m-%d")

    print("\n--- Fetching MLB Schedule ---")
    games = fetch_mlb_schedule(date_str)
    print(f"Fetched {len(games)} games.")

    print("\n--- Fetching Probable Pitchers ---")
    pitchers = fetch_probable_pitchers(date_str)
    print(f"Fetched probable pitchers for {len(pitchers)} teams.")

    print("\n--- Fetching First 3 Batters Per Team ---")
    lineups = []
    for game in games:
        game_id = game.get("gamePk")
        if game_id:
            lineup = fetch_starting_lineups(game_id)
            if lineup:
                lineups.append(lineup)

    # Save as JSON
    json_path = RAW_DATA_DIR / "mlb_daily_summary.json"
    with open(json_path, "w") as f:
        json.dump({"date": date_str, "games": games, "pitchers": pitchers, "lineups": lineups}, f, indent=2)
    print(f"\n✅ Saved combined summary to {json_path}")

    # Save as CSV (flattened)
    csv_path = RAW_DATA_DIR / "mlb_daily_summary.csv"
    with open(csv_path, "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Game ID", "Team Type", "Batter Name", "Position", "Stat - Hits", "Stat - AVG", "Stat - OBP"])

        for lineup in lineups:
            for team_type in ["home_batters", "away_batters"]:
                for batter in lineup.get(team_type, []):
                    writer.writerow([
                        lineup.get("game_id"),
                        "Home" if team_type == "home_batters" else "Away",
                        batter.get("name"),
                        batter.get("position"),
                        batter.get("stats", {}).get("hits"),
                        batter.get("stats", {}).get("avg"),
                        batter.get("stats", {}).get("obp")
                    ])
    print(f"✅ Saved CSV summary to {csv_path}")
