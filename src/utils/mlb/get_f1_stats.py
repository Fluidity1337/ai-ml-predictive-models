#!/usr/bin/env python3
"""
Standalone script to compute a pitcher's first-inning ERA and WHIP over a 30-day window using MLB Statcast data via PyBaseball.
Also supports a "test" mode to compute for all today's probable starters.

Usage:
  python get_f1_stats.py <pitcher_id> [YYYY-MM-DD]
  python get_f1_stats.py test [YYYY-MM-DD]
"""
from fetch_schedule_bkp_20250702 import fetch_schedule
import pandas as pd
from pybaseball import statcast_pitcher
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add project src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


# Configure basic console logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-8s %(message)s")


def compute_first_inning_era(pitcher_id: int, start_dt: str, end_dt: str) -> str:
    """
    Fetches Statcast data for the given pitcher ID and computes their first-inning ERA.
    Returns a two-decimal ERA string or 'NA'.
    """
    try:
        df = statcast_pitcher(start_dt, end_dt, pitcher_id)
        if 'inning' not in df.columns:
            return 'NA'
        first = df[df['inning'] == 1]
        if first.empty:
            return 'NA'
        # Compute innings pitched
        if 'outs' in first.columns:
            ip = first['outs'].sum() / 3.0
        else:
            games_count = first['game_pk'].nunique(
            ) if 'game_pk' in first.columns else 0
            ip = float(games_count) if games_count > 0 else 1.0
        # Determine earned runs
        if 'earned_run' in first.columns:
            er = first['earned_run'].sum()
        elif 'events' in first.columns:
            er = (first['events'] == 'home_run').sum()
        else:
            return 'NA'
        era_val = (er / ip) * 9 if ip > 0 else None
        return f"{era_val:.2f}" if era_val is not None else 'NA'
    except Exception as e:
        logging.warning(
            f"Error computing first-inning ERA for {pitcher_id}: {e}")
        return 'NA'


def compute_first_inning_whip(pitcher_id: int, start_dt: str, end_dt: str) -> str:
    """
    Fetches Statcast data for the given pitcher ID and computes their first-inning WHIP.
    Returns a two-decimal WHIP string or 'NA'.
    """
    try:
        df = statcast_pitcher(start_dt, end_dt, pitcher_id)
        if 'inning' not in df.columns:
            return 'NA'
        first = df[df['inning'] == 1]
        if first.empty:
            return 'NA'
        # Compute innings pitched
        if 'outs' in first.columns:
            ip = first['outs'].sum() / 3.0
        else:
            games_count = first['game_pk'].nunique(
            ) if 'game_pk' in first.columns else 0
            ip = float(games_count) if games_count > 0 else 1.0
        # Count hits
        hit_events = {'single', 'double', 'triple', 'home_run'}
        hits = first['events'].apply(lambda e: 1 if e in hit_events else 0).sum(
        ) if 'events' in first.columns else 0
        # Count walks
        if 'bb' in first.columns:
            bb = first['bb'].sum()
        else:
            bb = first['events'].apply(lambda e: 1 if e in {
                                       'walk', 'intent_walk'} else 0).sum() if 'events' in first.columns else 0
        whip = (hits + bb) / ip if ip > 0 else None
        return f"{whip:.2f}" if whip is not None else 'NA'
    except Exception as e:
        logging.warning(
            f"Error computing first-inning WHIP for {pitcher_id}: {e}")
        return 'NA'


if __name__ == '__main__':
    # Test mode: compute for all probable starters today
    if len(sys.argv) < 2 or sys.argv[1].lower() == 'test':
        date_str = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].lower() != 'test' else (
            sys.argv[2] if len(
                sys.argv) > 2 else datetime.today().strftime('%Y-%m-%d')
        )
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        start_dt = (dt - timedelta(days=30)).strftime('%Y-%m-%d')
        games = fetch_schedule(date_str)
        recs = []
        for g in games:
            for side in ('away', 'home'):
                prob = g['teams'][side].get('probablePitcher')
                if prob:
                    pid, name = prob['id'], prob['fullName']
                    era = compute_first_inning_era(pid, start_dt, date_str)
                    whip = compute_first_inning_whip(pid, start_dt, date_str)
                    recs.append({
                        'pitcher_id': pid,
                        'name': name,
                        'side': side,
                        'f1_era': era,
                        'f1_whip': whip
                    })
        df = pd.DataFrame(recs)
        print(df.to_string(index=False))
        sys.exit(0)
    # Single mode: explicit pitcher ID
    try:
        pitcher_id = int(sys.argv[1])
    except ValueError:
        logging.error("Invalid pitcher_id %r", sys.argv[1])
        sys.exit(1)
    date_str = sys.argv[2] if len(
        sys.argv) > 2 else datetime.today().strftime('%Y-%m-%d')
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    start_dt = (dt - timedelta(days=30)).strftime('%Y-%m-%d')
    era = compute_first_inning_era(pitcher_id, start_dt, date_str)
    whip = compute_first_inning_whip(pitcher_id, start_dt, date_str)
    print(
        f"First-inning ERA for pitcher {pitcher_id} from {start_dt} to {date_str}: {era}, WHIP: {whip}")
