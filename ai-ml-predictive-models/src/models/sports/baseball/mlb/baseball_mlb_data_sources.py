# Directory Structure for Modular MLB RFI/NRFI Model

# 1. baseball_mlb_data_sources.py
# Responsible for fetching raw data from APIs

def fetch_mlb_schedule(date=None):
    # Hit MLB schedule API
    pass

def fetch_mlb_probable_pitchers(date=None):
    # Hit MLB probable pitchers endpoint
    pass

def fetch_mlb_pitcher_stats(player_id, year, last_n=3):
    # StatsAPI or wrapper for pitcher logs
    pass

def fetch_mlb_batter_stats(team_id, pitcher_hand):
    # StatsAPI for batter splits
    pass

# 2. schema.py
# Defines expected data structure for consistency

pitcher_schema = {
    'player_id': str,
    'name': str,
    'team': str,
    'IP': float,
    'H': int,
    'BB': int,
    'K': int,
    'ERA': float,
    'WHIP': float,
    'games': list
}

batter_schema = {
    'player_id': str,
    'name': str,
    'AVG_1st_inning': float,
    'OBP_1st_inning': float,
    'SLG_1st_inning': float,
    'recent_OBP': float
}

# 3. features.py
# Transforms raw data into model features

def compute_pitcher_features(pitcher_data):
    # Combine WHIP, ERA, BB/9, etc. with weights
    pass

def compute_batter_features(batter_data):
    # Aggregate 1st inning metrics, splits vs RHP/LHP
    pass

def aggregate_matchup_features(pitcher, batters):
    # Combine for RFI prediction
    pass

# 4. pipeline.py
# Orchestrates full process

def run_mlb_pipeline(game_date):
    schedule = fetch_mlb_schedule(game_date)
    for game in schedule:
        pitchers = fetch_mlb_probable_pitchers(game_date)
        for pitcher in pitchers:
            pitcher_data = fetch_mlb_pitcher_stats(pitcher['id'])
            features = compute_pitcher_features(pitcher_data)
            # fetch and compute batter stats
            # aggregate and generate prediction
            pass

    # Output final structured results as JSON or CSV
    pass
