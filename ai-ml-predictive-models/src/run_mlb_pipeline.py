# run_mlb_pipeline.py
import sys
from pathlib import Path
import requests
from datetime import datetime
import json
import csv
import os

sys.path.append(str(Path(__file__).resolve().parents[2]))

RAW_DATA_DIR = Path(__file__).resolve().parents[6] / "data" / "raw"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

def fetch_mlb_schedule(date_str):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch schedule for {date_str}")
    data = response.json()
    return data.get("dates", [{}])[0].get("games", [])

def fetch_game_details(game_id):
    url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch boxscore for game {game_id}")
        return {}, {}
    data = response.json()

    pitchers = []
    batters = []

    for team_type in ["home", "away"]:
        team = data.get("teams", {}).get(team_type, {})
        for player_id, player_data in team.get("players", {}).items():
            person = player_data.get("person", {})
            stats = player_data.get("stats", {})
            position = player_data.get("position", {}).get("abbreviation")
            full_name = person.get("fullName")
            if not full_name:
                continue
            if position == "P":
                pitchers.append({
                    "name": full_name,
                    "id": person.get("id"),
                    "team": team_type,
                    "stats": stats.get("pitching", {})
                })
            elif player_data.get("battingOrder") and player_data.get("battingOrder").isdigit():
                batting_order = int(player_data.get("battingOrder"))
                if batting_order <= 300:
                    batters.append({
                        "name": full_name,
                        "id": person.get("id"),
                        "team": team_type,
                        "order": batting_order,
                        "position": position,
                        "stats": stats.get("batting", {})
                    })
    batters = sorted(batters, key=lambda x: x["order"])[:6]
    return pitchers, batters

if __name__ == "__main__":
    date_str = datetime.now().strftime("%Y-%m-%d")

    print("\n--- Fetching MLB Schedule ---")
    games = fetch_mlb_schedule(date_str)
    print(f"Fetched {len(games)} games.")

    all_pitchers = []
    all_batters = []

    print("\n--- Fetching Details for Each Game ---")
    for game in games:
        game_id = game.get("gamePk")
        if not game_id:
            continue
        pitchers, batters = fetch_game_details(game_id)
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
    print(f"\n✅ Saved combined summary to {json_path}")

    csv_path = RAW_DATA_DIR / "mlb_daily_summary.csv"
    with open(csv_path, "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Game ID", "Player Type", "Team", "Name", "Position", "Stat - Hits", "Stat - ERA", "Stat - AVG", "Stat - OBP"])
        for p in all_pitchers:
            writer.writerow([
                p["game_id"], "Pitcher", p["team"], p["name"], "P",
                "", p["stats"].get("era"), "", ""
            ])
        for b in all_batters:
            writer.writerow([
                b["game_id"], "Batter", b["team"], b["name"], b["position"],
                b["stats"].get("hits"), "", b["stats"].get("avg"), b["stats"].get("obp")
            ])
    print(f"✅ Saved CSV summary to {csv_path}")
