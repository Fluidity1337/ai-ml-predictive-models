from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd

# Start Chrome browser
driver = webdriver.Chrome()

url = "https://www.baseball-reference.com/players/gl.fcgi?id=verlaju01&t=p&year=2025"
driver.get(url)

# Wait until table is loaded
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.ID, "pitching_gamelogs"))
)

# Parse HTML
html = driver.page_source
soup = BeautifulSoup(html, "html.parser")

table = soup.find("table", {"id": "pitching_gamelogs"})
if not table:
    raise Exception("Pitching game log table not found")

rows = table.find("tbody").find_all("tr", class_=lambda x: x != "thead")

games = []
for row in rows:
    cols = row.find_all("td")
    if not cols:
        continue
    try:
        ip = cols[6].text.strip()
        ip = float(ip) if '.' in ip else int(ip)
        h = int(cols[8].text.strip())
        bb = int(cols[11].text.strip())
    except (ValueError, IndexError):
        continue

    games.append({
        "Date": cols[0].text.strip(),
        "IP": ip,
        "H": h,
        "BB": bb
    })

df = pd.DataFrame(games)
print(df.head())

driver.quit()
