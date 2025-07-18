#!/usr/bin/env python3
import logging
import argparse
import sys
import os
from datetime import datetime, date, timedelta

import pandas as pd
from pybaseball import statcast_single_game
from utils.mlb.fetch_games_by_pitcher import FetchGamesByPitcher
from utils.config_loader import load_config
from utils.helpers import RatingCalculator, FeatureConfigLoader

# Load config and logging
cfg = load_config()
try:
    log_cfg = cfg.get("logging", {})
    handlers = log_cfg.get("handlers", {})
    file_h = handlers.get("file", {})
    if file_h:
        os.makedirs(os.path.dirname(file_h.get("filename", "")), exist_ok=True)
    logging.config.dictConfig(log_cfg)
except Exception as e:
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s %(levelname)-8s %(message)s")
    logging.warning(
        "Could not configure file logging, using console only: %s", e)

# Load feature config
features_path = cfg["models"]["mlb_rfi"]["feature_definitions_path"]
features_cfg = FeatureConfigLoader.load_features_config(features_path)


def lookup_advanced_stats(pitcher_id, start=None, end=None):
    analyzer = PitcherAdvancedStats(pitcher_id, start=start, end=end)
    analyzer.analyze()
    # build a dict keyed by game_pk from analyzer.records
    return {
        rec[0]: {
            "date":    rec[1],
            "xFIP":    rec[2],
            "xFIP_score":   rec[3],
            "Barrel%": rec[4],
            "Barrel%_score": rec[5],
        }
        for rec in analyzer.records
    }


class PitcherAdvancedStats:
    """
    Analyze a pitcher's xFIP and barrel percentage across games in a date range.
    """

    def __init__(self, pitcher_id: int, start: date = None, end: date = None):
        self.pitcher_id = pitcher_id
        self.pitcher_name = None
        self.team_name = None
        self.fetcher = FetchGamesByPitcher(pitcher_id, start=start, end=end)
        self.start = self.fetcher.start
        self.end = self.fetcher.end
        self.games = self.fetcher.fetch_games()
        # Records: list of (game_pk, date, xfip, xfip_score, barrel_pct, barrel_score)
        self.records = []

    def analyze(self):
        recs = []
        for gp, gd in self.games:
            try:
                df = statcast_single_game(gp)
                df_p = df[df['pitcher'] == self.pitcher_id]
                # Set pitcher name
                if self.pitcher_name is None and not df_p.empty:
                    first = df_p.iloc[0]
                    mp = first.get('matchup', {})
                    self.pitcher_name = mp.get('pitcher', {}).get(
                        'fullName') if isinstance(mp, dict) else f"ID {self.pitcher_id}"
                # Determine team
                try:
                    half = df_p['inning_topbot'].mode()[0]
                    is_home = (half == 'Top')
                    team_col = 'home_team' if is_home else 'away_team'
                    self.team_name = df[team_col].mode(
                    )[0] if team_col in df.columns else "Unknown"
                except Exception:
                    self.team_name = "Unknown"
                # Compute xFIP and Barrel%
                hr = df_p['events'].eq('home_run').sum()
                bb = df_p['bb_type'].eq('walk').sum()
                hbp = df_p['events'].eq('hit_by_pitch').sum()
                k = df_p['events'].eq('strikeout').sum()
                fb = df_p[(df_p['launch_speed'].notna()) & (
                    df_p['launch_angle'] > 15)].shape[0]
                outs = df_p['outs_when_up'].sum()
                ip = outs / 3.0
                xfip = float('nan')
                if ip > 0:
                    hr_exp = fb * 0.105
                    xfip = (13 * hr_exp + 3 * (bb + hbp) - 2 * k) / ip + 3.20
                barrels = df_p['launch_speed_angle'].eq(6).sum()
                batted = df_p['launch_speed'].notna().sum()
                barrel_pct = float('nan')
                if batted > 0:
                    barrel_pct = barrels / batted * 100.0
                # Scale
                rc = RatingCalculator(features_cfg)
                xfip_score = rc.minmax_scale(xfip, "xFIP", reverse=True)
                barrel_score = rc.minmax_scale(
                    barrel_pct, "BarrelPct", reverse=True)
                recs.append((gp, gd, xfip, xfip_score,
                            barrel_pct, barrel_score))
            except Exception as e:
                logging.error("Error analyzing game %s: %s", gp, e)
                recs.append((gp, gd, float('nan'), 50, float('nan'), 50))
        self.records = recs
        return recs

    def to_dataframe(self, existing_df: pd.DataFrame = None) -> pd.DataFrame:
        """
        Convert analyzed records to a DataFrame, appending to existing_df if provided.
        Columns: pitcher_id, game_pk, date, xFIP, xFIP_score, Barrel%, Barrel%_score
        """
        if not self.records:
            # Run analysis if not done
            self.analyze()
        df = pd.DataFrame([
            {
                'pitcher_id':    self.pitcher_id,
                'game_pk':       gp,
                'date':          gd,
                'xFIP':          xf,
                'xFIP_score':    xfs,
                'Barrel%':       bp,
                'Barrel%_score': bps
            }
            for gp, gd, xf, xfs, bp, bps in self.records
        ])
        if existing_df is not None:
            return pd.concat([existing_df, df], ignore_index=True)
        return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze a pitcher's xFIP and Barrel% and return a DataFrame."
    )
    parser.add_argument("pitcher_id", type=int, help="MLBAM pitcher ID")
    parser.add_argument(
        "--start", type=lambda s: datetime.fromisoformat(s).date(),
        help="Start date YYYY-MM-DD"
    )
    parser.add_argument(
        "--end",   type=lambda s: datetime.fromisoformat(s).date(),
        help="End date YYYY-MM-DD"
    )
    args = parser.parse_args()
    pas = PitcherAdvancedStats(args.pitcher_id, start=args.start, end=args.end)
    df = pas.to_dataframe()
    print(df.to_string(index=False))
