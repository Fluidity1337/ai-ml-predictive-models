# fetch_mlb_probable_starting_pitchers.py
import requests
from datetime import datetime
from src.models.sports.baseball.schema.baseball_model_schema import GameInfo
from src.models.sports.baseball.mlb.data_sources.api.fetch_mlb_stats import fetch_mlb_pitcher_stats


def fetch_probable_pitchers(date_input: str = None) -> list[dict]:
    """
    Fetch probable starting pitchers for all games on the given date from the MLB API.
    Returns a list of dicts with pitcher stats for each team.
    """
    base_url = "https://statsapi.mlb.com/api/v1/schedule"

    if date_input is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    else:
        date_str = date_input

    params = {
        "sportId": 1,
        "date": date_str,
        "hydrate": "probablePitcher(stats(gameLog))"
    }

    print(f"Fetching probable pitchers for {date_str}...")
    response = requests.get(base_url, params=params)
    print(f"GET {response.url} => {response.status_code}")

    if response.status_code != 200:
        raise Exception(f"Failed to fetch schedule: {response.status_code}")

    data = response.json()
    games = data.get("dates", [])[0].get("games", [])

    pitcher_profiles: list[dict] = []

    for game in games:
        for team_type in ["home", "away"]:
            team = game.get(team_type, {})
            team_name = team.get("team", {}).get("name")
            pitcher = team.get("probablePitcher")

            if pitcher:
                pitcher_id = pitcher.get("id")
                pitcher_name = pitcher.get("fullName")

                print(f"Fetching stats for {pitcher_name} ({team_name})...")
                try:
                    stats_df = fetch_mlb_pitcher_stats(pitcher_id)
                    pitcher_profiles.append({
                        "date": date_str,
                        "team": team_name,
                        "pitcher": pitcher_name,
                        "pitcher_id": pitcher_id,
                        "stats": stats_df.to_dict(orient="records")
                    })
                except Exception as e:
                    print(f"Error fetching stats for {pitcher_name}: {e}")

    return pitcher_profiles


if __name__ == "__main__":
    import json
    results = fetch_probable_pitchers()
    with open("probable_pitchers.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Saved probable_pitchers.json")
