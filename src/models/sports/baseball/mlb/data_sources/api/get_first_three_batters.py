import sys
import requests
import logging
from datetime import datetime

# Configure logging
datefmt = '%Y-%m-%d %H:%M:%S'
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt=datefmt)


def fetch_player_season_stats(player_id, season, group="hitting"):
    """Fetch season-long stats for a player."""
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=season&group={group}&season={season}"
    resp = requests.get(url)
    resp.raise_for_status()
    splits = resp.json().get("stats", [{}])[0].get("splits", [])
    return splits[0].get("stat", {}) if splits else {}


def get_first_three_projected_batters(game_id):
    """Fetch first three projected batters pre-game using the live feed's probablePlayers."""
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live"
    logging.debug("Fetching live feed for projected lineup: %s", url)
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()

    # Access projected lineup from gameData
    teams = data.get("gameData", {}).get("teams", {})
    season = datetime.now().year
    result = {}

    for side in ["away", "home"]:
        team_info = teams.get(side, {})
        # probablePlayers contains projected lineup
        projected = team_info.get("probablePlayers") or team_info.get("probableLineup") or []
        top3 = projected[:3]
        batters = []
        for entry in top3:
            person = entry.get("person", {})
            pid = person.get("id")
            name = person.get("fullName", "Unknown")
            position = entry.get("position", {}).get("abbreviation", "")
            order = entry.get("battingOrder") or entry.get("lineupSlot")
            stats = fetch_player_season_stats(pid, season, group="hitting")
            batters.append({
                "order": order,
                "id": pid,
                "name": name,
                "position": position,
                "avg": stats.get("avg"),
                "homeRuns": stats.get("homeRuns"),
                "ops": stats.get("ops")
            })
        result[side] = batters
    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python run_mlb_pipeline.py <game_id>")
       # sys.exit(1)
    #game_id = sys.argv[1]
    game_id = 777552
    try:
        batters = get_first_three_projected_batters(game_id)
    except Exception as e:
        logging.error("Failed to fetch projected batters for game %s: %s", game_id, e)
        sys.exit(1)
    for side in ["away", "home"]:
        print(f"{side.capitalize()} projected batters for game {game_id}:")
        if not batters.get(side):
            print("  No projected lineup available pre-game.")
        for b in batters.get(side, []):
            print(
                f"  {b['order']}. {b['name']} ({b['position']}) — "
                f"AVG: {b['avg']}, HR: {b['homeRuns']}, OPS: {b['ops']}"
            )
        print()
