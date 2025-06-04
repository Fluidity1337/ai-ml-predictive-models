# fetch_stats.py
import requests
import pandas as pd
from datetime import date

def fetch_pitcher_stats(player_id: str, year: int = date.today().year, last_n_starts: int = 3):
    """
    Fetch last N starts for a given pitcher using the MLB Stats API (or a wrapper).
    Currently simulates data as placeholder.
    """
    # Placeholder endpoint -- replace with actual MLB Stats API usage or endpoint if available
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=gameLog&season={year}"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise ValueError(f"Failed to fetch stats for player {player_id}. Status: {response.status_code}")

    data = response.json()

    # --- Example: parse and simulate stats for now ---
    # Replace this with actual parsing logic for real endpoint structure
    games = []
    for game in data.get("stats", [])[0].get("splits", [])[:last_n_starts]:
        try:
            stat = game["stat"]
            games.append({
                "Date": game["date"],
                "IP": float(stat.get("inningsPitched", 0)),
                "H": int(stat.get("hits", 0)),
                "BB": int(stat.get("baseOnBalls", 0))
            })
        except Exception:
            continue

    df = pd.DataFrame(games)
    df["WHIP"] = round((df["H"] + df["BB"]) / df["IP"], 2)
    df["Cumulative WHIP (last 3)"] = round((df["H"].sum() + df["BB"].sum()) / df["IP"].sum(), 2)

    return df
