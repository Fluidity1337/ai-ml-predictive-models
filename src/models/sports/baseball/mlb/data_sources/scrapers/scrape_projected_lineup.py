import requests
from bs4 import BeautifulSoup  # pip install beautifulsoup4

def scrape_projected_lineup(home_team, away_team):
    # e.g. https://www.mlb.com/preview/nyy-at-bos
    url = f"https://www.mlb.com/preview/{away_team}-at-{home_team}"
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    result = {}
    for side, cls in [("away", "preview__away-side"), ("home", "preview__home-side")]:
        table = soup.select_one(f".{cls} .preview-lineup-table")
        rows = table.select("tbody tr")[:3]
        batters = []
        for row in rows:
            cells = row.select("td")
            order = cells[0].text.strip().rstrip(".")
            name = cells[1].text.strip()
            pos = cells[2].text.strip()
            batters.append({"order": order, "name": name, "position": pos})
        result[side] = batters
    return result

if __name__ == "__main__":
    lineup = scrape_projected_lineup("boston-red-sox", "new-york-yankees")
    print("Away:", lineup["away"])
    print("Home:", lineup["home"])
