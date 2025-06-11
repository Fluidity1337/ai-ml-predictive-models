| Feature                    | Description                                                 | Weight (initial guess) |
| -------------------------- | ----------------------------------------------------------- | ---------------------- |
| Elo Rating Differential    | Adjusted for surface-specific Elo                           | 0.30                   |
| Surface Skill Score        | Historical win rate on current surface                      | 0.15                   |
| Recent Form Index          | Weighted result of last 5–8 matches (W/L, margin, opponent) | 0.10                   |
| Overusage/Fatigue Factor   | Penalizes if >6 matches in 10–15 days incl. doubles         | -0.10                  |
| Head-to-Head History       | Weighted by recency and surface type                        | 0.10                   |
| Motivation / Ranking Gain  | Captures incentives, eg. defending points, home crowd       | 0.05                   |
| Travel & Time Zone Offset  | Penalizes travel/time zone jumps over past 7 days           | -0.05                  |
| Quality of Wins            | Based on defeated opponent strength                         | 0.10                   |
| Market Line Movement       | Captures sharp early movement vs opener                     | 0.10                   |
| Injury / Retirement Signal | Binary/soft factor based on DNF patterns or known issues    | -0.05                  |
