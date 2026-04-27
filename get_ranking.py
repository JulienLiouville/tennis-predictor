import requests
from bs4 import BeautifulSoup
from database import get_connection
import urllib3
import re
import time
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RankingCollector:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def clean_and_format_name(self, name):
        name = re.sub(r'\(.*?\)', '', name).strip()
        return name

    def scrape_rankings(self, gender_url, gender_label, limit=1500):
        pages = limit // 50
        all_players = []
        gender = 'M' if gender_url == 'atp-men' else 'F'  # FIX: 'women' contient 'men'

        print(f"📊 Extraction du classement {gender_label} (Top {limit})...")

        for page in range(1, pages + 1):
            url = f"https://www.tennisexplorer.com/ranking/{gender_url}/?page={page}"
            try:
                res = requests.get(url, headers=self.headers, verify=False, timeout=10)
                soup = BeautifulSoup(res.text, 'html.parser')
                rows = soup.select('table.result tbody.flags tr')

                if not rows:
                    print(f"⚠️  Fin des données à la page {page}")
                    break

                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 5:
                        rank = cells[0].get_text(strip=True).replace('.', '')
                        name_raw = cells[2].get_text(strip=True)
                        name = self.clean_and_format_name(name_raw)
                        country = cells[3].get_text(strip=True)
                        points = cells[4].get_text(strip=True)

                        all_players.append({
                            'rank': int(rank),
                            'name': name,
                            'country': country,
                            'points': int(points),
                            'gender': gender,
                        })

                print(f"  ✅ Page {page} traitée ({len(rows)} joueurs)")
                time.sleep(1.5)

            except Exception as e:
                print(f"  ❌ Erreur page {page}: {e}")
                break

        return all_players

    def save_to_db(self, players):
        if not players:
            return

        conn = get_connection()
        c = conn.cursor()

        c.execute('''CREATE TABLE IF NOT EXISTS players_rankings (
                        name TEXT,
                        rank INTEGER,
                        points INTEGER,
                        country TEXT,
                        gender TEXT,
                        date_recorded DATE,
                        PRIMARY KEY (name, gender, date_recorded))''')

        ranking_date = datetime.now().strftime('%Y-%m-%d')  # FIX: date dynamique

        for p in players:
            c.execute('''INSERT OR REPLACE INTO players_rankings 
                         (name, rank, points, country, gender, date_recorded)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (p['name'], p['rank'], p['points'], p['country'], p['gender'], ranking_date))

        conn.commit()
        conn.close()
        print(f"💾 {len(players)} joueurs enregistrés en base (date: {ranking_date}).")


if __name__ == "__main__":
    collector = RankingCollector()

    atp = collector.scrape_rankings('atp-men', 'ATP')
    collector.save_to_db(atp)

    wta = collector.scrape_rankings('wta-women', 'WTA')
    collector.save_to_db(wta)