from utils.fangraphs_client import FangraphsClient

# 1) Instantiate the client (pass your real API key if you have one)
client = FangraphsClient(api_key=None)

# 2) Pick a FanGraphs player ID (e.g. 11001 for Aaron Judge)
fg_id = 11001

# 3) Call the pitching or hitting endpoint
#    — for pitching stats (FIP, xFIP, etc.):
pitching_stats = client.get_player_stats(
    player_id=fg_id,
    stat_type='pitching',
    season=2025
)
print("Pitching stats:", pitching_stats)

#    — for hitting stats (wOBA, wRC+, etc.):
hitting_stats = client.get_player_stats(
    player_id=fg_id,
    stat_type='hitting',
    season=2025
)
print("Hitting stats:", hitting_stats)
