import logging
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
from pybaseball import statcast

from utils.config_loader import load_config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class AdvancedTeamStats:
    def __init__(self, lookback_days: int = 7, force: bool = False):
        self.lookback_days = lookback_days
        self.config = load_config()
        self.team_woba_splits = {}
        self.force = force
        logger.debug(
            "Initialized AdvancedTeamStats with %d-day default lookback", self.lookback_days)

    def fetch_statcast_data(self, lookback_days: int) -> pd.DataFrame:
        cache_path = Path(f"data/statcast_{lookback_days}d_raw.csv")
        if not self.force and cache_path.exists():
            age_hours = (datetime.now(
            ) - datetime.fromtimestamp(cache_path.stat().st_mtime)).total_seconds() / 3600
            if age_hours < 12:
                logger.info(
                    "📂 Using cached Statcast CSV from %s (%.1f hrs old)", cache_path, age_hours)
                return pd.read_csv(cache_path)

        try:
            end = datetime.today().date()
            start = end - timedelta(days=lookback_days)
            logger.info("📥 Fetching Statcast data from %s to %s", start, end)
            df = statcast(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
            teams = df['home_team'].dropna().unique(
            ).tolist() if 'home_team' in df.columns else []
            games = df['game_date'].dropna().unique(
            ).tolist() if 'game_date' in df.columns else []
            logger.info(
                "📊 Statcast summary → Games: %d, Unique teams: %s", len(games), teams)
            df.to_csv(cache_path, index=False)
            logger.info("💾 Cached Statcast raw data to %s", cache_path)
            logger.debug("📊 Fetched %d rows from Statcast", len(df))
            return df
        except Exception as e:
            logger.warning("⚠️ Statcast fetch failed on first attempt: %s", e)
            try:
                logger.info("🔁 Retrying fetch after brief pause...")
                import time
                time.sleep(3)
                df = statcast(start.strftime("%Y-%m-%d"),
                              end.strftime("%Y-%m-%d"))
                logger.debug("📊 Retry fetch succeeded with %d rows", len(df))
                return df
            except Exception as e2:
                logger.exception("❌ Retry also failed: %s", e2)
                return pd.DataFrame()

    def compute_team_woba_split(self, lookback_days: int) -> dict:
        try:
            cache_path = Path(f"data/team_woba_{lookback_days}d.json")
            if cache_path.exists():
                age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
                if age.days > 3:
                    logger.info(
                        "🧹 Cache %s is %d days old. Deleting...", cache_path, age.days)
                    cache_path.unlink(missing_ok=True)
                else:
                    logger.info("📦 Using cached wOBA data from %s", cache_path)
                    with open(cache_path, "r", encoding="utf-8") as f:
                        return json.load(f)

            df = self.fetch_statcast_data(lookback_days)
            if df.empty:
                logger.warning(
                    "Statcast data is empty for %d-day lookback. Returning empty dict.", lookback_days)
                return {}

            df_first_inning = df[df['inning'] == 1]
            logger.debug("Filtered to %d first-inning rows for %d-day window",
                         len(df_first_inning), lookback_days)

            if 'batting_team' not in df_first_inning.columns:
                logger.warning(
                    "Statcast data missing 'batting_team'. Attempting fallback using 'team' or 'team_name'...")
                logger.debug("Available columns: %s",
                             list(df_first_inning.columns))

                for alt_col in ['team', 'team_name', 'home_team', 'away_team']:
                    if alt_col in df_first_inning.columns:
                        fallback_values = df_first_inning[alt_col].dropna(
                        ).unique().tolist()
                        if any(len(str(v)) > 25 for v in fallback_values):
                            logger.warning(
                                "⚠️ Fallback column '%s' contains unstandardized values: %s", alt_col, fallback_values[:5])
                        logger.info(
                            "✅ Fallback succeeded using column '%s'", alt_col)
                        df_first_inning[alt_col] = df_first_inning[alt_col].astype(
                            str).str.strip().str.title()
                        woba_by_team = df_first_inning.groupby(
                            alt_col)['woba_value'].mean().to_dict()
                        return woba_by_team

                logger.error("❌ No usable team column found. Skipping.")
                return {}

            woba_by_team = df_first_inning.groupby(
                'batting_team')['woba_value'].mean().to_dict()
            logger.info("Computed wOBA for %d teams over %d days",
                        len(woba_by_team), lookback_days)

            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(woba_by_team, f, indent=2)
                logger.info("Cached %dd wOBA to %s", lookback_days, cache_path)

            return woba_by_team

        except Exception as e:
            logger.exception(
                "Error computing %d-day wOBA split: %s", lookback_days, e)
            return {}

    def compute_all_splits(self, force: bool = False):
        combined_path = Path("data/team_woba_splits_combined.json")
        if not force and combined_path.exists():
            age_hours = (datetime.now(
            ) - datetime.fromtimestamp(combined_path.stat().st_mtime)).total_seconds() / 3600
            if age_hours < 12:
                logger.info(
                    "🕒 Cached combined split file is recent (%.1f hrs). Loading from cache.", age_hours)
                return self.load_from_json(combined_path)

        from concurrent.futures import ThreadPoolExecutor
        logger.info(
            "Computing team-level wOBA3 splits (7d, 14d; 30d and season disabled for now)")
        results = {}

        results["7d"] = self.compute_team_woba_split(7)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.compute_team_woba_split, 14)
            try:
                results["14d"] = future.result()
            except Exception as e:
                logger.warning("14d wOBA3 computation failed: %s", e)
                results["14d"] = {}

        self.team_woba_splits = results
        logger.debug("Finished computing all wOBA splits")
        return self.team_woba_splits

    def save_to_json(self, output_path: Path):
        try:
            if not self.team_woba_splits:
                logger.warning("No wOBA data to save. Skipping JSON export.")
                return

            output_path.parent.mkdir(parents=True, exist_ok=True)
            date_range = {
                'generated_at': datetime.now().isoformat(),
                'range': {
                    '7d': (datetime.today() - timedelta(days=7)).strftime('%Y-%m-%d'),
                    '14d': (datetime.today() - timedelta(days=14)).strftime('%Y-%m-%d')
                }
            }
            payload = {
                'meta': date_range,
                'splits': self.team_woba_splits
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            logger.info("Saved wOBA splits to %s", output_path)
        except Exception as e:
            logger.exception("Failed to save wOBA splits to JSON: %s", e)

    def load_from_json(self, input_path: Path):
        try:
            if not input_path.exists():
                logger.warning(
                    "JSON file %s does not exist. Skipping load.", input_path)
                return {}

            with open(input_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.team_woba_splits = data.get('splits', {})
            logger.info("Loaded wOBA splits from %s", input_path)
            return self.team_woba_splits

        except Exception as e:
            logger.exception("Failed to load wOBA splits from JSON: %s", e)
            return {}


if __name__ == "__main__":
    from colorama import init as colorama_init
    colorama_init()

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    stats = AdvancedTeamStats(force='--force' in sys.argv)
    splits = stats.compute_all_splits()

    stats.save_to_json(Path("data/team_woba_splits_combined.json"))

    if splits:
        for period, data in splits.items():
            print(f"\n{period.upper()} split wOBA3:")
            for team, value in sorted(data.items(), key=lambda x: x[1], reverse=True):
                print(f"{team:>20}: {value:.3f}")
