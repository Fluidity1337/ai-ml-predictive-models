# tennis_model_features.py

from typing import Dict, List

# Raw candidate features to derive and evaluate during backtest or model fitting
CANDIDATE_FEATURES: List[str] = [
    "overusage_flag",
    "days_rest_since_last_match",
    "avg_opponent_ranking_last_5",
    "win_quality_last_5",
    "average_games_played_last_5",
    "tiebreak_rate",
    "first_set_win_rate",
    "weather_condition_effect",
    "motivation_score",
    "pre_match_sentiment_score",
    "serve_quality",
    "return_quality",
    "injury_flag",
    "line_movement",
    "odds_implied_prob",
    "model_predicted_prob"
]

# Feature engineering map for where features come from (or how derived)
FEATURE_SOURCE_MAP: Dict[str, str] = {
    "surface": "ATP/WTA API or Tennis Abstract",
    "match_format": "ATP/WTA API",
    "ranking_diff": "ATP/WTA API",
    "h2h_record": "Tennis Abstract",
    "recent_win_pct": "ATP/WTA match history",
    "serve_quality": "Tennis Abstract or Elo Serve",
    "return_quality": "Tennis Abstract or Elo Return",
    "fatigue_index": "Calculated from recent matches (\u226410 days)",
    "injury_flag": "Manually flagged / LWOS",
    "line_movement": "Scraped sportsbook (BetOnline/Pinnacle)",
    "odds_implied_prob": "Converted from live odds",
    "model_predicted_prob": "Model-generated",
    "days_rest_since_last_match": "ATP/WTA match calendar",
    "tiebreak_rate": "ATP/WTA stats",
    "motivation_score": "Sentiment/NLP",
    "win_quality_last_5": "Weighted avg Elo or rank of defeated opponents"
}
