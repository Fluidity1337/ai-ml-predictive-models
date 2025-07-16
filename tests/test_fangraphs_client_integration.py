import socket
import pytest
from utils.fangraphs_client import FangraphsClient


@pytest.mark.integration
@pytest.mark.parametrize(
    "player_id, player_name",
    [
        (11001, None),        # Aaron Judge by FG ID
        (None, "Aaron Judge"),  # Aaron Judge by name
    ]
)
def test_get_player_stats_live(player_id, player_name):
    # 1) Bail out early if DNS fails (network offline or host unreachable)
    host = FangraphsClient.BASE_URL.replace("https://", "").split("/")[0]
    try:
        socket.gethostbyname(host)
    except socket.gaierror:
        pytest.skip(f"Cannot resolve {host}; skipping live integration test")

    # 2) Hit the real API
    client = FangraphsClient(api_key=None)  # or real key if needed
    data = client.get_player_stats(
        player_id=player_id,
        player_name=player_name,
        stat_type='pitching',
        season=2025
    )

    # 3) Assert you got back the fields you expect
    assert isinstance(data, dict)
    keys = {k.lower() for k in data.keys()}
    assert 'fip' in keys
    assert 'xfip' in keys
