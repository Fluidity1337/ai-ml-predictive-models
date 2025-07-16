+------------------+       +------------------+       +-----------------+
|  Pull Schedule   |----->| Get Starting SPs  |-----> | Fetch Lineups    |
|  (Game Day List) |       | (Probable Pitchers)|     | (From MLB API)   |
+------------------+       +------------------+       +-----------------+
                                                          |
                                                          v
                             +---------------------------------------------------+
                             |              Pull Pitcher Stats (MLB Stats API)  |
                             |       - Last 3 starts (weighted)                  |
                             |       - WHIP, ERA, K/BB, IP                       |
                             +---------------------------------------------------+
                                                          |
                                                          v
                             +---------------------------------------------------+
                             |           Pull Batter Stats vs SPs               |
                             |     - 1st Inning AVG, OBP, SLG                   |
                             |     - vs RHP/LHP, Recent Form                    |
                             +---------------------------------------------------+
                                                          |
                                                          v
                             +---------------------------------------------------+
                             |           Aggregate Rating & Confidence          |
                             |   - Calculate NRFI & YRFI Probability            |
                             |   - Adjust for Ballpark, Weather, Day of Week   |
                             +---------------------------------------------------+
                                                          |
                                                          v
                             +---------------------------+
                             |     Make Recommendation   |
                             |  ✅ NRFI or ✅ YRFI         |
                             +---------------------------+