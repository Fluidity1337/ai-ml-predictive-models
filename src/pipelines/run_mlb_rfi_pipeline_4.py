import sys
import logging
import json
import csv
from pathlib import Path
from datetime import datetime, date
import requests
import pandas as pd

# Constants & configuration
RAW_DATA_DIR = Path(__file__).parent.parent / 'data' / 'raw'
SEASON = None  # will be set at runtime based on input date

# Weights for combining pitcher and batter scores
WEIGHTS = {'pitcher': 0.6, 'batter': 0.4}

# Bounds for min-max scaling
BOUNDS = {
    'era':    (2.0, 6.0),
    'whip':   (0.8, 1.6),
    'k_rate': (0.0, 1.5),
    'bb_rate': (0.0, 1.0),
    'f1_era': (2.0, 8.0)
}

# Load pybaseball fallback data
try:
    df_pitch = pd.read_csv(RAW_DATA_DIR / 'mlb_pitch_data.csv')
    df_bat = pd.read_csv(RAW_DATA_DIR / 'mlb_bat_data.csv')
    HAS_PYBASEBALL = True
except FileNotFoundError:
    logging.warning(
        "pybaseball CSVs not found; season-leader fallback disabled.")
    df_pitch = pd.DataFrame()
    df_bat = pd.DataFrame()
    HAS_PYBASEBALL = False


def minmax_scale(x, low, high):
    'Scale x in [low, high] to [0,1], guard divide by zero'
    try:
        return max(0.0, min((x - low) / (high - low), 1.0))
    except Exception:
        return 0.5


def lookup_stats(pid: int, name: str, df: pd.DataFrame, group: str) -> dict:
    logging.debug(f"[LookupStats] {group.upper()} for {name} (ID={pid})…")
    # 1) Primary statsapi GET
    try:
        url = (f"https://statsapi.mlb.com/api/v1/people/{pid}/stats"
               f"?stats=season&group={group}&season={SEASON}")
        res = requests.get(url)
        res.raise_for_status()
        stats_list = res.json().get('stats', [])
        if stats_list and isinstance(stats_list, list):
            splits = stats_list[0].get('splits', [])
        else:
            splits = []
        if splits:
            stat = splits[0].get('stat', {})
            logging.debug(f"[LookupStats]  → got {len(stat)} fields")
            return stat
    except Exception:
        logging.debug(
            f"[LookupStats]  → Primary API failed for {name}", exc_info=True)
    # 2) Hydrated people endpoint
    try:
        url2 = (f"https://statsapi.mlb.com/api/v1/people/{pid}"
                f"?hydrate=stats(group={group},type=season,season={SEASON})")
        res2 = requests.get(url2)
        res2.raise_for_status()
        ppl = res2.json().get('people', [])
        if ppl and isinstance(ppl, list):
            splits2 = ppl[0].get('stats', [{}])[0].get('splits', [])
        else:
            splits2 = []
        if splits2:
            return splits2[0].get('stat', {})
    except Exception:
        pass
    # 3) pybaseball fallback
    if HAS_PYBASEBALL:
        for col in ('mlbam_id', 'player_id'):
            if col in df.columns and pid in df[col].values:
                return df[df[col] == pid].iloc[0].dropna().to_dict()
    return {}


def get_boxscore_batters(game_id: int, side: str) -> list:
    url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore?hydrate=all"
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        lineup = data.get('teams', {}).get(side, {}).get('batters', [])
        return [{'id': p['person']['id'], 'name': p['person']['fullName'],
                 'position': p.get('position', {}).get('abbreviation', ''),
                 'order': p.get('battingOrder', None)} for p in lineup]
    except Exception:
        return []


def get_live_batters(game_id: int, side: str) -> list:
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live?hydrate=all"
    try:
        res = requests.get(url)
        res.raise_for_status()
        live = res.json().get('liveData', {})
        b_ids = live.get('boxscore', {}).get(
            'teams', {}).get(side, {}).get('batters', [])[:3]
        players = live.get('boxscore', {}).get('teams', {}).get(
            side, {}).get('players', {}).values()
        return [{'id': bid,
                 'name': next(pl['person']['fullName'] for pl in players if pl['person']['id'] == bid),
                 'position': '', 'order': idx+1}
                for idx, bid in enumerate(b_ids)]
    except Exception:
        return []


def get_roster_batters(team_id: int) -> list:
    url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster"
    try:
        res = requests.get(url)
        res.raise_for_status()
        roster = res.json().get('roster', [])
        return [{'id': r['person']['id'], 'name': r['person']['fullName'],
                 'position': r.get('position', {}).get('abbreviation', ''),
                 'order': None}
                for r in roster if r.get('position', {}).get('abbreviation', '') != 'P'][:3]
    except Exception:
        return []


def get_schedule_preview_batters(game: dict, side: str) -> list:
    preview = game['teams'][side].get('previewPlayers', [])[:3]
    return [{'id': p['person']['id'], 'name': p['person']['fullName'],
             'position': p.get('position', {}).get('abbreviation', ''),
             'order': int(p.get('battingOrder', 0)) if p.get('battingOrder') else None}
            for p in preview]


def get_season_leaders() -> list:
    if HAS_PYBASEBALL:
        top = df_bat.sort_values('ops', ascending=False).head(3)
        return [{'id': int(r['player_id']), 'name': r['name_display_first_last'],
                 'position': '', 'order': None} for _, r in top.iterrows()]
    return []


def pitcher_score(stats: dict) -> float:
    b = BOUNDS
    def safe(k, d): v = stats.get(k); return float(v) if v is not None else d
    def mid(lo, hi): return (lo+hi)/2
    era = safe('era', mid(*b['era']))
    whip = safe('whip', mid(*b['whip']))
    so9 = safe('strikeoutsPer9Inn', 0)/9
    bb9 = safe('baseOnBallsPer9Inn', 0)/9
    f1 = safe('firstInningEra', mid(*b['f1_era']))
    sc = {'era': 1-minmax_scale(era, *b['era']), 'whip': 1-minmax_scale(whip, *b['whip']),
          'k_rate': minmax_scale(so9, *b['k_rate']), 'bb_rate': 1-minmax_scale(bb9, *b['bb_rate']),
          'f1_era': 1-minmax_scale(f1, *b['f1_era'])}
    return sum(sc.values())/len(sc)


def batter_score(feats: dict) -> float:
    return feats.get('obp_vs', 0)*0.5+feats.get('hr_rate', 0)*0.3+feats.get('recent_f1_obp', 0)*0.2


def fetch_schedule(date_str: str) -> list:
    url = (f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
           "&hydrate=teams(team,probablePitcher,previewPlayers)")
    res = requests.get(url)
    res.raise_for_status()
    d = res.json().get('dates', [])
    return d[0].get('games', []) if d else []


def fetch_game_details(game: dict) -> tuple[list, list]:
    gid = game.get('gamePk')
    stats_map = {'away': {}, 'home': {}}
    P, B = [], []
    for side in ('away', 'home'):
        info = game['teams'][side]
        tid = info['team']['id']
        prob = info.get('probablePitcher')
        if prob:
            ps = pitcher_score(lookup_stats(
                prob['id'], prob['fullName'], df_pitch, 'pitching'))
            P.append({'game_id': gid, 'player_type': 'pitcher', 'team': side, 'id': prob['id'],
                      'name': prob['fullName'], 'position': 'P', 'order': None, 'stats': {}, 'score': ps})
            stats_map[side]['pitcher'] = ps
        line = get_boxscore_batters(gid, side)
        if len(line) < 3:
            line = get_live_batters(gid, side)
        if len(line) < 3:
            line = get_roster_batters(tid)
        if len(line) < 3:
            line = get_schedule_preview_batters(game, side)
        if len(line) < 3:
            line = get_season_leaders()
        line = line[:3]
        feats = []
        for b in line:
            bs = batter_score(lookup_stats(
                b['id'], b['name'], df_bat, 'hitting'))
            B.append({'game_id': gid, 'player_type': 'batter', 'team': side, 'id': b['id'],
                      'name': b['name'], 'position': b['position'], 'order': b.get('order'),
                      'stats': {}, 'score': bs})
            feats.append(bs)
        stats_map[side]['batter'] = sum(feats)/len(feats) if feats else 0
    for side in ('away', 'home'):
        raw = WEIGHTS['pitcher']*stats_map[side]['pitcher'] + \
            WEIGHTS['batter']*stats_map[side]['batter']
        game[f'{side}_rfi_grade'] = round(raw*10, 1)
    game['nrfi_grade'] = round(
        (game['away_rfi_grade']+game['home_rfi_grade'])/2, 1)
    return P, B


if __name__ == '__main__':
    if len(sys.argv) > 1:
        dstr = sys.argv[1]
    else:
        dstr = date.today().isoformat()
    try:
        datetime.strptime(dstr, '%Y-%m-%d')
    except:
        logging.error('Date must be YYYY-MM-DD')
        sys.exit(1)
    SEASON = int(dstr[:4])
    games = fetch_schedule(dstr)
    AP, AB = [], []
    Gsum = []
    for g in games:
        ps, bs = fetch_game_details(g)
        for r in ps+bs:
            r.update({'away_rfi_grade': g['away_rfi_grade'],
                      'home_rfi_grade': g['home_rfi_grade'],
                      'nrfi_grade': g['nrfi_grade']})
        AP.extend(ps)
        AB.extend(bs)
        Gsum.append({'game_id': g['gamePk'], 'away_team': g['teams']['away']['team']['name'],
                     'home_team': g['teams']['home']['team']['name'],
                     'away_pitcher': g['teams']['away'].get('probablePitcher', {}).get('fullName', ''),
                     'home_pitcher': g['teams']['home'].get('probablePitcher', {}).get('fullName', ''),
                     'away_batters': [b['name'] for b in AB if b['game_id'] == g['gamePk'] and b['team'] == 'away'],
                     'home_batters': [b['name'] for b in AB if b['game_id'] == g['gamePk'] and b['team'] == 'home'],
                     'away_rfi_grade': g['away_rfi_grade'], 'home_rfi_grade': g['home_rfi_grade'],
                     'nrfi_grade': g['nrfi_grade']})
    # write combined CSV
    out_csv = RAW_DATA_DIR/f"mlb_combined_stats_{dstr.replace('-','')}.csv"
    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        h = ['game_id', 'player_type', 'team',
             'id', 'name', 'position', 'order']
        gk = ['away_rfi_grade', 'home_rfi_grade', 'nrfi_grade']
        w.writerow(h+gk+['score'])
        for r in AP+AB:
            w.writerow([r.get(c, '') for c in h]+[r.get(g, '')
                       for g in gk]+[r.get('score', '')])
    logging.info(f"Saved combined CSV to {out_csv}")
    # write JSON stats
    out_js = RAW_DATA_DIR / \
        f"mlb_daily_stats_summary_{dstr.replace('-','')}.json"
    with open(out_js, 'w', encoding='utf-8') as jf:
        json.dump(AP+AB, jf, indent=2)
    logging.info(f"Saved stats JSON to {out_js}")
    # write game summary CSV
    game_csv = RAW_DATA_DIR / \
        f"mlb_daily_game_summary_{dstr.replace('-','')}.csv"
    with open(game_csv, 'w', newline='', encoding='utf-8') as gf:
        w = csv.writer(gf)
        w.writerow(['game_id', 'away_team', 'home_team',
                    'away_pitcher', 'home_pitcher', 'away_batters', 'home_batters',
                    'away_rfi_grade', 'home_rfi_grade', 'nrfi_grade'])
        for r in Gsum:
            w.writerow([r['game_id'], r['away_team'], r['home_team'],
                        r['away_pitcher'], r['home_pitcher'], ';'.join(
                            r['away_batters']),
                        ';'.join(r['home_batters']), r['away_rfi_grade'], r['home_rfi_grade'], r['nrfi_grade']])
    logging.info(f"Saved game CSV to {game_csv}")
    # write game JSON
    game_js = RAW_DATA_DIR / \
        f"mlb_daily_game_summary_{dstr.replace('-','')}.json"
    with open(game_js, 'w', encoding='utf-8') as gj:
        json.dump(Gsum, gj, indent=2)
    logging.info(f"Saved game JSON to {game_js}")
