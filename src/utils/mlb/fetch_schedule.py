import requests


def fetch_schedule(date_str: str) -> list:
    """
    Fetches the MLB schedule for a given date from the MLB Stats API.

    Args:
        date_str (str): Date in 'YYYY-MM-DD' format.

    Returns:
        list: A list of game dicts for the given date.
    """
    url = (
        f"https://statsapi.mlb.com/api/v1/schedule?"
        f"sportId=1&date={date_str}&"
        f"hydrate=teams(team,previewPlayers),probablePitcher"
    )
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    # Navigate to games list safely
    dates = data.get("dates", [])
    if not dates:
        return []
    games = dates[0].get("games", [])
    return games
