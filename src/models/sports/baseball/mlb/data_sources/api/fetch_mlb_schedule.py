# fetch_mlb_schedule.py
import requests
import pandas as pd
from datetime import datetime


def fetch_mlb_schedule(date_input=None):
    """
    Fetches the MLB game schedule for the given date.
    If no date is provided, today's date is used.
    """
    if date_input is None:
        date_input = datetime.today().date()

    if isinstance(date_input, datetime):
        date_str = date_input.strftime("%Y-%m-%d")
    elif isinstance(date_input, str):
        date_str = date_input
    elif hasattr(date_input, 'strftime'):
        date_str = date_input.strftime("%Y-%m-%d")
    else:
        raise ValueError("date_input must be a string or datetime/date object")

    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
    response = requests.get(url)
    data = response.json()

    games = []
    for date in data.get("dates", []):
        for game in date.get("games", []):
            games.append({
                "gamePk": game.get("gamePk"),
                "gameDate": game.get("gameDate"),
                "awayTeam": game.get("teams", {}).get("away", {}).get("team", {}).get("name"),
                "homeTeam": game.get("teams", {}).get("home", {}).get("team", {}).get("name")
            })

    df = pd.DataFrame(games)
    return df


if __name__ == "__main__":
    df_today = fetch_mlb_schedule("2025-06-26")
    # df_today = fetch_mlb_schedule()
    print(df_today)
