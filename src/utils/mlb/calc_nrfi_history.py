import requests
from datetime import datetime, timedelta


def fetch_game_ids(start_date, end_date):
    """Return a list of all game IDs between start_date and end_date (inclusive)."""
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1,
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate":   end_date.strftime("%Y-%m-%d"),
        "gameTypes": "R"    # Regular season only
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    game_ids = []
    for date_block in data["dates"]:
        for game in date_block["games"]:
            game_ids.append(game["gamePk"])
    return game_ids


def had_first_inning_run(game_id):
    """Return True if either team scored in the first inning of the given game."""
    url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/linescore"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    for inn in data.get("innings", []):
        if inn["num"] == 1:
            away = inn["away"].get("runs", 0)
            home = inn["home"].get("runs", 0)
            return (away + home) > 0
    # no inning 1 data → assume 0 runs
    return False


if __name__ == "__main__":
    # Define the 2025 regular‐season window
    season_start = datetime(2025, 4, 1)
    season_end = datetime(2025, 10, 1)

    print("Fetching game list…")
    all_game_ids = fetch_game_ids(season_start, season_end)
    total = len(all_game_ids)
    print(f"Total regular-season games found: {total}")

    print("Checking first-inning scores…")
    runs_1st = sum(had_first_inning_run(g) for g in all_game_ids)
    nrfi = total - runs_1st
    pct_nrfi = nrfi / total * 100

    print(
        f"Games with no run in inning 1: {nrfi}/{total} → {pct_nrfi:.2f}% NRFI")
