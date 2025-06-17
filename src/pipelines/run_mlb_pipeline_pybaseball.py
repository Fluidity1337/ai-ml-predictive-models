#!/usr/bin/env python3
import sys
import logging
import json
import csv
from pathlib import Path
from datetime import datetime

import requests
import pandas as pd

# Try pybaseball for season stats
try:
    from pybaseball import batting_stats, pitching_stats
    HAS_PYBASEBALL = True
except ImportError:
    HAS_PYBASEBALL = False
    logging.warning("pybaseball not available, season stats may be incomplete")

# Paths & Config
ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config.json"
with open(CONFIG_PATH) as f:
    config = json.load(f)

RAW_DATA_DIR = Path(config.get("mlb_test_output_path", "./output")).resolve()
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Logging setup
date_now = datetime.now().strftime('%Y-%m-%d')
log_file = RAW_DATA_DIR / f"mlb_pipeline_{date_now}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(), logging.FileHandler(
        log_file, mode='a', encoding='utf-8')]
)
logging.info(f"Logging to console and file: {log_file}")

# Determine date to process
date_str = sys.argv[1] if len(
    sys.argv) > 1 else datetime.now().strftime('%Y-%m-%d')
SEASON = int(date_str.split('-')[0])

# Load season stats


def load_stats():
    df_pitch = pd.DataFrame()
    df_bat = pd.DataFrame()
    if HAS_PYBASEBALL:
        try:
            logging.info(f"Loading {SEASON} pitching stats via pybaseball…")
            df_pitch = pitching_stats(SEASON)
        except Exception as e:
            logging.error(f"pybaseball pitching_stats error: {e}")
        try:
            logging.info(f"Loading {SEASON} batting stats via pybaseball…")
            df_bat = batting_stats(SEASON)
        except Exception as e:
            logging.error(f"pybaseball batting_stats error: {e}")
    return df_pitch, df_bat


DF_PITCH, DF_BAT = load_stats()

# Lookup stats helper


def lookup_stats(pid: int, name: str, df: pd.DataFrame, group: str) -> dict:
    logging.debug(f"Looking up {group} stats for {name} (ID={pid})")
    # 1) Primary statsapi GET
    try:
        url = f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?stats=season&group={group}&season={SEASON}"
        res = requests.get(url)
        res.raise_for_status()
        splits = res.json().get('stats', [{}])[0].get('splits', [])
        if splits:
            return splits[0].get('stat', {})
    except Exception:
        pass
    # 2) Hydrate people endpoint
    try:
        url2 = (f"https://statsapi.mlb.com/api/v1/people/{pid}"
                f"?hydrate=stats(group={group},type=season,season={SEASON})")
        res2 = requests.get(url2)
        res2.raise_for_status()
        ppl = res2.json().get('people', [{}])[0]
        splits2 = ppl.get('stats', [{}])[0].get('splits', [])
        if splits2:
            return splits2[0].get('stat', {})
    except Exception:
        pass
    # 3) pybaseball fallback
    if HAS_PYBASEBALL and not df.empty:
        for col in ('mlbam_id', 'player_id'):
            if col in df.columns and pid in df[col].values:
                return df[df[col] == pid].iloc[0].dropna().to_dict()
    return {}

# Batter fetchers


def get_boxscore_batters(game_id: int, side: str) -> list:
    try:
        teams = requests.get(
            f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
        ).json()['teams'][side]
    except Exception:
        return []
    bat = []
    for pl in teams.get('players', {}).values():
        ord = pl.get('battingOrder')
        if ord and str(ord).isdigit():
            bat.append({
                'id': pl['person']['id'],
                'name': pl['person']['fullName'],
                'position': pl.get('position', {}).get('abbreviation', ''),
                'order': int(ord)
            })
    return sorted(bat, key=lambda x: x['order'])[:3]


def get_live_batters(game_id: int, side: str) -> list:
    try:
        data = requests.get(
            f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live"
        ).json()
        teams = data['liveData']['boxscore']['teams'][side]
    except Exception:
        return []
    bat = []
    for bid in teams.get('batters', [])[:3]:
        p = teams['players'].get(f"ID{bid}", {})
        pers = p.get('person', {})
        bat.append({
            'id': bid,
            'name': pers.get('fullName', 'Unknown'),
            'position': p.get('position', {}).get('abbreviation', ''),
            'order': None
        })
    return bat


def get_roster_batters(team_id: int) -> list:
    try:
        roster = requests.get(
            f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster"
        ).json().get('roster', [])
    except Exception:
        return []
    bat = [
        {
            'id': r['person']['id'],
            'name': r['person']['fullName'],
            'position': r.get('position', {}).get('abbreviation', ''),
            'order': None
        }
        for r in roster if r.get('position', {}).get('type') == 'Batter'
    ]
    return bat[:3]


def get_season_leaders() -> list:
    if DF_BAT.empty:
        return []
    df = DF_BAT.copy()
    col = next((c for c in df.columns if 'OBP' in c.upper()
               or 'AVG' in c.upper()), None)
    if not col:
        return []
    top = df.sort_values(col, ascending=False).head(3)
    return [{
        'id': int(r.get('mlbam_id', 0)) if r.get('mlbam_id') else None,
        'name': r.get('Name', ''),
        'position': r.get('POS', ''),
        'order': None
    } for _, r in top.iterrows()]

# Fallback from schedule previewPlayers


def get_schedule_preview_batters(game: dict, side: str) -> list:
    pp = game['teams'][side].get('previewPlayers', [])
    bat = []
    for p in pp[:3]:
        bat.append({
            'id': p['person']['id'],
            'name': p['person']['fullName'],
            'position': p.get('position', {}).get('abbreviation', ''),
            'order': int(p.get('battingOrder', 0))
        })
    return bat

# Main game detail fetch


def fetch_game_details(game: dict) -> tuple[list, list]:
    gid = game.get('gamePk')
    pitchers, batters = [], []
    for side in ('away', 'home'):
        info = game['teams'][side]
        team_id = info['team']['id']
        # Pitcher
        prob = info.get('probablePitcher')
        if prob:
            stats = lookup_stats(
                prob['id'], prob['fullName'], DF_PITCH, 'pitching')
            pitchers.append({
                'game_id': gid,
                'player_type': 'Pitcher',
                'team': side,
                'id': prob['id'],
                'name': prob['fullName'],
                'position': 'P',
                'stats': stats
            })
        # Batters: sequence of fallbacks
        lineup = get_boxscore_batters(gid, side)
        if len(lineup) < 3:
            lineup = get_live_batters(gid, side)
        if len(lineup) < 3:
            lineup = get_roster_batters(team_id)
        if len(lineup) < 3:
            lineup = get_season_leaders()
        if len(lineup) < 3:
            lineup = get_schedule_preview_batters(game, side)
            logging.info(
                f"Using schedule previewPlayers for {side} in game {gid}")
        for b in lineup:
            stats = lookup_stats(b['id'], b.get(
                'name', ''), DF_BAT, 'hitting') if b.get('id') else {}
            batters.append({
                'game_id': gid,
                'player_type': 'Batter',
                'team': side,
                'id': b['id'],
                'name': b['name'],
                'position': b['position'],
                'order': b.get('order'),
                'stats': stats
            })
    return pitchers, batters


# Main
if __name__ == '__main__':
    # fetch schedule with previewPlayers hydrate
    sched = requests.get(
        f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
        "&hydrate=teams(team,previewPlayers),probablePitcher"
    ).json()
    games = sched.get('dates', [{}])[0].get('games', [])
    allp, allb = [], []
    for g in games:
        ps, bs = fetch_game_details(g)
        allp.extend(ps)
        allb.extend(bs)

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
