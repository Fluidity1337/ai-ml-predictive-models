# run_mlb_rfi_pipeline_with_websheets_3.py

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

# Load config
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

FEATURES_CONFIG_PATH = Path(config["mlb_rfi_model_features_config_path"])
with open(FEATURES_CONFIG_PATH, "r", encoding="utf-8") as f:
    features_cfg = json.load(f)

ROOT = Path(config["root_path"]).resolve()
RAW_DATA_DIR = Path(config["mlb_test_output_path"]).resolve()
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

WEIGHTS = features_cfg["weights"]
BOUNDS = features_cfg["bounds"]

# Optionally load pybaseball data
try:
    from pybaseball import pitching_stats, batting_stats
    SEASON = int(datetime.now().year)
    df_pitch = pitching_stats(SEASON)
    df_bat = batting_stats(SEASON)
except Exception as e:
    logging.warning("Pybaseball not available or errored: %s", e)
    df_pitch = pd.DataFrame()
    df_bat = pd.DataFrame()


def minmax_scale(x, lo, hi):
    if x is None:
        return 0.5
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def pitcher_score(stats):
    b = BOUNDS

    # helper: coerce to float, or fall back to default
    def safe(key, default):
        try:
            v = stats.get(key, None)
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    # midpoint of a bound range
    def mid(low, high):
        return (low + high) / 2

    # debug log so you can inspect what came in
    print(f"[DEBUG pitcher_score] stats = {stats!r}")

    # pull every value through safe()
    era = safe("era",            mid(*b["era"]))
    whip = safe("whip",           mid(*b["whip"]))
    so9 = safe("strikeOutsPer9Inn", 0.0) / 9.0
    bb9 = safe("baseOnBallsPer9Inn", 0.0) / 9.0
    f1era = safe("firstInningEra", mid(*b["f1_era"]))

    # build your feature scores
    scores = {
        "era":     1.0 - minmax_scale(era,   *b["era"]),
        "whip":    1.0 - minmax_scale(whip,  *b["whip"]),
        "k_rate":  minmax_scale(so9,        *b["k_rate"]),
        "bb_rate": 1.0 - minmax_scale(bb9,   *b["bb_rate"]),
        "f1_era":  1.0 - minmax_scale(f1era, *b["f1_era"]),
    }

    # average them
    return sum(scores.values()) / len(scores)


def batter_score(feats):
    b = BOUNDS
    f = {
        "obp_vs":        feats["obp_vs"],
        "hr_rate":       minmax_scale(feats["hr_rate"], *b["hr_rate"]),
        "recent_f1_obp": feats["recent_f1_obp"]
    }
    return sum(f.values()) / len(f)


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


def fetch_schedule(date_str):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&hydrate=teams(team,previewPlayers),probablePitcher"
    return requests.get(url).json().get("dates", [{}])[0].get("games", [])


def lookup_stats(pid: int, name: str, df: pd.DataFrame, group: str) -> dict:
    logging.debug(f"[LookupStats] {group.upper()} for {name} (ID={pid})…")
    # 1) Primary statsapi GET
    try:
        url = f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?stats=season&group={group}&season={SEASON}"
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
    if HAS_PYBASEBALL and not df.empty:
        for col in ('mlbam_id', 'player_id'):
            if col in df.columns and pid in df[col].values:
                return df[df[col] == pid].iloc[0].dropna().to_dict()
    return {}


def fetch_game_details(game: dict) -> tuple[list, list]:
    game_id = game.get("gamePk")
    team_stats = {"away": {}, "home": {}}
    pitchers, batters = [], []

    for side in ("away", "home"):
        info = game["teams"][side]
        team_id = info["team"]["id"]

        # ——— Probable Pitcher ———
        prob = info.get("probablePitcher")
        if prob:
            stats = lookup_stats(
                prob["id"], prob["fullName"], df_pitch, "pitching")
            pitchers.append({
                "game_id":     game_id,
                "player_type": "pitcher",
                "team":        side,
                "id":          prob["id"],
                "name":        prob["fullName"],
                "position":    "P",
                "order":       None,
                "stats":       stats
            })
            team_stats[side]["pitcher"] = stats

        # ——— Batters fallback chain ———
        # 1) boxscore
        lineup = get_boxscore_batters(game_id, side)
        logging.debug(
            f"[{game_id}][{side}] Boxscore batters ({len(lineup)}): {[b['name'] for b in lineup]}")

        # 2) live feed
        if len(lineup) < 3:
            logging.debug(
                f"[{game_id}][{side}] Falling back to LIVE feed (had {len(lineup)})")
            lineup = get_live_batters(game_id, side)
            logging.debug(
                f"[{game_id}][{side}] Live batters ({len(lineup)}): {[b['name'] for b in lineup]}")

        # 3) team roster (exclude any position "P")
        if len(lineup) < 3:
            logging.debug(
                f"[{game_id}][{side}] Falling back to ROSTER (had {len(lineup)})")
            try:
                roster = requests.get(f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster") \
                                 .json().get('roster', [])
            except Exception:
                roster = []
            roster_lineup = [
                {
                    'id': r['person']['id'],
                    'name': r['person']['fullName'],
                    'position': r.get('position', {}).get('abbreviation', ''),
                    'order': None
                }
                for r in roster
                if r.get('position', {}).get('abbreviation', '') != 'P'
            ][:3]
            lineup = roster_lineup
            logging.debug(
                f"[{game_id}][{side}] Roster batters ({len(lineup)}): {[b['name'] for b in lineup]}")

        # 4) schedule previewPlayers
        if len(lineup) < 3:
            logging.debug(
                f"[{game_id}][{side}] Falling back to PREVIEW (had {len(lineup)})")
            lineup = get_schedule_preview_batters(game, side)
            logging.debug(
                f"[{game_id}][{side}] Preview batters ({len(lineup)}): {[b['name'] for b in lineup]}")

        # 5) season leaders (last resort)
        if len(lineup) < 3:
            logging.debug(
                f"[{game_id}][{side}] Falling back to SEASON LEADERS (had {len(lineup)})")
            lineup = get_season_leaders()
            logging.debug(
                f"[{game_id}][{side}] Season leader batters ({len(lineup)}): {[b['name'] for b in lineup]}")

        # ensure exactly three batters
        lineup = lineup[:3]

        # collect their stats
        team_feats = []
        for b in lineup:
            stats = lookup_stats(b["id"], b["name"], df_bat, "hitting")
            batters.append({
                "game_id":     game_id,
                "player_type": "batter",
                "team":        side,
                "id":          b["id"],
                "name":        b["name"],
                "position":    b["position"],
                "order":       b.get("order"),
                "stats":       stats
            })
            team_feats.append(stats)
        team_stats[side]["batters"] = team_feats

    # ——— Compute RFI grades ———
    for side in ("away", "home"):
        pscore = pitcher_score(team_stats[side].get("pitcher", {}))
        bat_feats = team_stats[side].get("batters", [])
        if bat_feats:
            obp_vs = sum(float(b.get("obp", 0))
                         for b in bat_feats) / len(bat_feats)
            hr_rate = sum(float(b.get("homeRuns", 0))
                          for b in bat_feats) / len(bat_feats)
            f1_obp = sum(float(b.get("firstInningOBP", 0))
                         for b in bat_feats) / len(bat_feats)
        else:
            obp_vs = hr_rate = f1_obp = 0.0

        bscore = batter_score({
            "obp_vs":        obp_vs,
            "hr_rate":       hr_rate,
            "recent_f1_obp": f1_obp
        })

        game[f"{side}_pitcher_score"] = pscore
        game[f"{side}_batter_score"] = bscore
        game[f"{side}_rfi_grade"] = WEIGHTS["pitcher"] * \
            pscore + WEIGHTS["batter"] * bscore

    game["nrfi_grade"] = game["away_rfi_grade"]
    return pitchers, batters


if __name__ == '__main__':
    # allow passing a date in YYYY-MM-DD as first arg, otherwise use today
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = datetime.now().strftime('%Y-%m-%d')

    # validate format (simple check)
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        logging.error("Date must be in YYYY-MM-DD format, got %r", date_str)
        sys.exit(1)

    games = fetch_schedule(date_str)

    all_pitchers, all_batters = [], []
    for g in games:
        ps, bs = fetch_game_details(g)
        # attach the game-level grades onto each record
        for p in ps:
            p.update({
                'pitcher_score': g[f"{p['team']}_pitcher_score"],
                'batter_score':  g[f"{p['team']}_batter_score"],
                'rfi_grade':     g[f"{p['team']}_rfi_grade"],
                'nrfi_grade':    g["nrfi_grade"]
            })
        for b in bs:
            b.update({
                'pitcher_score': g[f"{b['team']}_pitcher_score"],
                'batter_score':  g[f"{b['team']}_batter_score"],
                'rfi_grade':     g[f"{b['team']}_rfi_grade"],
                'nrfi_grade':    g["nrfi_grade"]
            })
        all_pitchers.extend(ps)
        all_batters.extend(bs)

    # build CSV filename with the provided date
    csv_path = RAW_DATA_DIR / \
        f"mlb_combined_stats_{date_str.replace('-', '')}.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        headers = ['game_id', 'player_type', 'team',
                   'id', 'name', 'position', 'order']
        grade_keys = ['pitcher_score',
                      'batter_score', 'rfi_grade', 'nrfi_grade']
        stat_keys = sorted({k for rec in all_pitchers +
                           all_batters for k in rec['stats'].keys()})
        writer.writerow(headers + grade_keys + stat_keys)
        for rec in all_pitchers + all_batters:
            row = [rec.get(c, '') for c in headers]
            row += [rec.get(gk, '') for gk in grade_keys]
            row += [rec['stats'].get(sk, '') for sk in stat_keys]
            writer.writerow(row)

    logging.info(f"Saved CSV to {csv_path}")

    # ——— JSON stats summary alongside CSV ———
    json_stats_path = RAW_DATA_DIR / \
        f"mlb_daily_stats_summary_{date_str.replace('-', '')}.json"
    with open(json_stats_path, 'w', encoding='utf-8') as jf:
        json.dump(all_pitchers + all_batters, jf, indent=2)
    logging.info(f"Saved JSON stats summary to {json_stats_path}")

    # ——— Build a per‐game summary ———
    game_summary = []
    for g in games:
        away_team = g["teams"]["away"]["team"]["name"]
        home_team = g["teams"]["home"]["team"]["name"]
        away_pitch = g["teams"]["away"].get(
            "probablePitcher", {}).get("fullName", "")
        home_pitch = g["teams"]["home"].get(
            "probablePitcher", {}).get("fullName", "")
        # first 3 batters we just collected:
        away_bats = [b['name'] for b in all_batters if b['game_id']
                     == g["gamePk"] and b['team'] == "away"]
        home_bats = [b['name'] for b in all_batters if b['game_id']
                     == g["gamePk"] and b['team'] == "home"]

        game_summary.append({
            "game_id":          g["gamePk"],
            "away_team":        away_team,
            "home_team":        home_team,
            "away_pitcher":     away_pitch,
            "home_pitcher":     home_pitch,
            "away_batters":     away_bats,
            "home_batters":     home_bats,
            "away_rfi_grade":   g["away_rfi_grade"],
            "home_rfi_grade":   g["home_rfi_grade"],
            "nrfi_grade":       g["nrfi_grade"],
        })

    # ——— CSV game summary ———
    game_csv = RAW_DATA_DIR / \
        f"mlb_daily_game_summary_{date_str.replace('-', '')}.csv"
    with open(game_csv, 'w', newline='', encoding='utf-8') as gf:
        writer = csv.writer(gf)
        writer.writerow([
            "game_id", "away_team", "home_team",
            "away_pitcher", "home_pitcher",
            "away_batters", "home_batters",
            "away_rfi_grade", "home_rfi_grade", "nrfi_grade"
        ])
        for r in game_summary:
            writer.writerow([
                r["game_id"], r["away_team"], r["home_team"],
                r["away_pitcher"], r["home_pitcher"],
                ";".join(r["away_batters"]), ";".join(r["home_batters"]),
                r["away_rfi_grade"], r["home_rfi_grade"], r["nrfi_grade"],
            ])
    logging.info(f"Saved CSV game summary to {game_csv}")

    # ——— JSON game summary ———
    game_json = RAW_DATA_DIR / \
        f"mlb_daily_game_summary_{date_str.replace('-', '')}.json"
    with open(game_json, 'w', encoding='utf-8') as gj:
        json.dump(game_summary, gj, indent=2)
    logging.info(f"Saved JSON game summary to {game_json}")
