import pytest
import requests
from utils.fangraphs_client import FanGraphsClient


class DummyResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code != 200:
            raise requests.HTTPError(f"Status {self.status_code}")


@pytest.fixture
def sample_payload():
    return {
        "data": [
            {"Name": "Alice Ace",   "xFIP": "3.21", "Other": "foo"},
            {"Name": "Bob Bomber",  "xFIP": "4.56", "Other": "bar"},
        ]
    }


def test_fetch_leaderboard_parses_xfip(monkeypatch, sample_payload):
    client = FanGraphsClient(session=requests.Session())
    # stub out session.get to return our dummy payload

    def fake_get(url, params):
        assert "leaders/major-league/data" in url
        # verify we passed the correct season param
        assert params["season"] == "2025"
        return DummyResponse(sample_payload, status_code=200)

    monkeypatch.setattr(client.session, "get", fake_get)

    rows = client.fetch_leaderboard(2025)
    assert isinstance(rows, list)
    assert rows[0]["Name"] == "Alice Ace"
    assert isinstance(rows[0]["xFIP"], float)
    assert rows[0]["xFIP"] == pytest.approx(3.21)
    assert rows[1]["xFIP"] == pytest.approx(4.56)


def test_get_xfip_by_name_found(monkeypatch):
    client = FanGraphsClient()
    dummy_rows = [
        {"Name": "Charlie Closer", "xFIP": 2.34},
        {"Name": "Dana Duster",   "xFIP": 3.45},
    ]
    monkeypatch.setattr(client, "fetch_leaderboard", lambda season: dummy_rows)

    xfip = client.get_xfip_by_name("Dana Duster", 2025)
    assert xfip == pytest.approx(3.45)


def test_get_xfip_by_name_not_found(monkeypatch):
    client = FanGraphsClient()
    dummy_rows = [
        {"Name": "Evan Extra", "xFIP": 4.00},
    ]
    monkeypatch.setattr(client, "fetch_leaderboard", lambda season: dummy_rows)

    xfip = client.get_xfip_by_name("Nonexistent Pitcher", 2025)
    assert xfip is None


def test_fetch_leaderboard_http_error(monkeypatch):
    client = FanGraphsClient(session=requests.Session())

    def fake_get(url, params):
        return DummyResponse({}, status_code=500)
    monkeypatch.setattr(client.session, "get", fake_get)

    with pytest.raises(requests.HTTPError):
        client.fetch_leaderboard(2025)
