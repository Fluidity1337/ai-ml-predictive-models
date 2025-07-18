#!/usr/bin/env python3
import logging
import logging.config
import os
import sys
import argparse
from datetime import datetime, date, timedelta

import pandas as pd
from pybaseball import statcast_single_game
from utils.mlb.fetch_games_by_pitcher import FetchGamesByPitcher
from utils.config_loader import load_config
from utils.helpers import RatingCalculator, FeatureConfigLoader
# First-inning utilities
from utils.mlb.get_f1_stats import compute_first_inning_era, compute_first_inning_whip

# Configure logging
cfg = load_config()
try:
    log_cfg = cfg.get("logging", {})
    handlers = log_cfg.get("handlers", {})
    file_handler = handlers.get("file", {})
    if file_handler:
        os.makedirs(os.path.dirname(
            file_handler.get("filename", "")), exist_ok=True)
    logging.config.dictConfig(log_cfg)
except Exception as e:
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s %(levelname)-8s %(message)s")
    logging.warning(
        "Could not configure file logging, using console only: %s", e)

# Load feature config
features_path = cfg["models"]["mlb_rfi"]["feature_definitions_path"]
features_cfg = FeatureConfigLoader.load_features_config(features_path)


class PitcherAdvancedStats:
    """
    Analyze a pitcher's per-game xFIP and Barrel% across a date range,
    compute first-inning ERA and WHIP, and compute average metrics.
    """

    def __init__(self, pitcher_id: int, start: date = None, end: date = None):
        self.pitcher_id = pitcher_id
        self.pitcher_name = None
        self.team_name = None
        self.fetcher = FetchGamesByPitcher(pitcher_id, start=start, end=end)
        self.start = self.fetcher.start
        self.end = self.fetcher.end
        self.games = self.fetcher.fetch_games()
        # records: game_pk, game_date, xfip, xfip_score, barrel_pct, barrel_score
        self.records = []
        # average metrics
        self.avg_xfip = float('nan')
        self.avg_xfip_score = float('nan')
        self.avg_barrel_pct = float('nan')
        self.avg_barrel_score = float('nan')

    def analyze(self):
        recs = []
        for gp, gd in self.games:
            try:
                df = statcast_single_game(gp)
                df_p = df[df['pitcher'] == self.pitcher_id]
                if self.pitcher_name is None and not df_p.empty:
                    mp = df_p.iloc[0].get('matchup', {})
                    self.pitcher_name = mp.get('pitcher', {}).get(
                        'fullName', f"ID {self.pitcher_id}")
                # xFIP calculation
                hr = df_p['events'].eq('home_run').sum()
                bb = df_p['bb_type'].eq('walk').sum()
                hbp = df_p['events'].eq('hit_by_pitch').sum()
                k = df_p['events'].eq('strikeout').sum()
                fb = df_p[(df_p['launch_speed'].notna()) & (
                    df_p['launch_angle'] > 15)].shape[0]
                outs = df_p['outs_when_up'].sum(
                ) if 'outs_when_up' in df_p.columns else df_p['outs'].sum()
                ip = outs / 3.0 if outs > 0 else 0
                xfip = float('nan')
                if ip > 0:
                    hr_exp = fb * 0.105
                    xfip = (13 * hr_exp + 3 * (bb + hbp) - 2 * k) / ip + 3.20
                # Barrel % calculation
                barrels = df_p['launch_speed_angle'].eq(
                    6).sum() if 'launch_speed_angle' in df_p.columns else 0
                batted = df_p['launch_speed'].notna().sum(
                ) if 'launch_speed' in df_p.columns else 0
                barrel_pct = (barrels / batted *
                              100.0) if batted > 0 else float('nan')
                # scale scores
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
        # compute averages
        xfips = [r[2] for r in recs if pd.notna(r[2])]
        xfip_scores = [r[3] for r in recs if pd.notna(r[3])]
        barrel_pcts = [r[4] for r in recs if pd.notna(r[4])]
        barrel_scores = [r[5] for r in recs if pd.notna(r[5])]
        self.avg_xfip = sum(xfips) / len(xfips) if xfips else float('nan')
        self.avg_xfip_score = sum(
            xfip_scores) / len(xfip_scores) if xfip_scores else float('nan')
        self.avg_barrel_pct = sum(
            barrel_pcts) / len(barrel_pcts) if barrel_pcts else float('nan')
        self.avg_barrel_score = sum(
            barrel_scores) / len(barrel_scores) if barrel_scores else float('nan')
        return recs

    def f1_era(self) -> str:
        """Compute the pitcher’s first-inning ERA over the configured date range."""
        return compute_first_inning_era(
            self.pitcher_id,
            self.start.isoformat(),
            self.end.isoformat()
        )

    def f1_whip(self) -> str:
        """Compute the pitcher’s first-inning WHIP over the configured date range."""
        return compute_first_inning_whip(
            self.pitcher_id,
            self.start.isoformat(),
            self.end.isoformat()
        )

    def summary(self):
        name = self.pitcher_name or f"ID {self.pitcher_id}"
        team = self.team_name or ""
        print(f"Summary for {name} ({team}):")
        for gp, gd, xf, xfsc, bp, bpsc in self.records:
            xf_str = f"{xf:.2f} ({xfsc}/100)" if pd.notna(xf) else "NA"
            bp_str = f"{bp:.1f}% ({bpsc}/100)" if pd.notna(bp) else "NA"
            print(f"Game {gp} on {gd}: xFIP = {xf_str}, Barrel% = {bp_str}")
        print(f"\nAverage over {len(self.records)} games:")
        print(f"  xFIP: {self.avg_xfip:.2f} ({self.avg_xfip_score:.1f}/100)")
        print(
            f"  Barrel%: {self.avg_barrel_pct:.1f}% ({self.avg_barrel_score:.1f}/100)")
        # first-inning stats
        fie = self.f1_era()
        fiw = self.f1_whip()
        print(f"First-inning ERA: {fie}, WHIP: {fiw}")


def pitcher_stats_to_df(
    pitcher_id: int,
    start: date = None,
    end: date = None,
    existing_df: pd.DataFrame = None
) -> pd.DataFrame:
    """
    Fetch per-game statistics and first-inning ERA/WHIP, return DataFrame.
    """
    pa = PitcherAdvancedStats(pitcher_id, start=start, end=end)
    pa.analyze()
    data = []
    for gp, gd, xf, xfsc, bp, bpsc in pa.records:
        data.append({
            'pitcher_id': pitcher_id,
            'game_pk': gp,
            'date': gd,
            'xFIP': xf,
            'xFIP_score': xfsc,
            'Barrel%': bp,
            'Barrel%_score': bpsc,
            'f1_era': pa.f1_era(),
            'f1_whip': pa.f1_whip()
        })
    df = pd.DataFrame(data)
    df['avg_xFIP'] = pa.avg_xfip
    df['avg_xFIP_score'] = pa.avg_xfip_score
    df['avg_Barrel%'] = pa.avg_barrel_pct
    df['avg_Barrel%_score'] = pa.avg_barrel_score
    if existing_df is not None:
        return pd.concat([existing_df, df], ignore_index=True)
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze a pitcher's stats including first-inning ERA/WHIP."
    )
    parser.add_argument("pitcher_id", type=int, help="MLBAM pitcher ID")
    parser.add_argument(
        "--start", type=lambda s: datetime.fromisoformat(s).date(),
        help="Start date YYYY-MM-DD"
    )
    parser.add_argument(
        "--end", type=lambda s: datetime.fromisoformat(s).date(),
        help="End date YYYY-MM-DD"
    )
    args = parser.parse_args()
    df = pitcher_stats_to_df(
        args.pitcher_id,
        start=args.start,
        end=args.end
    )
    print(df.to_string(index=False))
