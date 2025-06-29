from io import StringIO
import os
from bs4 import BeautifulSoup
import requests
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


class BaseStats:
    def __init__(self):
        self.config = load_config()
        self.root_path = Path(self.config.get("root_path", "."))
        self.mlb_cfg = self.config.get("mlb_data", {})
        self.statcast_cfg = self.mlb_cfg.get("statcast", {})
        self.cache_path = Path(self.config.get("cache_path", ".cache"))
        self.output_path = self.root_path / self.mlb_cfg.get("outputs_path")


class AdvancedTeamStats(BaseStats):
    def __init__(self, lookback_days: int = 7, force: bool = False, quiet: bool = False):
        super().__init__()
        self.lookback_days = lookback_days
        self.team_woba_splits = {}
        self.force = force
        self.quiet = quiet

        # Build paths from config
        self.raw_csv_path = self.root_path / self.statcast_cfg.get("raw_csv")
        self.woba_split_path = self.root_path / \
            self.statcast_cfg.get("split_json")
        self.combined_path = self.root_path / \
            self.statcast_cfg.get("combined_json")
        self.csv_export_path = self.output_path / \
            f"woba3-features-{self.lookback_days}d.csv"

        logger.debug(
            "Initialized AdvancedTeamStats with %d-day default lookback", self.lookback_days)

    def fetch_statcast_data(self, lookback_days: int) -> pd.DataFrame:
        cache_path = Path(
            str(self.raw_csv_path).format(lookback=lookback_days))
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
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache_path, index=False)
            logger.info("📂 Cached Statcast raw data to %s", cache_path)
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
            # This metric represents wOBA in the FIRST INNING ONLY — a proxy for the performance of the top 3 in the batting order.
            # We refer to it as "wOBA3" throughout for consistency, even though it's not literally per-player.
            cache_path = Path(
                str(self.woba_split_path).format(lookback=lookback_days))
            if cache_path.exists():
                age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
                if age.days > 3:
                    logger.info(
                        "🩹 Cache %s is %d days old. Deleting...", cache_path, age.days)
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
        if not force and self.combined_path.exists():
            age_hours = (datetime.now(
            ) - datetime.fromtimestamp(self.combined_path.stat().st_mtime)).total_seconds() / 3600
            if age_hours < 12:
                logger.info(
                    "🕒 Cached combined split file is recent (%.1f hrs). Loading from cache.", age_hours)
                return self.load_from_json(self.combined_path)

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

    def save_wrclike_to_json(self):
        try:
            wrclike = self.fetch_wrclike_splits_from_fangraphs()
            if not wrclike:
                logger.warning(
                    "No wRCP1st data to save. Skipping JSON export.")
                return

            wrclike_path = self.output_path / \
                f"wrclike_1st_inning_{datetime.today().strftime('%Y%m%d')}.json"
            wrclike_path.parent.mkdir(parents=True, exist_ok=True)
            with open(wrclike_path, "w", encoding="utf-8") as f:
                json.dump(wrclike, f, indent=2)
            logger.info("Saved wRCP1st splits to %s", wrclike_path)
        except Exception as e:
            logger.exception("Failed to save wRCP1st splits to JSON: %s", e)

    def save_to_csv(self):
        try:
            if not self.team_woba_splits:
                logger.warning("No wOBA data to save. Skipping CSV export.")
                return

            rows = []
            all_teams = set()
            for period in self.team_woba_splits:
                all_teams.update(self.team_woba_splits[period].keys())

            for team in sorted(all_teams):
                row = {"Team": team}
                for period, data in self.team_woba_splits.items():
                    row[f"wOBA_{period}"] = data.get(team, None)
                rows.append(row)

            df = pd.DataFrame(rows)
            self.csv_export_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(self.csv_export_path, index=False)
            logger.info("Exported wOBA splits to CSV: %s",
                        self.csv_export_path)
        except Exception as e:
            logger.exception("CSV export failed: %s", e)

    def save_wrclike_to_csv(self):
        try:
            wrclike = self.fetch_wrclike_splits_from_fangraphs()
            if not wrclike:
                logger.warning("No wRCP1st data to save. Skipping CSV export.")
                return

            df = pd.DataFrame(list(wrclike.items()),
                              columns=["Team", "wRCP1st"])
            path = self.output_path / \
                f"wrclike_1st_inning_{datetime.today().strftime('%Y%m%d')}.csv"
            path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(path, index=False)
            logger.info("Exported wRCP1st to CSV: %s", path)

        except Exception as e:
            logger.exception("CSV export of wRCP1st failed: %s", e)

    def fetch_wrclike_splits_from_fangraphs(self) -> dict:
        # IMPLEMENT LATER
        """
        Fetch per-team 1st-inning wRC+ via FanGraphs' CSV export,
        with safe fallbacks if headers aren’t exactly as expected.
        """
        try:
            url = (
                "https://www.fangraphs.com/leaders/splits-leaderboards.csv"
                "?splitArr=44"
                "&splitTeams=true"
                "&statType=team"
                "&statgroup=2"
                "&startDate=2025-03-01"
                "&endDate=2025-11-01"
                "&groupBy=team"
                "&position=B"
                "&sort=15,1"
            )
            logger.info("🌐 Fetching CSV splits from FanGraphs: %s", url)
            df = pd.read_csv(url, engine="python", on_bad_lines="skip")
            logger.debug("CSV columns: %s", df.columns.tolist())

            # 1) Team column: prefer "Team", then "Tm", else first column
            team_candidates = [c for c in df.columns if c in ("Team", "Tm")]
            if team_candidates:
                team_col = team_candidates[0]
            else:
                team_col = df.columns[0]
                logger.warning(
                    "No 'Team' or 'Tm' column found—falling back to first column: %r", team_col)

            # 2) Stat column: prefer any containing "RC+", else last column
            stat_candidates = [c for c in df.columns if "RC+" in c]
            if stat_candidates:
                stat_col = stat_candidates[0]
            else:
                stat_col = df.columns[-1]
                logger.warning(
                    "No 'RC+' column found—falling back to last column: %r", stat_col)

            logger.debug("Using team_col=%r, stat_col=%r", team_col, stat_col)

            out = dict(zip(df[team_col].astype(str).str.strip(),
                           df[stat_col].astype(float)))
            logger.info("✅ Parsed %s for %d teams", stat_col, len(out))
            return out

        except Exception as e:
            logger.exception("❌ Failed to fetch or parse FanGraphs CSV: %s", e)
            return {}

    def get1stInningStats(csv_path="splits_1st_2025.csv", decode_uri_fn=None, data_uri=None):
        """
        Returns the team‐level first‐inning wRC+ table as a DataFrame.
        If csv_path exists on disk, we load it.  Otherwise we call decode_uri_fn(data_uri)
        to fetch & decode, then save it to csv_path and return that DataFrame.
        """
        if os.path.exists(csv_path):
            return pd.read_csv(csv_path)
        if not (decode_uri_fn and data_uri):
            raise RuntimeError(
                "No CSV cache and no URI fetch function/URI provided")
        df = decode_uri_fn(data_uri)
        df.to_csv(csv_path, index=False)
        return df

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

    force_flag = '--force' in sys.argv
    quiet_flag = '--quiet' in sys.argv

    stats = AdvancedTeamStats(force=force_flag, quiet=quiet_flag)
    splits = stats.compute_all_splits()

    stats.save_to_json(stats.combined_path)
    stats.save_to_csv()
    stats.save_wrclike_to_json()
    stats.save_wrclike_to_csv()

    # Save combined CSV with both wOBA3 and wRCP1st
    try:
        woba_df = pd.read_csv(stats.csv_export_path)
        wrclike = stats.fetch_wrclike_splits_from_fangraphs()
        wrclike_df = pd.DataFrame(
            list(wrclike.items()), columns=["Team", "wRCP1st"])
        combined = pd.merge(woba_df, wrclike_df, on="Team", how="left")
        combined_path = stats.output_path / \
            f"combined_features_{datetime.today().strftime('%Y%m%d')}.csv"
        combined.to_csv(combined_path, index=False)
        logger.info("📦 Saved combined CSV to %s", combined_path)
    except Exception as e:
        logger.exception("❌ Failed to save combined CSV: %s", e)

    if not quiet_flag and splits:
        for period, data in splits.items():
            print(f"\n{period.upper()} split wOBA3:")
            for team, value in sorted(data.items(), key=lambda x: x[1], reverse=True):
                print(f"{team:>20}: {value:.3f}")
