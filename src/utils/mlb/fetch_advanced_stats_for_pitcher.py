#!/usr/bin/env python3
import logging
import argparse
import sys
import warnings
from datetime import datetime, date, timedelta

import pandas as pd
from pybaseball import statcast_single_game
from fetch_games_by_pitcher import FetchGamesByPitcher

# Suppress FutureWarnings from pybaseball internals
warnings.filterwarnings("ignore", category=FutureWarning, module="pybaseball")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


class PitcherXfipAnalyzer:
    """
    Analyze a pitcher's xFIP and barrel percentage across games in a date range.
    """

    def __init__(self, pitcher_id: int, start: date = None, end: date = None):
        self.pitcher_id = pitcher_id
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
                recs.append((gp, gd, xfip, barrel_pct))
            except Exception as e:
                logging.error("Error analyzing game %s: %s", gp, e)
                recs.append((gp, gd, float('nan'), float('nan')))
        self.records = recs
        return recs

    def summary(self):
        """
        Print the per-game xFIP, barrel%, and the average xFIP with game count.
        """
        if not self.records:
            print(
                f"No games pitched by {self.pitcher_id} in {self.fetcher.start}→{self.fetcher.end}.")
            return
        xfips = []
        barrels = []
        for gp, gd, xf, bp in self.records:
            xf_str = f"{xf:.2f}" if not pd.isna(xf) else "NA"
            bp_str = f"{bp:.1f}%" if not pd.isna(bp) else "NA"
            print(f"Game {gp} on {gd}: xFIP = {xf_str}, Barrel% = {bp_str}")
            if not pd.isna(xf):
                xfips.append(xf)
            if not pd.isna(bp):
                barrels.append(bp)
        avg_xfip = sum(xfips) / len(xfips) if xfips else float('nan')
        avg_barrel = sum(barrels) / len(barrels) if barrels else float('nan')
        count = len(self.records)
        print(
            f"\nOver {count} games ({self.fetcher.start}→{self.fetcher.end}):")
        print(f"  Average xFIP: {avg_xfip:.2f}")
        print(f"  Average Barrel%: {avg_barrel:.1f}%")


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
