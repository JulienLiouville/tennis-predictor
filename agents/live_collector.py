import requests
from datetime import datetime
from database import get_connection
from config import ODDS_API_KEY, ODDS_SPORT, ODDS_REGION, ODDS_MARKET

class LiveCollectorAgent:
    def __init__(self):
        self.base_url = "https://api.the-odds-api.com/v4"
        print("✅ LiveCollectorAgent initialisé")

    def get_todays_matches(self):
        print("📥 Récupération des matchs du jour...")
        try:
            url = f"{self.base_url}/sports/{ODDS_SPORT}/odds"
            params = {
                "apiKey": ODDS_API_KEY,
                "regions": ODDS_REGION,
                "markets": ODDS_MARKET,
                "oddsFormat": "decimal"
            }
            response = requests.get(url, params=params)
            data = response.json()

            if response.status_code != 200:
                print(f"❌ Erreur API: {data}")
                return []

            matches = []
            for event in data:
                if not event.get("bookmakers"):
                    continue
                tourney_name = event.get("sport_title", "Unknown")  # Souvent "WTA Stuttgart" ou "ATP Barcelona"
                player1 = event["home_team"]
                player2 = event["away_team"]
                commence = event["commence_time"]

                # Récupère les cotes
                odds1, odds2 = None, None
                bookmaker = event["bookmakers"][0]
                for market in bookmaker["markets"]:
                    if market["key"] == "h2h":
                        for outcome in market["outcomes"]:
                            if outcome["name"] == player1:
                                odds1 = outcome["price"]
                            elif outcome["name"] == player2:
                                odds2 = outcome["price"]

                matches.append({
                    "player1": player1,
                    "player2": player2,
                    "tournament": tourney_name,
                    "commence_time": commence,
                    "odds1": odds1,
                    "odds2": odds2
                })

            print(f"✅ {len(matches)} matchs trouvés aujourd'hui")
            return matches

        except Exception as e:
            print(f"❌ Erreur: {e}")
            return []

    def save_todays_matches(self, matches):
        if not matches:
            return
        conn = get_connection()
        c = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        for m in matches:
            try:
                c.execute("""
                            INSERT OR IGNORE INTO predictions (date, player1, player2, surface, predicted_winner, confidence)
                            VALUES (?, ?, ?, 
                                COALESCE((SELECT surface FROM tourney_map WHERE ? LIKE '%' || tournament || '%' LIMIT 1), 'Hard'),
                                ?, ?)
                        """, (today, m["player1"], m["player2"], m["tournament"], "", 0.0))
            except Exception:
                continue
        conn.commit()
        conn.close()
        print(f"✅ {len(matches)} matchs sauvegardés")

    def run(self):
        matches = self.get_todays_matches()
        self.save_todays_matches(matches)
        return matches

if __name__ == "__main__":
    agent = LiveCollectorAgent()
    matches = agent.run()
    for m in matches:
        print(f"🎾 {m['player1']} vs {m['player2']} | cotes: {m['odds1']} / {m['odds2']}")