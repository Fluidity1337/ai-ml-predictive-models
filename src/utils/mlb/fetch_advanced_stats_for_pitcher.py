#!/usr/bin/env python3
import logging
import argparse
import sys
import warnings
from datetime import datetime, date, timedelta

import pandas as pd
from pybaseball import statcast_single_game
from fetch_games_by_pitcher import FetchGamesByPitcher
from utils.config_loader import load_config
from utils.helpers import RatingCalculator, FeatureConfigLoader

cfg = load_config()
logging.config.dictConfig(cfg["logging"])
features_path = cfg["models"]["mlb_rfi"]["feature_definitions_path"]
features_cfg = FeatureConfigLoader.load_features_config(features_path)


class PitcherXfipAnalyzer:
    """
    Analyze a pitcher's xFIP and barrel percentage across games in a date range.
    """

    def __init__(self, pitcher_id: int, start: date = None, end: date = None):
        self.pitcher_id = pitcher_id
        self.pitcher_name = None
        self.team_name = None

        self.fetcher = FetchGamesByPitcher(pitcher_id, start=start, end=end)
        self.games = self.fetcher.fetch_games()
        # records: list of (game_pk, game_date, xFIP, barrel_pct)
        self.records = []

    def analyze(self):
        """
        Compute xFIP and barrel% for each fetched game.
        """
        recs = []
        for gp, gd in self.games:
            try:
                # pull Statcast data for game
                df = statcast_single_game(gp)
                df_p = df[df['pitcher'] == self.pitcher_id]
                if self.pitcher_name is None and not df_p.empty:
                    try:
                        # Extract name from nested matchup field
                        first_matchup = df_p.iloc[0]['matchup']
                        self.pitcher_name = (
                            first_matchup['pitcher']['fullName']
                            if isinstance(first_matchup, dict) and 'pitcher' in first_matchup
                            else f"ID {self.pitcher_id}"
                        )

                    except Exception:
                        self.pitcher_name = f"ID {self.pitcher_id}"

                    # Infer team from inning
                    try:
                        is_home = (df_p['inning_topbot'] ==
                                   'Top').mode()[0] == 'Top'

                        team_col = 'home_team' if is_home else 'away_team'
                        if team_col in df.columns:
                            self.team_name = df[team_col].mode()[0]
                        else:
                            self.team_name = "Unknown"
                    except Exception:
                        self.team_name = "Unknown"

                # compute xFIP
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
                # compute barrel%
                # 6 = Barrel zone in launch_speed_angle
                barrels = df_p['launch_speed_angle'].eq(6).sum()
                batted = df_p['launch_speed'].notna().sum()
                barrel_pct = float('nan')
                if batted > 0:
                    barrel_pct = barrels / batted * 100.0
                # Scale metrics (bounds set from historical MLB data ranges)
                rating_calculator = RatingCalculator(features_cfg)
                xfip_score = rating_calculator.minmax_scale(
                    xfip, "xFIP", reverse=True)
                barrel_score = rating_calculator.minmax_scale(
                    barrel_pct, "BarrelPct", reverse=True)

                recs.append((gp, gd, xfip, xfip_score,
                            barrel_pct, barrel_score))
            except Exception as e:
                logging.error("Error analyzing game %s: %s", gp, e)
                recs.append((gp, gd, float('nan'), 50, float('nan'), 50))
        self.records = recs
        return recs

    def summary(self):
        """
        Print detailed per-game scores and averages.
        """
        name = self.pitcher_name or f"Pitcher ID {self.pitcher_id}"
        team = self.team_name or "Unknown Team"
        print(f"\nSummary for pitcher {name} ({team}):")

        if not self.records:
            print(
                f"No games pitched by {self.pitcher_id} in {self.fetcher.start}→{self.fetcher.end}.")
            return

        xfips, barrels, xfip_scores, barrel_scores = [], [], [], []
        for gp, gd, xf, xf_s, bp, bp_s in self.records:
            xf_str = f"{xf:.2f} ({xf_s}/100)" if not pd.isna(xf) else "NA"
            bp_str = f"{bp:.1f}% ({bp_s}/100)" if not pd.isna(bp) else "NA"
            print(f"Game {gp} on {gd}: xFIP = {xf_str}, Barrel% = {bp_str}")

            if not pd.isna(xf):
                xfips.append(xf)
                xfip_scores.append(xf_s)
            if not pd.isna(bp):
                barrels.append(bp)
                barrel_scores.append(bp_s)

        avg_xfip = sum(xfips) / len(xfips) if xfips else float('nan')
        avg_xfip_score = sum(xfip_scores) / \
            len(xfip_scores) if xfip_scores else 50
        avg_barrel = sum(barrels) / len(barrels) if barrels else float('nan')
        avg_barrel_score = sum(barrel_scores) / \
            len(barrel_scores) if barrel_scores else 50
        count = len(self.records)

        print(
            f"\nOver {count} games ({self.fetcher.start}→{self.fetcher.end}):")
        print(f"  Average xFIP: {avg_xfip:.2f} ({avg_xfip_score:.1f}/100)")
        print(
            f"  Average Barrel%: {avg_barrel:.1f}% ({avg_barrel_score:.1f}/100)")
        print(f"  Average xFIP Score: {avg_xfip_score:.1f}/100")
        print(f"  Average Barrel% Score: {avg_barrel_score:.1f}/100")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze a pitcher's xFIP and Barrel% over a date range via class."
    )
    parser.add_argument("pitcher_id", type=int, help="MLBAM pitcher ID")
    parser.add_argument(
        "--start", type=lambda s: datetime.fromisoformat(s).date(),
        help="Start date YYYY-MM-DD (defaults to 30 days ago)"
    )
    parser.add_argument(
        "--end",   type=lambda s: datetime.fromisoformat(s).date(),
        help="End date YYYY-MM-DD (defaults to today)"
    )
    args = parser.parse_args()
    try:
        analyzer = PitcherXfipAnalyzer(
            args.pitcher_id, start=args.start, end=args.end
        )
        analyzer.analyze()
        analyzer.summary()
    except Exception as e:
        logging.error("Fatal error: %s", e)
        sys.exit(1)
