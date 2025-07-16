# File: mlb_rfi/fangraphs_client.py
from utilities.fangraphs_client import FangraphsClient
import pytest
import requests


class FangraphsClient:
    BASE_URL = "https://api.fangraphs.com"

    def __init__(self, api_key: str = None):
        """
        Initialize the FangraphsClient.
        :param api_key: Optional API key for authenticated endpoints.
        """
        self.session = requests.Session()
        self.api_key = api_key
        if api_key:
            self.session.headers.update({'Authorization': f"Bearer {api_key}"})
        """
        Initialize the FangraphsClient.
        :param api_key: Optional API key for authenticated endpoints.
        """
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({'Authorization': f"Bearer {api_key}"})

    def get_player_stats(self,
                         player_id: int = None,
                         player_name: str = None,
                         stat_type: str = 'pitching',
                         season: int = None) -> dict:
        """
        Fetch player stats by FanGraphs ID or fallback to name.
        :param player_id: Numeric FanGraphs player ID.
        :param player_name: Full player name (fallback if ID not provided).
        :param stat_type: 'pitching' or 'hitting'.
        :param season: Optional season year.
        :return: Parsed JSON response as dict.
        """
        if player_id:
            params = {'playerid': player_id}
        elif player_name:
            params = {'playername': player_name}
        else:
            raise ValueError("Must provide player_id or player_name")

        if season:
            params['season'] = season

        url = f"{self.BASE_URL}/{stat_type}/stats"
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


# File: tests/test_fangraphs_client.py


@pytest.fixture
def client():
    # Initialize with dummy key or without
    return FangraphsClient(api_key="DUMMY")


@pytest.mark.parametrize(
    "player_id, player_name",
    [
        (11001, None),        # Example FG ID
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
