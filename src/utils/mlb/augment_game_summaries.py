"""
Augment MLB game summary JSONs with first-inning run data, filtered by date range or season.

REQUIRED:
  -i, --input-dir   Directory containing input JSON files.
  -d, --output-dir  Directory to output augmented JSON files.

OPTIONAL:
  -p, --pattern     Filename pattern to match (default: mlb_daily_game_summary_*.json)
  --start-date      Start date (YYYYMMDD) to process (inclusive)
  --end-date        End date (YYYYMMDD) to process (inclusive)
  --season          Season year (YYYY) to process (e.g., 2025)
  --force           Overwrite existing augmented files
  --example         Show usage examples and exit.

USAGE EXAMPLES:
  # Augment a single date
  python -m src.utils.mlb.augment_game_summaries -i data/baseball/mlb/raw -d data/baseball/mlb/interim/game_summaries --start-date 20250724 --end-date 20250724

  # Augment a date range
  python -m src.utils.mlb.augment_game_summaries -i data/baseball/mlb/raw -d data/baseball/mlb/interim/game_summaries --start-date 20250720 --end-date 20250725

  # Augment all files for a season, overwriting existing
  python -m src.utils.mlb.augment_game_summaries -i data/baseball/mlb/raw -d data/baseball/mlb/interim/game_summaries --season 2025 --force

NOTES:
- This script is designed for file-based workflows but is structured to allow future scaling to database (DB) backends.
- To support DB, refactor augment_game_summaries and output logic to use DB queries/inserts instead of file I/O.
"""

import os
import json
import argparse
import requests

def augment_game_summaries(input_dir, output_dir):
    # Find JSON files in the specified input directory
    json_files = [f for f in os.listdir(input_dir)
                  if f.startswith('mlb_daily_game_summary_') and f.endswith('.json')]
    if not json_files:
        print(f"No JSON files found in {input_dir}")
        return


    total_games = 0
    games_with_first_run = 0

    for filename in json_files:
        input_path = os.path.join(input_dir, filename)
        with open(input_path, 'r') as fp:
            games = json.load(fp)

        for game in games:
            total_games += 1
            # Support common key names for the game ID
            game_id = game.get('game_id') or game.get(
                'gamePk') or game.get('game_pk')
            if not game_id:
                print(f"Skipping entry without game_id in {filename}")
                continue

            # Fetch the linescore for the game
            url = f'https://statsapi.mlb.com/api/v1/game/{game_id}/linescore'
            resp = requests.get(url)
            resp.raise_for_status()
            data = resp.json()

            innings = data.get('innings', [])
            first_inning = next(
                (inn for inn in innings if inn.get('num') == 1), None)
            away_runs = first_inning['away'].get(
                'runs', 0) if first_inning else 0
            home_runs = first_inning['home'].get(
                'runs', 0) if first_inning else 0

            # Augment the game dict
            game['first_inning_away_runs'] = away_runs
            game['first_inning_home_runs'] = home_runs
            game['first_inning_score'] = f"{away_runs}-{home_runs}"
            game['first_inning_run'] = (away_runs + home_runs) > 0

            if game['first_inning_run']:
                games_with_first_run += 1

        # Write augmented JSON
        output_filename = filename.replace('.json', '_augmented.json')
        output_path = os.path.join(output_dir, output_filename)
        with open(output_path, 'w') as fp:
            json.dump(games, fp, indent=2)

        print(f"Processed {filename} -> {output_filename}")

    # Summary
    if total_games > 0:
        pct = games_with_first_run / total_games * 100
        print(
            f"\nFirst-inning runs in {games_with_first_run}/{total_games} games ({pct:.1f}% ran)")
    else:
        print("No games processed.")

def parse_date_from_filename(filename):
    # Expects format: mlb_daily_game_summary_YYYYMMDD.json
    try:
        parts = filename.split('_')
        date_part = parts[-1].replace('.json', '')
        if len(date_part) == 8 and date_part.isdigit():
            return date_part
    except Exception:
        pass
    return None

def augment_game_summaries(input_dir, output_dir, start_date=None, end_date=None, season=None, force=False):
    """
    Augment MLB game summary JSONs with first-inning run data, filtered by date range or season.
    Only processes files for the specified date(s) or season. Skips files if augmented output exists unless force=True.

    Args:
        input_dir (str): Directory containing mlb_daily_game_summary_*.json files.
        output_dir (str): Directory to output augmented JSON files.
        start_date (str): Start date (YYYYMMDD) to process (inclusive).
        end_date (str): End date (YYYYMMDD) to process (inclusive).
        season (str): Season year (YYYY) to process (e.g., 2025).
        force (bool): Overwrite existing augmented files if True.

    Usage examples:
        # Augment a single date
        python augment_game_summaries.py -i data/baseball/mlb/raw -o data/baseball/mlb/interim/game_summaries --start-date 20250724 --end-date 20250724

        # Augment a date range
        python augment_game_summaries.py -i data/baseball/mlb/raw -o data/baseball/mlb/interim/game_summaries --start-date 20250720 --end-date 20250725

        # Augment all files for a season, overwriting existing
        python augment_game_summaries.py -i data/baseball/mlb/raw -o data/baseball/mlb/interim/game_summaries --season 2025 --force
    """
    # Find JSON files in the specified input directory
    json_files = [f for f in os.listdir(input_dir)
                  if f.startswith('mlb_daily_game_summary_') and f.endswith('.json')]
    if not json_files:
        print(f"No JSON files found in {input_dir}")
        return

    # Filter files by date range or season
    filtered_files = []
    for f in json_files:
        file_date = parse_date_from_filename(f)
        if file_date:
            if season and not file_date.startswith(str(season)):
                continue
            if start_date and file_date < start_date:
                continue
            if end_date and file_date > end_date:
                continue
        filtered_files.append(f)

    if not filtered_files:
        print("No files match the specified date range or season.")
        return

    total_games = 0
    games_with_first_run = 0

    for filename in filtered_files:
        input_path = os.path.join(input_dir, filename)
        output_filename = filename.replace('.json', '_augmented.json')
        output_path = os.path.join(output_dir, output_filename)

        if os.path.exists(output_path) and not force:
            print(f"[SKIP] {output_filename} already exists. Use --force to overwrite.")
            continue

        with open(input_path, 'r') as fp:
            games = json.load(fp)

        for game in games:
            total_games += 1
            # Support common key names for the game ID
            game_id = game.get('game_id') or game.get('gamePk') or game.get('game_pk')
            if not game_id:
                print(f"Skipping entry without game_id in {filename}")
                continue

            # Fetch the linescore for the game
            url = f'https://statsapi.mlb.com/api/v1/game/{game_id}/linescore'
            resp = requests.get(url)
            resp.raise_for_status()
            data = resp.json()

            innings = data.get('innings', [])
            first_inning = next((inn for inn in innings if inn.get('num') == 1), None)
            away_runs = first_inning['away'].get('runs', 0) if first_inning else 0
            home_runs = first_inning['home'].get('runs', 0) if first_inning else 0

            # Augment the game dict
            game['first_inning_away_runs'] = away_runs
            game['first_inning_home_runs'] = home_runs
            game['first_inning_score'] = f"{away_runs}-{home_runs}"
            game['first_inning_run'] = (away_runs + home_runs) > 0

            if game['first_inning_run']:
                games_with_first_run += 1

        # Write augmented JSON
        with open(output_path, 'w') as fp:
            json.dump(games, fp, indent=2)
        print(f"Processed {filename} -> {output_filename}")

    # Summary
    if total_games > 0:
        pct = games_with_first_run / total_games * 100
        print(f"\nFirst-inning runs in {games_with_first_run}/{total_games} games ({pct:.1f}% ran)")
    else:
        print("No games processed.")


def main():
    parser = argparse.ArgumentParser(
        description="Augment MLB game summary JSONs with first-inning run data.\n\nREQUIRED:\n  -i, --input-dir   Directory containing input JSON files.\n  -d, --output-dir  Directory to output augmented JSON files.\n\nOPTIONAL:\n  -p, --pattern     Filename pattern to match (default: mlb_daily_game_summary_*.json)\n  --start-date      Start date (YYYYMMDD) to process (inclusive)\n  --end-date        End date (YYYYMMDD) to process (inclusive)\n  --season          Season year (YYYY) to process (e.g., 2025)\n  --force           Overwrite existing augmented files\n  --example         Show usage examples and exit.\n"
    )
    parser.add_argument('-i', '--input-dir', required=True, help='[REQUIRED] Directory containing input JSON files')
    parser.add_argument('-d', '--output-dir', required=True, help='[REQUIRED] Directory to output augmented JSON files')
    parser.add_argument('-p', '--pattern', default='mlb_daily_game_summary_*.json', help='Filename pattern to match (default: mlb_daily_game_summary_*.json)')
    parser.add_argument('--start-date', type=str, default=None, help='Start date (YYYYMMDD) to process (inclusive)')
    parser.add_argument('--end-date', type=str, default=None, help='End date (YYYYMMDD) to process (inclusive)')
    parser.add_argument('--season', type=str, default=None, help='Season year (YYYY) to process (e.g., 2025)')
    parser.add_argument('--force', action='store_true', help='Overwrite existing augmented files')
    parser.add_argument('--example', action='store_true', help='Show usage examples and exit.')
    args = parser.parse_args()
    if args.example:
        print("""
USAGE EXAMPLES:
  # Augment a single date
  python -m src.utils.mlb.augment_game_summaries -i data/baseball/mlb/raw -d data/baseball/mlb/interim/game_summaries --start-date 20250724 --end-date 20250724

  # Augment a date range
  python -m src.utils.mlb.augment_game_summaries -i data/baseball/mlb/raw -d data/baseball/mlb/interim/game_summaries --start-date 20250720 --end-date 20250725

  # Augment all files for a season, overwriting existing
  python -m src.utils.mlb.augment_game_summaries -i data/baseball/mlb/raw -d data/baseball/mlb/interim/game_summaries --season 2025 --force
        """)
        return
    # Validate required args
    if not args.input_dir or not args.output_dir:
        parser.error('Both -i/--input-dir and -d/--output-dir are required.')
    augment_game_summaries(
        args.input_dir,
        args.output_dir,
        start_date=args.start_date,
        end_date=args.end_date,
        season=args.season,
        force=args.force
    )


if __name__ == '__main__':
    main()
