#!/usr/bin/env python3
from datetime import datetime as _dt
import sys
import logging
import json
import csv
from pathlib import Path
from datetime import datetime

import requests
import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Load configuration


def load_config():
    config_path = Path.cwd() / 'config.json'
    if not config_path.exists():
        logging.error(f"config.json not found at {config_path}")
        sys.exit(1)
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


config = load_config()

# your existing config load
CONFIG_PATH = Path(config["root_path"]) / "config.json"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

# new: load the RFI-features config
FEATURES_CONFIG_PATH = Path(config["mlb_rfi_model_features_config_path"])
with open(FEATURES_CONFIG_PATH, "r", encoding="utf-8") as f:
    features_cfg = json.load(f)

WEIGHTS = features_cfg["weights"]
BOUNDS = features_cfg["bounds"]

# Define paths
ROOT = Path(config['root_path']).resolve()
RAW_DATA_DIR = Path(config['mlb_test_output_path']).resolve()
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

date_suffix = _dt.now().strftime('%Y%m%d')
JSON_PATH = RAW_DATA_DIR / f"mlb_daily_summary_{date_suffix}.json"
HTML_PATH = RAW_DATA_DIR / f"mlb_mlh_rfi_websheet_{date_suffix}.html"
CSV_PATH = RAW_DATA_DIR / f"mlb_daily_summary_{date_suffix}.csv"

# Load season stats via pybaseball if available
df_pitch = pd.DataFrame()
df_bat = pd.DataFrame()
try:
    from pybaseball import batting_stats, pitching_stats
    SEASON = int(datetime.now().strftime('%Y'))
    logging.info(f"Loading season stats for {SEASON} via pybaseball")
    df_pitch = pitching_stats(SEASON)
    df_bat = batting_stats(SEASON)
except ImportError:
    logging.warning("pybaseball not available; season stats may be incomplete")
except Exception as e:
    logging.error(f"Error loading pybaseball stats: {e}")

# Helper to lookup stats


def minmax_scale(x, lo, hi):
    if x is None:
        return 0.5
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def pitcher_score(stats):
    b = BOUNDS
    f = {
        "era":    1 - minmax_scale(stats.get("era"),    *b["era"]),
        "whip":   1 - minmax_scale(stats.get("whip"),   *b["whip"]),
        "k_rate": minmax_scale(stats.get("strikeOutsPer9Inn")/9, *b["k_rate"]),
        "bb_rate": 1 - minmax_scale(stats.get("baseOnBallsPer9Inn")/9, *b["bb_rate"]),
        "f1_era": 1 - minmax_scale(stats.get("firstInningEra"), *b["f1_era"])
    }
    return sum(f.values()) / len(f)


def batter_score(feats):
    b = BOUNDS
    f = {
        "obp_vs":        feats["obp_vs"],
        "hr_rate":       minmax_scale(feats["hr_rate"], *b["hr_rate"]),
        "recent_f1_obp": feats["recent_f1_obp"]
    }
    return sum(f.values()) / len(f)


def compute_nrfi_score(pitch_stats, batt_feats, park, weather, team_pct, opp_pct):
    ps = pitcher_score(pitch_stats)
    bs = batter_score(batt_feats)
    pk = (park + weather) / 2
    tm = (team_pct + opp_pct) / 2

    w = WEIGHTS
    return (
        w["pitcher"] * ps +
        w["batter"] * bs +
        w["park"] * pk +
        w["team"] * tm
    )


def lookup_stats(pid, name, df, group):
    try:
        url = f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?stats=season&group={group}&season={SEASON}"
        r = requests.get(url)
        r.raise_for_status()
        splits = r.json().get('stats', [{}])[0].get('splits', [])
        if splits:
            return splits[0].get('stat', {})
    except Exception:
        pass
    try:
        url = f"https://statsapi.mlb.com/api/v1/people/{pid}?hydrate=stats(group={group},type=season,season={SEASON})"
        r = requests.get(url)
        r.raise_for_status()
        ppl = r.json().get('people', [{}])[0]
        splits = ppl.get('stats', [{}])[0].get('splits', [])
        if splits:
            return splits[0].get('stat', {})
    except Exception:
        pass
    if not df.empty:
        for col in ('mlbam_id', 'player_id'):
            if col in df.columns and pid in df[col].values:
                return df[df[col] == pid].iloc[0].dropna().to_dict()
    return {}

# Fetchers for batters


def get_boxscore_batters(game_id, side):
    try:
        data = requests.get(
            f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore").json()
        players = data['teams'][side]['players']
    except Exception:
        return []
    arr = []
    for p in players.values():
        ord = p.get('battingOrder')
        if ord and str(ord).isdigit():
            arr.append({
                'id': p['person']['id'],
                'name': p['person']['fullName'],
                'position': p.get('position', {}).get('abbreviation', ''),
                'order': int(ord)
            })
    return sorted(arr, key=lambda x: x['order'])[:3]


def get_live_batters(game_id, side):
    try:
        data = requests.get(
            f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live").json()
        teams = data['liveData']['boxscore']['teams'][side]
    except Exception:
        return []
    return [
        {
            'id': bid,
            'name': teams['players'][f'ID{bid}']['person']['fullName'],
            'position': teams['players'][f'ID{bid}'].get('position', {}).get('abbreviation', ''),
            'order': None
        }
        for bid in teams.get('batters', [])[:3]
    ]


def get_roster_batters(team_id):
    try:
        roster = requests.get(
            f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster").json().get('roster', [])
    except Exception:
        return []
    return [
        {
            'id': r['person']['id'],
            'name': r['person']['fullName'],
            'position': r.get('position', {}).get('abbreviation', ''),
            'order': None
        }
        for r in roster if r.get('position', {}).get('type') == 'Batter'
    ][:3]


def get_season_leaders():
    if df_bat.empty:
        return []
    col = next((c for c in df_bat.columns if 'OBP' in c.upper()
               or 'AVG' in c.upper()), None)
    if not col:
        return []
    top = df_bat.sort_values(col, ascending=False).head(3)
    return [
        {
            'id': int(r['mlbam_id']) if r.get('mlbam_id') else None,
            'name': r['Name'],
            'position': r['POS'],
            'order': None
        }
        for _, r in top.iterrows()
    ]


def get_schedule_preview_batters(game, side):
    return [
        {
            'id': p['person']['id'],
            'name': p['person']['fullName'],
            'position': p.get('position', {}).get('abbreviation', ''),
            'order': int(p.get('battingOrder', 0))
        }
        for p in game['teams'][side].get('previewPlayers', [])[:3]
    ]

# Generate HTML report


def generate_html(games):
    """
    Generate the HTML websheet: two rows per game, shared Game Time cell,
    CamelCase headers, center-aligned, with a borderless Vs column.
    """
    html = f"""<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='UTF-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1.0'/>
  <title>Moneyline Hacks - RFI Model</title>
  <link href='https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css' rel='stylesheet'>
  <style>
    body {{ background-color:#0f172a; color:#e2e8f0; font-family:'Segoe UI',sans-serif; }}
    .title-highlight {{ background:linear-gradient(to right,#34d399,#06b6d4);
                       -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
    table {{ border-collapse: collapse; width:100%; }}
    th, td {{ padding:0.5rem; text-align:center; }}
    th, td:not(.borderless) {{ border:1px solid #fff; }}
  </style>
</head>
<body class='p-6'>
  <div class=\"flex flex-col items-center justify-center gap-3 mb-6\">
    <img src=\"https://raw.githubusercontent.com/Fluidity1337/ai-ml-predictive-models/main/assets/img/mlh/mlh-logo-1.jpg\" alt=\"Moneyline Hacks Logo\" class=\"h-16\" />
    <h1 class=\"text-4xl font-extrabold title-highlight\">Moneyline Hacks</h1>
    <h2 class=\"text-xl text-gray-400\">Run First Inning (RFI) Model — {datetime.now().strftime('%B %d')}</h2>
    <img src=\"https://raw.githubusercontent.com/Fluidity1337/ai-ml-predictive-models/main/assets/img/mlb/mlb-logo-2.png\" alt=\"Baseball Icon\" class=\"h-10\" />
  </div>
  <div class='overflow-auto max-w-5xl mx-auto'>
    <table class='min-w-full text-gray-300 text-sm'>
      <thead class='bg-gray-900 text-gray-100 uppercase text-xs'>
        <tr>
          <th class='px-4 py-2'>Game Time</th>
          <th class='px-4 py-2'>Pitching Team</th>
          <th class='px-4 py-2'>Projected Starter</th>
          <th class='px-4 py-2 borderless'>Vs</th>
          <th class='px-4 py-2'>Team To NRFI</th>
          <th class='px-4 py-2'>Team Grade</th>
          <th class='px-4 py-2'>NRFI Grade</th>
          <th class='px-4 py-2'>Recommendation</th>
        </tr>
      </thead>
      <tbody>
"""
    for game in games:
        # format the game time
        iso = game.get('gameDate', '')
        if iso:
            try:
                dt = _dt.fromisoformat(iso.replace('Z', ''))
                time_str = dt.strftime('%I:%M %p ET').lstrip('0')
            except:
                time_str = '-'
        else:
            time_str = '-'

        away = game['teams']['away']
        home = game['teams']['home']

        # dummy placeholders
        tg_away = "0.0"
        tg_home = "0.0"
        nrfi_grade = "TBD"
        rec = "TBD"

        # Away row (lighter gray on left 5 cols, lighter gray on RHS spans)
        html += (
            "<tr>"
            f"<td class='px-4 py-2 bg-gray-700' rowspan='2'>{time_str}</td>"
            f"<td class='px-4 py-2 bg-gray-700'>{away['team']['name']}</td>"
            f"<td class='px-4 py-2 bg-gray-700'>{away.get('probablePitcher',{}).get('fullName','-')}</td>"
            f"<td class='px-4 py-2 bg-gray-700'>vs</td>"
            f"<td class='px-4 py-2 bg-gray-700'>{home['team']['name']}</td>"
            f"<td class='px-4 py-2 bg-gray-700'>{tg_away}</td>"
            f"<td class='px-4 py-2 bg-gray-700' rowspan='2'>{nrfi_grade}</td>"
            f"<td class='px-4 py-2 bg-gray-700' rowspan='2'>{rec}</td>"
            "</tr>\n"
        )

        # Home row (darker gray on left 5 cols, lighter gray on RHS already spanned)
        html += (
            "<tr>"
            f"<td class='px-4 py-2 bg-gray-800'>{home['team']['name']}</td>"
            f"<td class='px-4 py-2 bg-gray-800'>{home.get('probablePitcher',{}).get('fullName','-')}</td>"
            f"<td class='px-4 py-2 bg-gray-800'>vs</td>"
            f"<td class='px-4 py-2 bg-gray-800'>{away['team']['name']}</td>"
            f"<td class='px-4 py-2 bg-gray-800'>{tg_home}</td>"
            "</tr>\n"
        )

    html += (
        "      </tbody>\n"
        "    </table>\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )
    HTML_PATH.write_text(html)
    logging.info(f"Wrote HTML to {HTML_PATH}")


# Fetch game details with fallbacks


def fetch_game_details(game):
    # existing logic...
    pass


if __name__ == '__main__':
    # fetch schedule with previewPlayers hydrate
    sched = requests.get(
        f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
        "&hydrate=teams(team,previewPlayers),probablePitcher"
    ).json()
    games = sched.get('dates', [{}])[0].get('games', [])
    allp, allb = [], []
    for game in games:
        ps, bs = fetch_game_details(g)
        allp.extend(ps)
        allb.extend(bs)

'''
    # write outputs
    js = RAW_DATA_DIR / f"mlb_daily_stats_{date_str.replace('-','')}.json"
    with open(js, 'w') as f:
        json.dump(allp + allb, f, indent=2)
    logging.info(f"Saved JSON to {js}")

    csvf = RAW_DATA_DIR / f"mlb_daily_stats_{date_str.replace('-','')}.csv"
    keys = ['game_id', 'player_type', 'team',
            'id', 'name', 'position', 'order']
    stat_keys = sorted({k for p in (allp + allb) for k in p.get('stats', {})})
    with open(csvf, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(keys + stat_keys)
        for row in allp + allb:
            w.writerow([row.get(k) for k in keys] +
                       [row['stats'].get(k, '') for k in stat_keys])
    logging.info(f"Saved CSV to {csvf}")
'''
   # ─── Enrich each game with scores & grades ───────────────────────────────
   for game in games:
        # find this game’s pitchers & batters from the flattened lists
        for side in ("away", "home"):
            stats = next(
                (p["stats"] for p in allp
                 if p["game_id"] == game["gamePk"] and p["team"] == side),
                {}
            )
            p_score = pitcher_score(stats)

            lineup = [
                b["stats"] for b in allb
                if b["game_id"] == game["gamePk"] and b["team"] == side
            ]
            if lineup:
                obp_vs = sum(b.get("obp", 0) for b in lineup) / len(lineup)
                hr_rate = sum(b.get("homeRuns", 0)
                              for b in lineup) / len(lineup)
                recent_f1_obp = sum(b.get("firstInningOBP", 0)
                                    for b in lineup) / len(lineup)
                feats = {"obp_vs": obp_vs, "hr_rate": hr_rate,
                    "recent_f1_obp": recent_f1_obp}
            else:
                feats = {"obp_vs": 0, "hr_rate": 0, "recent_f1_obp": 0}
            b_score = batter_score(feats)

            # RFI grade = pitcher_weight * pitcher_score + batter_weight * batter_score
            rfi = WEIGHTS["pitcher"] * p_score + WEIGHTS["batter"] * b_score

            game[f"{side}_pitcher_score"] = p_score
            game[f"{side}_batter_score"] = b_score
            game[f"{side}_rfi_grade"] = rfi

        # game-level NRFI grade = away side’s RFI grade
        game["nrfi_grade"] = game["away_rfi_grade"]

    # ─── Write enriched JSON ────────────────────────────────────────────────
    enriched_json = RAW_DATA_DIR / \
        f"mlb_daily_summary_{date_str.replace('-', '')}.json"
    with open(enriched_json, "w", encoding="utf-8") as f:
        json.dump({"date": date_str, "games": games}, f, indent=2)
    logging.info(f"Saved enriched JSON to {enriched_json}")

    # ─── Write enriched CSV ─────────────────────────────────────────────────
    enriched_csv = RAW_DATA_DIR / \
        f"mlb_daily_summary_{date_str.replace('-', '')}.csv"
    headers = [
        "Date", "Game ID", "Game Time",
        "Away Team", "Away Pitcher", "Away Pitcher Score", "Away Batter Score", "Away RFI Grade",
        "Home Team", "Home Pitcher", "Home Pitcher Score", "Home Batter Score", "Home RFI Grade",
        "NRFI Grade"
    ]
    with open(enriched_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for game in games:
            # format time
            iso = game.get("gameDate", "")
            try:
                dt = _dt.fromisoformat(iso.replace("Z", ""))
                time_str = dt.strftime("%I:%M %p ET").lstrip("0")
            except:
                time_str = iso or "-"

            writer.writerow([
                date_str,
                game["gamePk"],
                time_str,
                game["teams"]["away"]["team"]["name"],
                game["teams"]["away"].get(
                    "probablePitcher", {}).get("fullName", "-"),
                game["away_pitcher_score"],
                game["away_batter_score"],
                game["away_rfi_grade"],
                game["teams"]["home"]["team"]["name"],
                game["teams"]["home"].get(
                    "probablePitcher", {}).get("fullName", "-"),
                game["home_pitcher_score"],
                game["home_batter_score"],
                game["home_rfi_grade"],
                game["nrfi_grade"],
            ])
    logging.info(f"Saved enriched CSV to {enriched_csv}")

    # ─── Finally, generate the websheet HTML ───────────────────────────────
    generate_html(games)

    # Example: load games from JSON and generate HTML
    """
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        games = data.get('games', [])
    except Exception as e:
        logging.error(f"Failed to load games JSON: {e}")
        sys.exit(1)
    """
   # generate_html(games)
