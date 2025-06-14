#!/usr/bin/env python3
import sys
from pathlib import Path
import logging
import json
import csv
from datetime import datetime

import requests
import pandas as pd
from pybaseball import batting_stats, pitching_stats, playerid_reverse_lookup

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ─── Paths & Config ────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))
CONFIG_PATH = ROOT / "config.json"
with open(CONFIG_PATH) as f:
    config = json.load(f)

RAW_DATA_DIR = Path(config.get("mlb_test_output_path", "./output")).resolve()
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

# ─── Season & Data Loading ─────────────────────────────────────────────────────
SEASON = datetime.now().year

logging.info(f"Loading {SEASON} pitching stats…")
DF_PITCH = pitching_stats(SEASON)
# Ensure MLBAM indexing for pitchers
pitch_id_cols = [c for c in DF_PITCH.columns if c.lower() in ('player_id','id','key_mlbam')]
if pitch_id_cols:
    DF_PITCH.set_index(pitch_id_cols[0], drop=False, inplace=True)
    logging.debug(f"Indexed DF_PITCH on MLBAM ID column: {pitch_id_cols[0]}")

logging.info(f"Loading {SEASON} batting stats…")
DF_BAT = batting_stats(SEASON)
# Identify FG ID column and index
fg_id_cols = [c for c in DF_BAT.columns if c.lower() == 'idfg']
if fg_id_cols:
    DF_BAT.set_index(fg_id_cols[0], drop=True, inplace=True)
    logging.debug(f"Indexed DF_BAT on Fangraphs ID column: {fg_id_cols[0]}")

# ─── Build MLBAM ↔ FG ID crosswalk ─────────────────────────────────────────────
logging.info("Building MLBAM→FG crosswalk…")
# Determine list of Fangraphs IDs to lookup
if fg_id_cols:
    fg_ids = DF_BAT.index.unique().tolist()
    ID_MAP = playerid_reverse_lookup(player_ids=fg_ids)
else:
    ID_MAP = playerid_reverse_lookup(player_ids=[])
# filter to MLBAM and Fangraphs keys
ID_MAP = ID_MAP[['key_mlbam','key_fangraphs']].dropna()
ID_MAP.rename(columns={'key_mlbam':'mlbam_id','key_fangraphs':'fg_id'}, inplace=True)
ID_MAP['mlbam_id'] = ID_MAP['mlbam_id'].astype(int)
ID_MAP['fg_id']    = ID_MAP['fg_id'].astype(int)
# merge into DF_BAT to allow lookup by MLBAM
if fg_id_cols:
    DF_BAT = (
        DF_BAT.reset_index()
        .merge(ID_MAP, left_on=fg_id_cols[0], right_on='fg_id', how='left')
        .set_index('mlbam_id', drop=False)
    )
    logging.debug("Re-indexed DF_BAT on MLBAM ID via crosswalk")

# ─── Helper: lookup stats by player_id or Name ───────────────────────────────────
def lookup_stats(player_id: int, player_name: str, df: pd.DataFrame) -> dict:
    pid = int(player_id)
    stats = {}
    # direct index lookup
    try:
        row = df.loc[pid]
        if isinstance(row, pd.Series):
            stats = row.dropna().to_dict()
        elif isinstance(row, pd.DataFrame) and not row.empty:
            stats = row.iloc[0].dropna().to_dict()
    except KeyError:
        logging.debug(f"Index lookup failed for ID {pid}")
    # fallback name match
    if not stats and 'Name' in df.columns:
        matches = df[df['Name'] == player_name]
        if not matches.empty:
            stats = matches.iloc[0].dropna().to_dict()
            logging.debug(f"Name fallback lookup succeeded for {player_name}")
    # still missing?
    if not stats:
        logging.warning(
            f"Stats missing for {player_name} (ID={pid}). Available columns: {list(df.columns)}"
        )
    return stats

# ─── Fetch schedule & boxscore ─────────────────────────────────────────────────
def fetch_mlb_schedule(date_str: str) -> list:
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&hydrate=probablePitcher"
    r = requests.get(url); r.raise_for_status()
    dates = r.json().get("dates", [])
    return dates[0].get("games", []) if dates else []


def fetch_game_details(game: dict) -> tuple[list, list]:
    game_id = game.get("gamePk")
    if not game_id:
        return [], []

    box = requests.get(f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore")
    box.raise_for_status()
    teams_box = box.json().get("teams", {})

    pitchers, batters = [], []
    for side in ("away", "home"):
        info = game["teams"][side]
        pb = teams_box.get(side, {})

        # probable pitcher
        prob = info.get("probablePitcher")
        if prob and (pid := prob.get("id")):
            name = prob.get("fullName")
            stats = lookup_stats(pid, name, DF_PITCH)
            pitchers.append({
                "game_id":    game_id,
                "player_type":"Pitcher",
                "team":       side,
                "id":         pid,
                "name":       name,
                "position":   "P",
                "stats":      stats
            })

        # first 3 batters
        count = 0
        for _, pd in pb.get("players", {}).items():
            order = pd.get("battingOrder")
            if not order or count >= 3:
                continue
            try:
                order = int(order)
            except ValueError:
                continue

            pid_b = pd.get("person", {}).get("id")
            name_b = pd.get("person", {}).get("fullName")
            if not pid_b or not name_b:
                continue

            stats_b = lookup_stats(pid_b, name_b, DF_BAT)
            batters.append({
                "game_id":    game_id,
                "player_type":"Batter",
                "team":       side,
                "id":         pid_b,
                "name":       name_b,
                "position":   pd.get("position", {}).get("abbreviation", ""),
                "order":      order,
                "stats":      stats_b
            })
            count += 1

    return pitchers, batters

# ─── Save JSON + CSV ────────────────────────────────────────────────────────────
def save_outputs(date_str: str, games: list, pitchers: list, batters: list):
    out = {"date": date_str, "games": games, "pitchers": pitchers, "batters": batters}
    p_json = RAW_DATA_DIR / "mlb_daily_summary.json"
    with open(p_json, "w") as f:
        json.dump(out, f, indent=2)
    logging.info(f"Wrote JSON → {p_json}")

    base_cols = ["game_id","player_type","team","id","name","position"]
    stat_keys = sorted({k for rec in pitchers + batters for k in rec.get("stats", {}).keys()})
    header = base_cols + stat_keys

    p_csv = RAW_DATA_DIR / "mlb_daily_summary.csv"
    with open(p_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for rec in pitchers + batters:
            row = [rec.get(c, "") for c in base_cols] + [rec.get("stats", {}).get(k, "") for k in stat_keys]
            writer.writerow(row)
    logging.info(f"Wrote CSV → {p_csv}")

# ─── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    today = datetime.now().strftime("%Y-%m-%d")
    logging.info("Fetching MLB schedule…")
    games = fetch_mlb_schedule(today)
    logging.info(f"  → {len(games)} games on {today}")

    all_pitchers, all_batters = [], []
    logging.info("Collecting details…")
    for g in games:
        p_list, b_list = fetch_game_details(g)
        all_pitchers.extend(p_list)
        all_batters.extend(b_list)

    save_outputs(today, games, all_pitchers, all_batters)
