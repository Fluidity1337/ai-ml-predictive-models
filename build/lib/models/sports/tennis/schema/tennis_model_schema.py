# schema.py

from dataclasses import dataclass
from typing import Optional

@dataclass
class MatchFeatures:
    player_name: str
    opponent_name: str
    surface: str
    match_format: str  # e.g. "Bo3" or "Bo5"
    ranking_diff: Optional[float]
    elo_diff: Optional[float]
    surface_win_diff: Optional[float]
    recent_form_diff: Optional[float]
    fatigue_index_diff: Optional[float]
    h2h_win_pct: Optional[float]
    win_quality_last_5: Optional[float]
    average_games_played_last_5: Optional[float]
    serve_quality: Optional[float]
    return_quality: Optional[float]
    tiebreak_rate: Optional[float]
    first_set_win_rate: Optional[float]
    injury_flag: Optional[bool]
    weather_condition_effect: Optional[float]
    motivation_score: Optional[float]
    line_movement: Optional[float]
    odds_implied_prob: Optional[float]
    model_predicted_prob: Optional[float]
