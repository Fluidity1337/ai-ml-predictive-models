import requests


def get_first_three_batters(game_id):
    """
    Returns a dict with two keys, 'home' and 'away', each mapping to a list
    of up to three (name, battingOrder) tuples for that side.
    Falls back to preview-mode boxscore if live isn’t available.
    """
    url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
    r = requests.get(url)
    if r.status_code != 200:
        # fallback to preview
        r = requests.get(url + "?mode=preview")
        r.raise_for_status()
    data = r.json()

    result = {}
    for side in ("home", "away"):
        players = data["teams"][side]["players"].values()
        # collect only those with a numeric battingOrder
        lineup = [
            (p["person"]["fullName"], int(p["battingOrder"]))
            for p in players
            if p.get("battingOrder") and str(p["battingOrder"]).isdigit()
        ]
        # sort and take first 3
        lineup_sorted = sorted(lineup, key=lambda x: x[1])[:3]
        result[side] = lineup_sorted

    return result


if __name__ == "__main__":
    import json
    # replace with any real game ID from schedule
    example_game_id = 777436
    batters = get_first_three_batters(example_game_id)
    print(json.dumps(batters, indent=2))
