#!/usr/bin/env python

import sys
import requests
import json
from datetime import datetime


def get_first_three_batters(game_id, date_str):
    """
    Tries, in order:
     1) preview-mode boxscore (?mode=preview)
     2) live boxscore
     3) schedule endpoint with previewPlayers hydrate
    Returns { "away": [(name,order)...], "home": [...] }.
    """
    base = f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"

    # 1 & 2) preview → live
    for suffix in ("?mode=preview", ""):
        resp = requests.get(base + suffix)
        if resp.status_code == 200:
            data = resp.json()
            break
    else:
        data = {}

    result = {"away": [], "home": []}
    for side in ("away", "home"):
        players = data.get("teams", {}).get(side, {}).get("players", {}) or {}
        lineup = [
            (p["person"]["fullName"], int(p["battingOrder"]))
            for p in players.values()
            if p.get("battingOrder") and str(p["battingOrder"]).isdigit()
        ]
        result[side] = sorted(lineup, key=lambda x: x[1])[:3]

    # 3) schedule previewPlayers fallback if either side is empty
    if not result["away"] or not result["home"]:
        sched = requests.get(
            "https://statsapi.mlb.com/api/v1/schedule"
            f"?sportId=1&date={date_str}"
            "&hydrate=teams(team,previewPlayers)"
        )
        sched.raise_for_status()
        games = sched.json().get("dates", [{}])[0].get("games", [])
        for g in games:
            if g["gamePk"] == int(game_id):
                for side in ("away", "home"):
                    if not result[side]:
                        pp = g["teams"][side].get("previewPlayers", [])
                        result[side] = [
                            (p["person"]["fullName"], int(
                                p.get("battingOrder", 0)))
                            for p in pp[:3]
                        ]
                break

    return result


if __name__ == "__main__":
    # defaults
    default_game_id = "660271"
    default_date = datetime.now().strftime("%Y-%m-%d")

    # allow overrides:
    #   python test_lineup_fallback.py [game_id] [YYYY-MM-DD]
    game_id = sys.argv[1] if len(sys.argv) > 1 else default_game_id
    date_str = sys.argv[2] if len(sys.argv) > 2 else default_date

    batters = get_first_three_batters(game_id, date_str)
    print(json.dumps({
        "game_id": game_id,
        "date": date_str,
        "batters": batters
    }, indent=2))
