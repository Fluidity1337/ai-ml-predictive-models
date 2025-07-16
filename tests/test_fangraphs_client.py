from utils.fangraphs_client import FangraphsClient
import pytest
import requests


@pytest.mark.unit
@pytest.fixture(autouse=True)
def mock_requests(monkeypatch):
    class DummyResponse:
        def __init__(self, data):
            self._data = data

        def json(self):
            return self._data

        def raise_for_status(self):
            pass

    def fake_get(self, url, params=None):
        # stubbed response with required keys for both pitching and hitting
        return DummyResponse({'FIP': 3.14, 'xFIP': 2.71, 'wOBA': 0.320})
    monkeypatch.setattr(requests.Session, 'get', fake_get)


@pytest.fixture
def client():
    return FangraphsClient(api_key="DUMMY")


@pytest.mark.parametrize(
    "player_id, player_name",
    [
        (11001, None),
        (None, "Aaron Judge"),
    ]
)
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


@pytest.mark.parametrize(
    "player_id, player_name",
    [
        (11001, None),
        (None, "Aaron Judge"),
    ]
)
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
