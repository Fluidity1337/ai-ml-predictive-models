class SurfaceSkillFeature:
    def __init__(self, match_data, player_name, surface):
        self.match_data = match_data
        self.player = player_name
        self.surface = surface

    def surface_win_rate(self, lookback=18):
        df = self.match_data[
            (self.match_data['surface'] == self.surface) &
            (self.match_data['player'] == self.player)
        ].sort_values(by='date', ascending=False)

        last_matches = df.head(20)
        wins = last_matches[last_matches['result'] == 'W']
        opponent_strength = last_matches['opponent_rank'].apply(lambda x: 1 if x > 100 else 1.25)
        adj_win_rate = (len(wins) / len(last_matches)) * opponent_strength.mean()
        return round(adj_win_rate, 3)

    def recent_surface_form(self):
        df = self.match_data[
            (self.match_data['surface'] == self.surface) &
            (self.match_data['player'] == self.player)
        ].sort_values(by='date', ascending=False)

        weights = [0.5, 0.3, 0.2]
        form_scores = []

        for i, weight in enumerate(weights):
            try:
                result = df.iloc[i]['result']
                form_scores.append(weight * (1 if result == 'W' else 0))
            except IndexError:
                form_scores.append(0)

        return round(sum(form_scores), 3)

    def get_features(self):
        return {
            f"{self.player}_{self.surface}_adj_win_rate": self.surface_win_rate(),
            f"{self.player}_{self.surface}_form_score": self.recent_surface_form()
        }
