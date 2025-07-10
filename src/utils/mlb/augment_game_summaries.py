#!/usr/bin/env python3
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


def main():
    parser = argparse.ArgumentParser(
        description="Augment MLB game summary JSONs with first-inning run data."
    )
    parser.add_argument(
        '-i', '--input-dir', default='.',
        help='Directory containing mlb_daily_game_summary_*.json files'
    )
    parser.add_argument(
        '-o', '--output-dir', default='.',
        help='Directory to output augmented JSON files'
    )
    args = parser.parse_args()
    augment_files(args.input_dir, args.output_dir)


if __name__ == '__main__':
    main()
