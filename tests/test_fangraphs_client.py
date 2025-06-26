from fangraphs_client import FangraphsClient
import pytest
import os
import sys
# ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))


@pytest.fixture
def client():
    return FangraphsClient(api_key="DUMMY")


@pytest.mark.parametrize("player_id, player_name", [
    (11001, None),        # Example FG ID (Aaron Judge)
    (None, "Aaron Judge"),
])
def test_get_player_stats_pitching(client, player_id, player_name):
    data = client.get_player_stats(
        player_id=player_id,
        player_name=player_name,
        stat_type='pitching',
        season=2025
    )
    assert isinstance(data, dict)
    keys = {k.lower() for k in data.keys()}
    assert 'fip' in keys
    assert 'xfip' in keys


@pytest.mark.parametrize("player_id, player_name", [
    (11001, None),
    (None, "Aaron Judge"),
])
def test_get_player_stats_hitting(client, player_id, player_name):
    data = client.get_player_stats(
        player_id=player_id,
        player_name=player_name,
        stat_type='hitting',
        season=2025
    )
    assert isinstance(data, dict)
    keys = {k.lower() for k in data.keys()}
    assert 'woba' in keys
