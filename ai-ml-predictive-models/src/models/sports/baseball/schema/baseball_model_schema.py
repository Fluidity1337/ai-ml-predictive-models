# baseball_model_schema.py

from typing import TypedDict, List, Optional

class PitcherStats(TypedDict):
    player_id: str
    name: str
    team: str
    handedness: str  # 'R' or 'L'
    date: str
    ip: float
    h: int
    bb: int
    k: int
    er: int
    whip: Optional[float]
    era: Optional[float]
    k_per_bb: Optional[float]
    game_score: Optional[int]

class BatterStats(TypedDict):
    player_id: str
    name: str
    team: str
    handedness: str
    position: str
    avg_1st_inning: Optional[float]
    obp_1st_inning: Optional[float]
    slg_1st_inning: Optional[float]
    vs_rhp_avg: Optional[float]
    vs_lhp_avg: Optional[float]
    recent_avg: Optional[float]  # last 5-10 games

class GameInfo(TypedDict):
    game_id: int
    start_time: str
    home_team: str
    away_team: str
    home_pitcher: Optional[str]  # player_id
    away_pitcher: Optional[str]  # player_id
