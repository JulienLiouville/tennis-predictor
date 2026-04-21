import requests
from bs4 import BeautifulSoup
from database import get_connection
import urllib3
from datetime import datetime, timedelta
import time

# Désactive les alertes SSL (le fameux fix pour ton erreur TLS)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class TennisCollector2026:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        # Dictionnaire étendu pour mapper les surfaces automatiquement
        self.surface_map = {
            'clay': 'Clay', 'terre': 'Clay', 'roland garros': 'Clay', 'madrid': 'Clay',
            'rome': 'Clay', 'monte carlo': 'Clay', 'barcelona': 'Clay', 'munich': 'Clay',
            'grass': 'Grass', 'wimbledon': 'Grass', 'stuttgart': 'Grass', 'mallorca': 'Grass', 'halle': 'Grass',
            'hard': 'Hard', 'australian open': 'Hard', 'us open': 'Hard', 'indian wells': 'Hard',
            'miami': 'Hard', 'gwangju': 'Hard', 'savannah': 'Clay', 'shenzhen': 'Hard'
        }

    def detect_surface(self, tournament_name):
        name_low = tournament_name.lower()
        for key, surface in self.surface_map.items():
            if key in name_low:
                return surface
        return "Unknown"

    def scrape_date(self, date_str):
        """ Scrape les résultats pour une date format YYYY-MM-DD """
        url = f"https://www.tennisexplorer.com/results/?date={date_str}"
        print(f"🌐 Récupération des données pour le {date_str}...")

        try:
            # verify=False est CRUCIAL pour ton erreur SSL
            response = requests.get(url, headers=self.headers, verify=False, timeout=15)
            if response.status_code != 200:
                print(f"❌ Erreur HTTP {response.status_code}")
                return 0

            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', class_='result')

            if not table:
                print(f"ℹ️ Aucun match trouvé pour cette date.")
                return 0

            conn = get_connection()
            c = conn.cursor()

            rows = table.find_all('tr')
            current_tournament = "Unknown"
            current_surface = "Unknown"
            added = 0

            i = 0
            while i < len(rows):
                row = rows[i]
                classes = row.get('class', [])

                # 1. Gestion des entêtes de tournois
                if 'head' in classes:
                    t_link = row.find('td', class_='t-name')
                    if t_link:
                        current_tournament = t_link.text.strip()
                        current_surface = self.detect_surface(current_tournament)
                    i += 1
                    continue

                # 2. Gestion des lignes de matchs
                row_id = row.get('id', '')
                # Si c'est une ligne de joueur (ID commence par 'r' et ne finit pas par 'b')
                if row_id.startswith('r') and not row_id.endswith('b'):
                    try:
                        # Ligne Joueur 1
                        p1_name = row.find('td', class_='t-name').text.strip()
                        p1_res = int(row.find('td', class_='result').text.strip())

                        # Ligne Joueur 2 (juste après)
                        next_row = rows[i + 1]
                        p2_name = next_row.find('td', class_='t-name').text.strip()
                        p2_res = int(next_row.find('td', class_='result').text.strip())

                        winner = p1_name if p1_res > p2_res else p2_name

                        # Insertion dans la DB
                        c.execute("""
                            INSERT OR IGNORE INTO matches (date, tournament, player1, player2, winner, surface)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (date_str, current_tournament, p1_name, p2_name, winner, current_surface))

                        # On inverse pour que l'IA apprenne dans les deux sens
                        c.execute("""
                            INSERT OR IGNORE INTO matches (date, tournament, player1, player2, winner, surface)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (date_str, current_tournament, p2_name, p1_name, winner, current_surface))

                        added += 1
                        i += 2
                    except (AttributeError, ValueError, IndexError):
                        i += 1
                else:
                    i += 1

            conn.commit()
            conn.close()
            print(f"✅ {added} matchs ajoutés ({current_surface}).")
            return added

        except Exception as e:
            print(f"💥 Erreur lors du scraping : {e}")
            return 0

    def run_historical_fill(self, days=30):
        """ Remonte dans le temps pour remplir la base """
        today = datetime.now()
        for i in range(days):
            target_date = today - timedelta(days=i)
            self.scrape_date(target_date.strftime("%Y-%m-%d"))
            time.sleep(1)  # Sécurité pour ne pas être banni


if __name__ == "__main__":
    collector = TennisCollector2026()
    # On récupère les 10 derniers jours pour commencer
    collector.run_historical_fill(days=10)