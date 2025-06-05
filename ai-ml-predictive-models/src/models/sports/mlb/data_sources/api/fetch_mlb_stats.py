# Enhanced fetch_pitcher_stats to include more pitcher stats and derived metrics
import requests
import pandas as pd
from datetime import date

def fetch_pitcher_stats(player_id: str, year: int = date.today().year, last_n_starts: int = 3):
    """
    Fetch last N starts for a given pitcher using the MLB Stats API.
    Includes extended metrics like K, ER, R, HR, BF, Pitches, etc. and derived metrics.
    """
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=gameLog&season={year}"
    headers = {"User-Agent": "Mozilla/5.0"}

    print(f"Fetching stats for player_id={player_id} for year={year}...")
    response = requests.get(url, headers=headers)
    print(f"HTTP GET status: {response.status_code}")

    if response.status_code != 200:
        raise ValueError(f"Failed to fetch stats for player {player_id}. Status: {response.status_code}")

    data = response.json()
    print("Parsing response JSON...")

    games = []
    for game in data.get("stats", [])[0].get("splits", [])[:last_n_starts]:
        try:
            stat = game["stat"]
            ip = float(stat.get("inningsPitched", 0))
            h = int(stat.get("hits", 0))
            bb = int(stat.get("baseOnBalls", 0))
            k = int(stat.get("strikeOuts", 0))
            er = int(stat.get("earnedRuns", 0))
            r = int(stat.get("runs", 0))
            hr = int(stat.get("homeRuns", 0))
            bf = int(stat.get("battersFaced", 0))
            pitch_count = int(stat.get("pitchesThrown", 0))
            strikes = int(stat.get("strikesThrown", 0))
            go = int(stat.get("groundOuts", 0))
            fo = int(stat.get("airOuts", 0))

            whip = round((h + bb) / ip, 2) if ip > 0 else None
            k9 = round((k * 9) / ip, 2) if ip > 0 else None
            bb9 = round((bb * 9) / ip, 2) if ip > 0 else None
            hr9 = round((hr * 9) / ip, 2) if ip > 0 else None
            strike_pct = round((strikes / pitch_count) * 100, 1) if pitch_count > 0 else None
            gb_rate = round((go / (go + fo)) * 100, 1) if (go + fo) > 0 else None

            print(f"Game date={game['date']}, IP={ip}, H={h}, BB={bb}, K={k}, HR={hr}, WHIP={whip}, K/9={k9}, HR/9={hr9}")

            games.append({
                "Date": game["date"],
                "IP": ip,
                "H": h,
                "BB": bb,
                "K": k,
                "ER": er,
                "R": r,
                "HR": hr,
                "BF": bf,
                "Pitches": pitch_count,
                "Strikes": strikes,
                "GO": go,
                "FO": fo,
                "WHIP": whip,
                "K/9": k9,
                "BB/9": bb9,
                "HR/9": hr9,
                "Strike%": strike_pct,
                "GB%": gb_rate
            })
        except Exception as e:
            print(f"Error parsing game data: {e}")
            continue

    df = pd.DataFrame(games)
    print("Constructed DataFrame:")
    print(df)

    total_ip = df["IP"].sum()
    total_h = df["H"].sum()
    total_bb = df["BB"].sum()
    df["Cumulative WHIP (last 3)"] = round((total_h + total_bb) / total_ip, 2) if total_ip > 0 else None

    return df
