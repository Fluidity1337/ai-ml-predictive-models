# MLB RFI Model Features

This document outlines the feature set, descriptions, and initial weights for predicting the likelihood of a run in the first inning of an MLB game.

| Feature                                   | Description                                                                            | Weight |
|-------------------------------------------|----------------------------------------------------------------------------------------|-------:|
| First-Inning xFIP                         | Pitcher’s xFIP limited to first-inning exposure (accounts for FB/HR rate, FIP skills) |   0.25 |
| Starting Pitcher First-Frame Barrel %     | Rate at which the SP allows “barreled” contact in their first inning                  |   0.15 |
| Lineup 1–3 wOBA (last 7 days)             | Weighted on-base average of your top 3 hitters over their most recent week            |   0.20 |
| Team First-Inning Run Frequency (L30)     | % of games in last 30 where the team scored in the 1st inning                         |   0.20 |
| Park-Adjusted Run Factor                  | Ballpark’s run environment multiplier for early innings (first 3 outs)                |   0.10 |
| Weather Wind Impact Score                 | Quantifies wind direction/speed’s effect on run scoring in the first inning           |   0.10 |

---

## Rationale

1. **Focus on first-inning splits**  
   We narrowed pitcher stats (xFIP and Barrel %) to their first-inning performance so they directly target “start of game” risk.

2. **Lineup recency vs. longevity**  
   A rolling 7-day wOBA for slots 1–3 captures hot/cold streaks more sharply than a broad multi-month average.

3. **Team‐level propensity**  
   Historical first-inning run frequency gives a baseline expectation independent of SP.

4. **Contextual factors**  
   Park factors and weather can swing early-inning run probabilities, so they each get a non-negligible (~10%) weight.

