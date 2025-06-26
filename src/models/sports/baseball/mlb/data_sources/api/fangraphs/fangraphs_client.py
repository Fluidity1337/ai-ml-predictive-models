import requests


class FangraphsClient:
    BASE_URL = "https://api.fangraphs.com"

    def __init__(self, api_key: str = None):
        """
        Initialize the FangraphsClient.
        :param api_key: Optional API key for authenticated endpoints.
        """
        self.session = requests.Session()
        if api_key:
            # If FG supports bearer tokens, include here
            self.session.headers.update({'Authorization': f"Bearer {api_key}"})

    def get_player_stats(self,
                         player_id: int = None,
                         player_name: str = None,
                         stat_type: str = 'pitching',
                         season: int = None) -> dict:
        """
        Fetch player stats by Fangraphs ID or fallback to name.
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

    # Additional helper methods can be added here (e.g., caching, rate limiting)
