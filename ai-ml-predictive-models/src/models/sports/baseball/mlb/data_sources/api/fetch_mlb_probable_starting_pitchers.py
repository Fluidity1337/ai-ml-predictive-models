import sys
from pathlib import Path

# Dynamically add project root to sys.path
current_file = Path(__file__).resolve()
project_root = current_file
while project_root.name != "src":
    project_root = project_root.parent
sys.path.append(str(project_root))

from models.sports.baseball.schema import Game, PitcherStats


def fetch_probable_pitchers(schedule: list[Game], game_date: date) -> dict[str, PitcherStats]:
    """
    Given a list of scheduled games, fetch probable pitchers with stats for each.
    """
    print(f"Fetching probable pitchers for {game_date}...")
    game_date_str = game_date.strftime("%Y-%m-%d")

    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={game_date_str}&hydrate=probablePitcher(note,stats)"
    headers = {"User-Agent": "Mozilla/5.0"}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error fetching data: {response.status_code}")

    data = response.json()
    probable_pitchers = {}

    for date_info in data.get("dates", []):
        for game in date_info.get("games", []):
            for side in ["home", "away"]:
                team_info = game.get(side, {})
                pitcher_info = team_info.get("probablePitcher", {})

                if pitcher_info:
                    name = pitcher_info.get("fullName")
                    player_id = pitcher_info.get("id")
                    team = team_info.get("team", {}).get("name")

                    probable_pitchers[name] = PitcherStats(
                        player_id=player_id,
                        name=name,
                        team=team,
                        last_3_game_stats=None,  # to be filled in next step
                        game_id=game.get("gamePk")
                    )

    return probable_pitchers

# Example usage
if __name__ == "__main__":
    dummy_schedule = []  # You'd pass in your list of Game objects
    result = fetch_probable_pitchers(dummy_schedule, date.today())
    for name, stats in result.items():
        print(f"{name} ({stats.team}) — ID: {stats.player_id}")
