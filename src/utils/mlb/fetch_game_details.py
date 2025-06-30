#!/usr/bin/env python3
import logging
import logging.config
import os
import sys
import json
import pandas as pd
from pathlib import Path
from datetime import date
from utils.config_loader import load_config
from utils.helpers import FeatureConfigLoader
from utils.mlb.fetch_advanced_stats_for_pitcher import PitcherAdvancedStats


def fetch_game_details(game, df_pitch=None, features_cfg=None, season=None):
    """
    Fetch game details and attach advanced stats (last 5 games' xFIP and Barrel) for probables.
    Returns list of dicts with keys: game_id, side, id, name, team, calculated_stats
    """
    game_id = game.get("gamePk")
    logging.debug(f"[Game {game_id}] Processing game details")

    probables = {
        "away": game.get("teams", {}).get("away", {}).get("probablePitcher"),
        "home": game.get("teams", {}).get("home", {}).get("probablePitcher")
    }
    logging.debug(f"[{game_id}] Probables parsed: {probables}")

    pitchers = []
    for side in ("away", "home"):
        prob = probables.get(side)
        logging.debug(f"[{game_id}] Side: {side}, Probable: {prob}")
        if not prob:
            continue

        pid = prob['id']
        # Analyze per-game stats
        # Analyze per-game stats for last 30 days
        pas = PitcherAdvancedStats(pid)
        pas.analyze()

        # Keep only regular-season games (from April 1 of the season year)
        from datetime import date
        season_year = pas.start.year if pas.start else date.today().year
        reg_start = date(season_year, 4, 1)
        pas.records = [r for r in pas.records if r[1] >= reg_start]

        # If still no games, fall back to season-to-date
        if not pas.records:
            logging.info(
                f"[{game_id}] No recent RS games for {prob['fullName']}, fetching season-to-date")
            from datetime import timedelta
            season_start = date(season_year, 1, 1)
            end_date = date.today() - timedelta(days=1)
            pas = PitcherAdvancedStats(pid, start=season_start, end=end_date)
            pas.analyze()
            pas.records = [r for r in pas.records if r[1] >= reg_start]

        # Take last 5 regular-season appearances
        last5 = pas.records[-5:]
        # Flag as insufficient only if no outings
        insufficient_data = len(last5) == 0
        # Build a map of those games' advanced stats, converting NaN to 'NA'
        last5_map = {
            gp: {
                'date': gd.isoformat(),
                'xFIP': xfip if pd.notna(xfip) else None,
                'xFIP_score': xfsc if pd.notna(xfsc) else None,
                'Barrel%': bp if pd.notna(bp) else None,
                'Barrel%_score': bpsc if pd.notna(bpsc) else None
            }
            for gp, gd, xfip, xfsc, bp, bpsc in last5
        }

        last5 = pas.records[-5:]
        # Flag as insufficient only if no outings
        insufficient_data = len(last5) == 0
        # Build a map of those games' advanced stats
        last5_map = {
            gp: {
                'date': gd.isoformat(),
                'xFIP': xfip,
                'xFIP_score': xfsc,
                'Barrel%': bp,
                'Barrel%_score': bpsc
            }
            for gp, gd, xfip, xfsc, bp, bpsc in last5
        }
        # Compute averages over last5
        xfips = [r[2] for r in last5 if pd.notna(r[2])]
        xfip_scores = [r[3] for r in last5 if pd.notna(r[3])]
        barrel_pcts = [r[4] for r in last5 if pd.notna(r[4])]
        barrel_scores = [r[5] for r in last5 if pd.notna(r[5])]
        avg_xfip = sum(xfips)/len(xfips) if xfips else float('nan')
        avg_xfip_score = sum(xfip_scores) / \
            len(xfip_scores) if xfip_scores else float('nan')
        avg_barrel_pct = sum(barrel_pcts) / \
            len(barrel_pcts) if barrel_pcts else float('nan')
        avg_barrel_score = sum(
            barrel_scores)/len(barrel_scores) if barrel_scores else float('nan')

        # Extract stats for this specific game
        this_game_stats = last5_map.get(game_id, {})
        # If no recent appearances, fall back to seasonal stats
        if not last5_map and df_pitch is not None:
            # Seasonal DataFrame is expected to have 'IDfg', 'xFIP', and 'Barrel%' columns
            seasonal = df_pitch.loc[df_pitch['IDfg'] == pid]
            if not seasonal.empty:
                row_season = seasonal.iloc[0]
                season_xfip = row_season.get('xFIP', float('nan'))
                season_barrel = row_season.get('Barrel%', float('nan'))
                # Compute season scores via RatingCalculator
                rc = RatingCalculator(features_cfg)
                season_xfip_score = rc.minmax_scale(
                    season_xfip, 'xFIP', reverse=True)
                season_barrel_score = rc.minmax_scale(
                    season_barrel, 'BarrelPct', reverse=True)
                # Override data maps
                last5_map = {
                    'season': {
                        'date': None,
                        'xFIP': season_xfip,
                        'xFIP_score': season_xfip_score,
                        'Barrel%': season_barrel,
                        'Barrel%_score': season_barrel_score
                    }
                }
                # Averages equal seasonal for this fallback
                avg_xfip = season_xfip
                avg_xfip_score = season_xfip_score
                avg_barrel_pct = season_barrel
                avg_barrel_score = season_barrel_score
                this_game_stats = {
                    'xFIP': season_xfip,
                    'xFIP_score': season_xfip_score,
                    'Barrel%': season_barrel,
                    'Barrel%_score': season_barrel_score,
                    'avg_xFIP': avg_xfip,
                    'avg_xFIP_score': avg_xfip_score,
                    'avg_Barrel%': avg_barrel_pct,
                    'avg_Barrel%_score': avg_barrel_score
                }
        # Always include averages if not overridden above
        this_game_stats.setdefault('avg_xFIP', avg_xfip)
        this_game_stats.setdefault('avg_xFIP_score', avg_xfip_score)
        this_game_stats.setdefault('avg_Barrel%', avg_barrel_pct)
        this_game_stats.setdefault('avg_Barrel%_score', avg_barrel_score)

        # Convert any remaining NaNs to None for JSON
        import math
        for key, val in list(this_game_stats.items()):
            if isinstance(val, float) and math.isnan(val):
                this_game_stats[key] = None

        logging.debug(
            f"[{game_id}] Computed stats for {prob['fullName']}: {this_game_stats}")

        pitchers.append({
            "insufficient_data": insufficient_data,
            "game_id": game_id,
            "side": side,
            "id": pid,
            "name": prob['fullName'],
            "team": game["teams"][side]["team"]["name"],
            "calculated_stats": {
                "recent_avgs": this_game_stats,
                "last5_games": last5_map
            }
        })

    logging.info(f"[{game_id}] Final pitcher count: {len(pitchers)}")
    return pitchers


def main():
    cfg = load_config()
    logging.config.dictConfig(cfg.get("logging", {}))

    # Sample stub for tomorrow's game (gamePk 777291)
    # Giants at Diamondbacks on 2025-07-01
    game = {
        "gamePk": 777291,
        "teams": {
            "away": {
                "team": {"id": 137, "name": "San Francisco Giants"},
                "probablePitcher": {"id": 657277, "fullName": "Logan Webb"}
            },
            "home": {
                "team": {"id": 109, "name": "Arizona Diamondbacks"},
                "probablePitcher": {"id": 669194, "fullName": "Ryne Nelson"}
            }
        }
    }

    # Fetch details and print JSON (nulls for missing values)
    ps = fetch_game_details(game)
    print(json.dumps(ps, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
