"""
Fetch and Store wRC+ CSV from Fangraphs.

REQUIRED:
  --output_dir   Output directory for CSV (default: from config)
  --date         Date in YYYY-MM-DD format (default: today)
  --fg_url       Fangraphs URL (default: from config)

USAGE EXAMPLES:
  # Fetch today's wRC+ CSV to default location
  python -m src.utils.mlb.fetch_wrc_teams_daily

  # Fetch for a specific date and output directory
  python -m src.utils.mlb.fetch_wrc_teams_daily --output_dir data/baseball/mlb/raw --date 2025-07-24

NOTES:
- This script is designed for file-based workflows but is structured to allow future scaling to database (DB) backends.
- To support DB, refactor fetch_wrc_plus and output logic to use DB queries/inserts instead of file I/O.
"""

# --- Fetch and Store wRC+ CSV from Fangraphs ---

import os
import requests
from datetime import datetime
from src.utils.config_loader import load_config
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


def fetch_wrc_plus(output_dir=None, date=None, fg_url=None):
    """
    Fetches wRC+ CSV for a given date from Fangraphs and saves to output_dir.
    All config values are loaded from config.yaml via config_loader.
    Args:
        output_dir (str): Directory to save CSV. If None, uses config.
        date (str): Date in YYYY-MM-DD format. If None, uses today.
        fg_url (str): Fangraphs URL. If None, uses config or default.
    Returns:
        str: Path to saved CSV file.
    """
    config = load_config()
    mlb_data = config.get("mlb_data", {})
    # Get Fangraphs URL from config, add if missing
    if not fg_url:
        fg_url = mlb_data.get("fangraphs_wrc_url")
        if not fg_url:
            fg_url = "https://www.fangraphs.com/leaders/splits-leaderboards"
            mlb_data["fangraphs_wrc_url"] = fg_url
            logging.info(f"Added fangraphs_wrc_url to config: {fg_url}")
    if not output_dir:
        output_dir = mlb_data.get("wrc_output_dir", "data/baseball/mlb/raw")
    os.makedirs(output_dir, exist_ok=True)
    if not date:
        date = datetime.today().strftime("%Y-%m-%d")
    logging.info(f"Fetching wRC+ CSV for date {date} from {fg_url}")
    params = {
        "splitArr": "44",
        "statType": "team",
        "statgroup": "2",
        "startDate": date,
        "endDate": date,
        "position": "B",
        "sort": "23,1",
        "csv": "1"
    }
    try:
        resp = requests.get(fg_url, params=params)
        resp.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to fetch wRC+ CSV: {e}")
        raise

    content_type = resp.headers.get('Content-Type', '')
    logging.info(f"Response status: {resp.status_code}, Content-Type: {content_type}")
    if 'text/csv' not in content_type:
        error_path = os.path.join(output_dir, f"wrc_plus_{date}_error.html")
        with open(error_path, "wb") as f:
            f.write(resp.content)
        logging.error(f"Response is not CSV. Saved error response to {error_path}")
        print(f"ERROR: Response is not CSV. See {error_path}")
        raise ValueError(f"Expected CSV, got {content_type}. Status: {resp.status_code}")

    path = os.path.join(output_dir, f"wrc_plus_{date}.csv")
    with open(path, "wb") as f:
        f.write(resp.content)
    logging.info(f"Saved wRC+ CSV to {path}")
    print(f"Saved wRC+ CSV to {path}")
    return path


def main():
    """
    Command-line entry point for fetching wRC+ CSV.
    Usage:
        python fetch_wrc_teams_daily.py --output_dir <dir> --date <YYYY-MM-DD> --fg_url <url>
    """
    import argparse
    parser = argparse.ArgumentParser(description="Fetch wRC+ CSV from Fangraphs")
    parser.add_argument("--output_dir", type=str, default=None, help="Output directory for CSV")
    parser.add_argument("--date", type=str, default=None, help="Date in YYYY-MM-DD format")
    parser.add_argument("--fg_url", type=str, default=None, help="Fangraphs URL")
    args = parser.parse_args()
    logging.info(f"Running main with args: {args}")
    fetch_wrc_plus(output_dir=args.output_dir, date=args.date, fg_url=args.fg_url)


# Pytest hook for automated testing
def test_fetch_wrc_plus(tmp_path):
    """
    Pytest hook: fetches wRC+ CSV for a test date and checks file creation.
    """
    test_date = "2025-07-24"
    path = fetch_wrc_plus(output_dir=tmp_path, date=test_date)
    assert os.path.exists(path)
    assert path.endswith(f"wrc_plus_{test_date}.csv")

if __name__ == "__main__":
    main()
