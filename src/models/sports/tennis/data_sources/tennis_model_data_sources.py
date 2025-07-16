# tennis_model_data_sources.py

from typing import Dict, List

# Catalog of available data sources, grouped by how reliable or accessible they are
data_sources: Dict[str, List[str]] = {
    "official": [
        "ATP/WTA Tour API",
        "Tennis Abstract (match history, Elo, surface splits)",
        "Flashscore (live scores, H2H, line movement)",
        "BetOnline, BetUS, Pinnacle (odds feed)",
        "Last Word on Sports (editorial previews)"
    ],
    "api_ready": [
        "SportRadar (premium tennis data feed)",
        "OddsAPI or TheOddsAPI (real-time odds integration)",
        "Tennis DataHub (point-by-point and match summaries)"
    ],
    "scraped": [
        "ATP/WTA match archives (via BeautifulSoup or Selenium)",
        "Last Word on Sports (keyword scan + sentiment)",
        "Live line movement (scraped from BetOnline/Pinnacle UI)"
    ]
}
