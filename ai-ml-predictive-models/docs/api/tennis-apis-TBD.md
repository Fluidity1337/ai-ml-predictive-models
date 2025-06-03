# Data Sources for MLB Model

This document outlines the APIs and data sources used for collecting data in the MLB NRFI/YRFI predictive model.

| Task                              | API/Source                  |
|-----------------------------------|-----------------------------|
| Get all games for tomorrow        | `statsapi.mlb.com`          |
| Get probable pitchers             | `statsapi.mlb.com`          |
| Get pitcher WHIP/HR/9             | `statsapi.mlb.com logs`     |
| Get team NRFI/YRFI rates          | **TeamRankings (scrape)**  |
| Get odds                          | **TheOddsAPI (optional)**  |
| Add deeper stats (e.g. xERA)      | `Baseball Savant`           |
