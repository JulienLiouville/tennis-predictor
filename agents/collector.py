import requests
import pandas as pd
from database import get_connection

class CollectorAgent:
    def __init__(self):
        self.atp_url = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master"
        print("✅ CollectorAgent initialisé")

    def collect_historical_data(self, year):
        try:
            url = f"{self.atp_url}/atp_matches_{year}.csv"
            print(f"📥 Téléchargement des matchs ATP {year}...")
            df = pd.read_csv(url)
            print(f"✅ {len(df)} matchs récupérés pour {year}")
            return df
        except Exception as e:
            print(f"❌ Erreur collecte {year}: {e}")
            return pd.DataFrame()

    def save_matches(self, df):
        if df.empty:
            return
        conn = get_connection()
        c = conn.cursor()
        saved = 0
        for _, row in df.iterrows():
            try:
                winner = str(row.get('winner_name', ''))
                loser  = str(row.get('loser_name', ''))
                surface = str(row.get('surface', ''))
                if not winner or not loser or not surface or surface in ('', 'None', 'nan'):
                    continue

                # Match original : winner vs loser → winner gagne
                c.execute(
                    'INSERT OR IGNORE INTO matches (date, tournament, player1, player2, winner, surface, score) VALUES (?,?,?,?,?,?,?)',
                    (str(row.get('tourney_date','')), str(row.get('tourney_name','')),
                     winner, loser, winner, surface, str(row.get('score','')))
                )
                # Match inversé : loser vs winner → winner gagne quand même
                c.execute(
                    'INSERT OR IGNORE INTO matches (date, tournament, player1, player2, winner, surface, score) VALUES (?,?,?,?,?,?,?)',
                    (str(row.get('tourney_date','')), str(row.get('tourney_name','')),
                     loser, winner, winner, surface, str(row.get('score','')))
                )
                saved += 1
            except Exception:
                continue
        conn.commit()
        conn.close()
        print(f"✅ {saved} matchs sauvegardés ({saved*2} entrées avec inversions)")

    def collect_and_save(self, years):
        for year in years:
            df = self.collect_historical_data(year)
            if not df.empty:
                self.save_matches(df)