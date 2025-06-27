import sys
import requests
import logging
from datetime import datetime

# Configure basic logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


def fetch_player_stats(player_id, season):
    """Fetch season-long batting stats for a player."""
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=season&group=hitting&season={season}"
    resp = requests.get(url)
    resp.raise_for_status()
    splits = resp.json().get("stats", [{}])[0].get("splits", [])
    return splits[0].get("stat", {}) if splits else {}


def get_first_three_projected_batters(game_id, date_str=None):
    """
    Fetch the first three projected batters for both away and home teams pre-game,
    using the schedule endpoint with previewPlayers hydration.
    """
    # Determine date and season
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    season = int(date_str.split('-')[0])

    # Fetch schedule with previewPlayers and team codes
    url = (
        f"https://statsapi.mlb.com/api/v1/schedule?"
        f"sportId=1&date={date_str}&hydrate=teams(team,previewPlayers)"
    )
    logging.info(f"Fetching schedule: {url}")
    r = requests.get(url)
    r.raise_for_status()
    dates = r.json().get("dates", [])
    if not dates:
        raise RuntimeError(f"No games found for date {date_str}")
    games = dates[0].get("games", [])

    # Locate target game
    game = next((g for g in games if str(
        g.get("gamePk")) == str(game_id)), None)
    if not game:
        raise RuntimeError(f"Game {game_id} not found on {date_str}")

    result = {}
    teams = game.get("teams", {})
    for side in ["away", "home"]:
        team_info = teams.get(side, {})
        preview = team_info.get("previewPlayers", [])
        # Sort by battingOrder and take first three
        top3 = sorted((p for p in preview if p.get("battingOrder") is not None),
                      key=lambda p: p["battingOrder"])[:3]
        batters = []
        for entry in top3:
            pid = entry.get("person", {}).get("id")
            name = entry.get("person", {}).get("fullName")
            position = entry.get("position", {}).get("abbreviation")
            order = entry.get("battingOrder")
            stats = fetch_player_stats(pid, season) if pid else {}
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
    if len(sys.argv) < 2:
        # sys.exit(1)
        print("Usage: python run_mlb_pipeline.py <game_id> [YYYY-MM-DD]")
    # game_id = sys.argv[1]
    game_id = 777344
    date_str = sys.argv[2] if len(sys.argv) > 2 else "20250626"
    try:
        batters = get_first_three_projected_batters(game_id, date_str)
    except Exception as e:
        logging.error("Error: %s", e)
        sys.exit(1)

    for side in ["away", "home"]:
        print(
            f"{side.capitalize()} projected batters for game {game_id} on {date_str or 'today'}:")
        if not batters.get(side):
            print("  No projected lineup available pre-game.")
        for b in batters.get(side, []):
            print(
                f"  {b['order']}. {b['name']} ({b['position']}) — "
                f"AVG: {b['avg']}, HR: {b['homeRuns']}, OPS: {b['ops']}"
            )
        print()
