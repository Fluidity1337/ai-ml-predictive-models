#!/usr/bin/env python3
import sys
import logging
import json
import csv
from pathlib import Path
from datetime import datetime

import requests
import pandas as pd

# Try pybaseball for MLBAM IDs and season stats
try:
    from pybaseball import batting_stats, pitching_stats, playerid_reverse_lookup
    HAS_PYBASEBALL = True
except ImportError:
    HAS_PYBASEBALL = False
    logging.warning("pybaseball not available, season stats may be incomplete")

# Try MLB-StatsAPI for fallback stats
try:
    import statsapi
    HAS_STATAPI = True
except ImportError:
    HAS_STATAPI = False
    logging.warning("statsapi not available, fallback stats may be incomplete")

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
    handlers=[logging.StreamHandler(), logging.FileHandler(log_file, mode='a', encoding='utf-8')]
)
logging.info(f"Logging to console and file: {log_file}")

# Determine season and date to process
date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime('%Y-%m-%d')
SEASON = int(date_str.split('-')[0])

# Load season stats with MLBAM IDs if available
DF_PITCH = pd.DataFrame()
DF_BAT = pd.DataFrame()
if HAS_PYBASEBALL:
    # Pitching stats
    logging.info(f"Loading {SEASON} pitching stats via pybaseball…")
    try:
        DF_PITCH = pitching_stats(SEASON, mlbam=True)
    except TypeError:
        logging.warning("pitching_stats() does not accept mlbam; falling back to default call without mlbam.")
        DF_PITCH = pitching_stats(SEASON)
    # Index by any available ID column
    id_cols_p = [c for c in DF_PITCH.columns if c.lower() in ('player_id','mlbam_id','key_mlbam','playerid','id')]
    if id_cols_p:
        DF_PITCH.set_index(id_cols_p[0], drop=False, inplace=True)
        logging.debug(f"Indexed DF_PITCH on: {id_cols_p[0]}")
    else:
        logging.warning("No MLBAM ID column in pitching DataFrame; lookup by ID will fail.")

    # Batting stats
    logging.info(f"Loading {SEASON} batting stats via pybaseball…")
    try:
        DF_BAT = batting_stats(SEASON, mlbam=True)
    except TypeError:
        logging.warning("batting_stats() does not accept mlbam; falling back to default call without mlbam.")
        DF_BAT = batting_stats(SEASON)
    id_cols_b = [c for c in DF_BAT.columns if c.lower() in ('player_id','mlbam_id','key_mlbam','playerid','id')]
    if id_cols_b:
        DF_BAT.set_index(id_cols_b[0], drop=False, inplace=True)
        logging.debug(f"Indexed DF_BAT on: {id_cols_b[0]}")
    else:
        logging.warning("No MLBAM ID column in batting DataFrame; lookup by ID will fail.")

# Helper: lookup season stats with pybaseball or fallback to statsapi

def lookup_stats(pid: int, name: str, df: pd.DataFrame, group: str) -> dict:
    logging.debug(f"Looking up {group} stats for {name} (ID={pid})")
    # Try pybaseball lookup by ID
    if HAS_PYBASEBALL and not df.empty:
        try:
            row = df.loc[pid]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            stats = row.dropna().to_dict()
            if stats:
                logging.debug("pybaseball index lookup succeeded")
                return stats
        except Exception as e:
            logging.debug(f"pybaseball index lookup failed: {e}")
        # Fallback by name
        if 'Name' in df.columns:
            m = df[df['Name'] == name]
            if not m.empty:
                stats = m.iloc[0].dropna().to_dict()
                logging.debug("pybaseball name fallback succeeded")
                return stats
    # Fallback to statsapi
    if HAS_STATAPI:
        try:
            d = statsapi.get('stats', {'stats': 'season', 'group': group, 'season': SEASON, 'personIds': pid})
            splits = d.get('stats', [{}])[0].get('splits', [])
            stat = splits[0].get('stat', {}) if splits else {}
            if stat:
                logging.debug("statsapi fallback succeeded")
                return stat
        except Exception as e:
            logging.error(f"statsapi fallback error for {name} (ID={pid}): {e}")
    logging.error(f"No stats found for {name} (ID={pid})")
    return {}

# Fetch lineup from boxscore

def get_boxscore_batters(game_id: int, side: str) -> list:
    try:
        box = requests.get(f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore").json()['teams'][side]
    except Exception:
        return []
    players = box.get('players', {})
    batters = []
    for pl in players.values():
        ord = pl.get('battingOrder')
        if ord and str(ord).isdigit():
            batters.append({
                'id': pl['person']['id'],
                'name': pl['person']['fullName'],
                'position': pl.get('position', {}).get('abbreviation', ''),
                'order': int(ord)
            })
    return sorted(batters, key=lambda x: x['order'])[:3]

# Fetch lineup from live-feed

def get_live_batters(game_id: int, side: str) -> list:
    try:
        data = requests.get(f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live").json()
        teams_box = data['liveData']['boxscore']['teams'][side]
    except Exception:
        return []
    ids = teams_box.get('batters', [])[:3]
    players = teams_box.get('players', {})
    batt = []
    for bid in ids:
        key = f"ID{bid}"
        p = players.get(key, {})
        person = p.get('person', {})
        batt.append({
            'id': bid,
            'name': person.get('fullName', 'Unknown'),
            'position': p.get('position', {}).get('abbreviation', ''),
            'order': None
        })
    return batt

# Season leaders fallback if no lineup available

def get_season_leaders(info: dict) -> list:
    if DF_BAT.empty:
        return []
    df = DF_BAT.copy()
    # Attempt to scope by team
    if HAS_STATAPI:
        try:
            team_info = statsapi.get('team', {'teamId': info['team']['id']})
            team_abbr = team_info['teams'][0].get('abbreviation')
            if team_abbr and 'Team' in df.columns:
                df = df[df['Team'] == team_abbr]
        except Exception:
            pass
    # Choose best column available
    col = 'OBP' if 'OBP' in df.columns else ('AVG' if 'AVG' in df.columns else None)
    if not col:
        return []
    leaders = df.sort_values(by=col, ascending=False).head(3)
    result = []
    for _, r in leaders.iterrows():
        result.append({
            'id': r.get('player_id') or r.get('mlbam_id') or None,
            'name': r.get('Name'),
            'position': r.get('POS', ''),
            'order': None
        })
    return result

# Fetch game details

def fetch_game_details(game: dict) -> tuple[list, list]:
    gid = game.get('gamePk')
    pitchers, batters = [], []
    for side in ('away', 'home'):
        info = game['teams'][side]
        # Probable pitcher
        prob = info.get('probablePitcher')
        if prob and prob.get('id'):
            stats = lookup_stats(prob['id'], prob['fullName'], DF_PITCH, 'pitching')
            pitchers.append({
                'game_id': gid,
                'player_type': 'Pitcher',
                'team': side,
                'id': prob['id'],
                'name': prob['fullName'],
                'position': 'P',
                'stats': stats
            })
        else:
            logging.warning(f"No probable pitcher for {side} in game {gid}")
        # Batters: boxscore -> live -> season leaders
        lineup = get_boxscore_batters(gid, side)
        if not lineup:
            logging.info(f"No boxscore batters for {side} in game {gid}, trying live feed")
            lineup = get_live_batters(gid, side)
        if not lineup:
            logging.info(f"No live feed batters for {side} in game {gid}, using season leaders fallback")
            lineup = get_season_leaders(info)
        for b in lineup:
            stats = lookup_stats(b['id'], b['name'], DF_BAT, 'hitting')
            batters.append({
                'game_id': gid,
                'player_type': 'Batter',
                'team': side,
                'id': b['id'],
                'name': b['name'],
                'position': b.get('position', ''),
                'order': b.get('order'),
                'stats': stats
            })
    return pitchers, batters

# Main pipeline
if __name__ == '__main__':
    schedule = requests.get(
        f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&hydrate=probablePitcher"
    ).json()
    games = schedule.get('dates', [{}])[0].get('games', [])
    all_players = []
    for game in games:
        p_list, b_list = fetch_game_details(game)
        all_players.extend(p_list + b_list)
    # Save JSON
    js_file = RAW_DATA_DIR / f"mlb_daily_stats_{date_str.replace('-', '')}.json"
    with open(js_file, 'w') as f:
        json.dump(all_players, f, indent=2)
    logging.info(f"Saved JSON summary to {js_file}")
    # Save CSV
    csv_file = RAW_DATA_DIR / f"mlb_daily_stats_{date_str.replace('-', '')}.csv"
    base_keys = ['game_id', 'player_type', 'team', 'id', 'name', 'position', 'order']
    stat_keys = sorted({k for p in all_players for k in p['stats'].keys()})
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(base_keys + stat_keys)
        for r in all_players:
            row = [r.get(k) for k in base_keys] + [r['stats'].get(k, '') for k in stat_keys]
            writer.writerow(row)
    logging.info(f"Saved CSV summary to {csv_file}")
