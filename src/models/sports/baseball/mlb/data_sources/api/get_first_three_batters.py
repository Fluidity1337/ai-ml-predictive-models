import sys
import requests
from datetime import datetime
import json
import csv
import logging

# Helper to fetch player stats
def fetch_player_season_stats(player_id, season, group="hitting"):
    pid = str(player_id)
    url = f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?stats=season&group={group}&season={season}"
    resp = requests.get(url)
    if resp.status_code != 200:
        logging.warning("Stat fetch failed for %s %s: %s", group, pid, resp.status_code)
        return {}
    stats = resp.json().get("stats", [{}])[0].get("splits", [])
    return stats[0].get("stat", {}) if stats else {}

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Main utility to get first 3 batters
def get_first_three_batters(game_id, date_str=None):
    """Fetch first three batters for both teams using schedule hydration of lineup."""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    url = (
        f"https://statsapi.mlb.com/api/v1/schedule?"
        f"sportId=1&date={date_str}&hydrate=teams(lineup)"
    )
    logging.debug("Schedule URL: %s", url)
    resp = requests.get(url)
    resp.raise_for_status()
    games = resp.json().get("dates", [{}])[0].get("games", [])

    # Find the game
    game = next((g for g in games if str(g.get("gamePk")) == str(game_id)), None)
    if not game:
        raise ValueError(f"Game {game_id} not found on {date_str}")

    season = datetime.now().year
    result = {}
    for side in ["away", "home"]:
        lineup = game.get("teams", {}).get(side, {}).get("lineup", [])[:3]
        batters = []
        for entry in lineup:
            person = entry.get("person", {})
            pid = person.get("id")
            stats = fetch_player_season_stats(pid, season, group="hitting")
            batters.append({
                "id": pid,
                "name": person.get("fullName"),
                "position": entry.get("position", {}).get("abbreviation"),
                "order": entry.get("lineupSlot"),
                "stats": stats
            })
        result[side] = batters
    return result

if __name__ == "__main__":
    game_id = 777556
    try:

        batters = get_first_three_batters(game_id=777556)  # Replace with your game ID
    except requests.HTTPError as e:
        print(f"Error fetching live feed for game {game_id}: {e}")
        sys.exit(1)

    for side in ["away", "home"]:
        print(f"{side.capitalize()} batters for game {game_id}:")
        if not batters.get(side):
            print("  No batters available (lineup not posted yet)")
        for b in batters.get(side, []):
            print(f"  {b['id']}: {b['name']} ({b['position']})")
        print()
