#!/usr/bin/env python3
from pybaseball import statcast_pitcher
import pandas as pd
import argparse
from datetime import datetime, date, timedelta
import sys
import logging.config

from utils.config_loader import load_config
from utils.helpers import FeatureConfigLoader

# 1. Load YAML config
cfg = load_config()

# 2. Apply logging configuration from YAML
logging.config.dictConfig(cfg["logging"])

# 3. Load your model’s feature definitions
# Load the features configuration
features_path = cfg["models"]["mlb_rfi"]["feature_definitions_path"]
features_cfg = FeatureConfigLoader.load_features_config(features_path)

# Now you can access:
#   cfg["api"]["mlb"]["pitcher"], cfg["defaults"]["lookback_days"], etc.
#   features_cfg["BarrelPct"]["weight"], features_cfg["BarrelPct"]["bounds"], etc.


class FetchGamesByPitcher:

    def __init__(self, pitcher_id: int, start: date = None, end: date = None):
        self.pitcher_id = pitcher_id
        self.today = datetime.today().date()
        # Default date window: last 30 days up to today
        self.start = start if start else self.today - timedelta(days=30)
        self.end = end if end else self.today
        # Clamp end to today
        if self.end > self.today:
            logging.warning(
                f"End date {self.end} is in the future; clamping to today {self.today}")
            self.end = self.today
        # Validate ordering
        if self.end < self.start:
            raise ValueError(f"Invalid date range {self.start} → {self.end}")
        # Extend window to last 35 days unless single-day query
        if self.start != self.end:
            self.start = max(self.start, self.today - timedelta(days=35))

    def fetch_games(self) -> list[tuple[int, date]]:
        """
        Pull every pitch by this pitcher in the window, then return unique (game_pk, game_date).
        """
        # pull every pitch for this pitcher in [start,end]
        df = statcast_pitcher(self.start.strftime("%Y-%m-%d"),
                              self.end.strftime("%Y-%m-%d"),
                              self.pitcher_id)

        if df is None or df.empty:
            logging.info("No Statcast pitches for %s in %s→%s",
                         self.pitcher_id, self.start, self.end)
            return []

        # ensure game_pk and game_date exist
        if "game_pk" not in df.columns or "game_date" not in df.columns:
            logging.error("Statcast response missing game_pk or game_date")
            return []

        # convert game_date to date
        df["game_date"] = pd.to_datetime(df["game_date"]).dt.date

        # drop duplicates and sort
        games = (
            df[["game_pk", "game_date"]]
            .drop_duplicates()
            .sort_values("game_date")
            .to_records(index=False)
        )
        games = [(int(gp), gd) for gp, gd in games]

        logging.info("Found %d appearances for %s→%s: %s",
                     len(games), self.start, self.end,
                     [gd.isoformat() for _, gd in games])
        return games


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch games pitched by an MLB pitcher via Statcast lookup."
    )
    parser.add_argument("pitcher_id", type=int, help="MLBAM pitcher ID")
    parser.add_argument("--start", type=lambda s: datetime.fromisoformat(s).date(),
                        help="Start date YYYY-MM-DD")
    parser.add_argument("--end",   type=lambda s: datetime.fromisoformat(s).date(),
                        help="End date YYYY-MM-DD")
    args = parser.parse_args()

    try:
        fetcher = FetchGamesByPitcher(args.pitcher_id, args.start, args.end)
        games = fetcher.fetch_games()
        if not games:
            print(
                f"No games pitched by {args.pitcher_id} in {fetcher.start}→{fetcher.end}.")
        else:
            for gp, gd in games:
                print(f"Game {gp} on {gd}")
            print(f"Total games: {len(games)}")
    except Exception as e:
        logging.error("Error: %s", e)
        sys.exit(1)
