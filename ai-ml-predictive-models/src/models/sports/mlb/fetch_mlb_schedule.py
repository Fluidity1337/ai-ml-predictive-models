# fetch_schedule.py
import requests
from datetime import datetime
import sys

def fetch_mlb_schedule(date_str=None):
    if date_str:
        date = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        date = datetime.today()

    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date.strftime('%Y-%m-%d')}"
    response = requests.get(url)
    data = response.json()

    games = data.get("dates", [])
    if not games:
        print("No games scheduled.")
        return []

    schedule = []
    for game in games[0]["games"]:
        home = game["teams"]["home"]["team"]["name"]
        away = game["teams"]["away"]["team"]["name"]
        start_time = game["gameDate"]
        schedule.append({
            "home": home,
            "away": away,
            "start_time": start_time
        })
    return schedule

# Allow testing from command line
if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    schedule = fetch_mlb_schedule(date_arg)
    for game in schedule:
        print(f"{game['away']} @ {game['home']} — {game['start_time']}")
