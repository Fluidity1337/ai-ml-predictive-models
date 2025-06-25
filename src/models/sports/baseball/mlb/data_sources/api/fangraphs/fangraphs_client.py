import requests
from typing import List, Dict, Optional


class FanGraphsClient:
    """
    Fetches FanGraphs pitching leaderboards (advanced stats, including xFIP)
    and allows lookup of a pitcher’s xFIP by name.
    """
    FG_ENDPOINT = "https://www.fangraphs.com/api/leaders/major-league/data"

    def __init__(self, session: Optional[requests.Session] = None):
        # Allows injection of a custom session for testing
        self.session = session or requests.Session()

    def fetch_leaderboard(self, season: int) -> List[Dict]:
        """
        Returns the 'advanced' (type=8) pitching leaderboard for the given season.
        Each row is a dict, with 'Name' and 'xFIP' among its keys.
        """
        params = {
            "pos":       "all",
            "stats":     "pit",
            "lg":        "all",
            "type":      "8",        # advanced metrics
            "qual":      "0",        # no min innings
            "season":    str(season),
            "season1":   str(season),
            "month":     "0",
            "pageitems": "500000"
        }
        resp = self.session.get(self.FG_ENDPOINT, params=params)
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("data", [])
        # convert xFIP from string to float
        for r in rows:
            xfip = r.get("xFIP")
            try:
                r["xFIP"] = float(xfip) if xfip is not None else None
            except (ValueError, TypeError):
                r["xFIP"] = None
        return rows

    def get_xfip_by_name(self, name: str, season: int) -> Optional[float]:
        """
        Lookup a pitcher’s xFIP by exact name match.
        Returns the float xFIP or None if not found.
        """
        rows = self.fetch_leaderboard(season)
        for r in rows:
            if r.get("Name") == name:
                return r.get("xFIP")
        return None
