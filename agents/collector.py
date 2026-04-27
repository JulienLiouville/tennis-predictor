import sqlite3
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
        try:
            c = conn.cursor()
            saved = 0
            for _, row in df.iterrows():
                try:
                    winner = str(row.get('winner_name', ''))
                    loser = str(row.get('loser_name', ''))
                    surface = str(row.get('surface', ''))
                    if not winner or not loser or surface in ('', 'None', 'nan'):
                        continue

                    # Niveau tournoi
                    tourney_level = str(row.get('tourney_level', ''))
                    round_name = str(row.get('round', ''))
                    best_of = row.get('best_of', 3)

                    # Profil winner (= player1)
                    w_rank = row.get('winner_rank', None)
                    w_rank_pts = row.get('winner_rank_points', None)
                    w_age = row.get('winner_age', None)
                    w_hand = str(row.get('winner_hand', ''))
                    w_ht = row.get('winner_ht', None)

                    # Profil loser (= player2)
                    l_rank = row.get('loser_rank', None)
                    l_rank_pts = row.get('loser_rank_points', None)
                    l_age = row.get('loser_age', None)
                    l_hand = str(row.get('loser_hand', ''))
                    l_ht = row.get('loser_ht', None)

                    # Stats In-Game winner
                    w_ace = row.get('w_ace', None)
                    w_df = row.get('w_df', None)
                    w_svpt = row.get('w_svpt', None)
                    w_1stIn = row.get('w_1stIn', None)
                    w_1stWon = row.get('w_1stWon', None)
                    w_2ndWon = row.get('w_2ndWon', None)
                    w_SvGms = row.get('w_SvGms', None)
                    w_bpSaved = row.get('w_bpSaved', None)
                    w_bpFaced = row.get('w_bpFaced', None)

                    # Stats In-Game loser
                    l_ace = row.get('l_ace', None)
                    l_df = row.get('l_df', None)
                    l_svpt = row.get('l_svpt', None)
                    l_1stIn = row.get('l_1stIn', None)
                    l_1stWon = row.get('l_1stWon', None)
                    l_2ndWon = row.get('l_2ndWon', None)
                    l_SvGms = row.get('l_SvGms', None)
                    l_bpSaved = row.get('l_bpSaved', None)
                    l_bpFaced = row.get('l_bpFaced', None)

                    date = str(row.get('tourney_date', ''))
                    tournament = str(row.get('tourney_name', ''))
                    score = str(row.get('score', ''))

                    # Match original : winner vs loser
                    c.execute('''INSERT OR IGNORE INTO matches (
                        date, tournament, tourney_level, surface, round, best_of,
                        player1, player2, winner, score,
                        p1_rank, p1_rank_points, p1_age, p1_hand, p1_height,
                        p2_rank, p2_rank_points, p2_age, p2_hand, p2_height,
                        p1_ace, p1_df, p1_svpt, p1_1stIn, p1_1stWon, p2ndWon,
                        p1_SvGms, p1_bpSaved, p1_bpFaced,
                        p2_ace, p2_df, p2_svpt, p2_1stIn, p2_1stWon, p2_2ndWon,
                        p2_SvGms, p2_bpSaved, p2_bpFaced
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (date, tournament, tourney_level, surface, round_name, best_of,
                     winner, loser, winner, score,
                     w_rank, w_rank_pts, w_age, w_hand, w_ht,
                     l_rank, l_rank_pts, l_age, l_hand, l_ht,
                     w_ace, w_df, w_svpt, w_1stIn, w_1stWon, w_2ndWon,
                     w_SvGms, w_bpSaved, w_bpFaced,
                     l_ace, l_df, l_svpt, l_1stIn, l_1stWon, l_2ndWon,
                     l_SvGms, l_bpSaved, l_bpFaced))

                    # Match inversé : loser vs winner
                    c.execute('''INSERT OR IGNORE INTO matches (
                        date, tournament, tourney_level, surface, round, best_of,
                        player1, player2, winner, score,
                        p1_rank, p1_rank_points, p1_age, p1_hand, p1_height,
                        p2_rank, p2_rank_points, p2_age, p2_hand, p2_height,
                        p1_ace, p1_df, p1_svpt, p1_1stIn, p1_1stWon, p2ndWon,
                        p1_SvGms, p1_bpSaved, p1_bpFaced,
                        p2_ace, p2_df, p2_svpt, p2_1stIn, p2_1stWon, p2_2ndWon,
                        p2_SvGms, p2_bpSaved, p2_bpFaced
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (date, tournament, tourney_level, surface, round_name, best_of,
                     loser, winner, winner, score,
                     l_rank, l_rank_pts, l_age, l_hand, l_ht,
                     w_rank, w_rank_pts, w_age, w_hand, w_ht,
                     l_ace, l_df, l_svpt, l_1stIn, l_1stWon, l_2ndWon,
                     l_SvGms, l_bpSaved, l_bpFaced,
                     w_ace, w_df, w_svpt, w_1stIn, w_1stWon, w_2ndWon,
                     w_SvGms, w_bpSaved, w_bpFaced))

                    saved += 1
                except sqlite3.Error as e:
                    print(f"❌ DB Error: {e}")
                    break
                except Exception as e:
                    continue

            conn.commit()
            print(f"✅ {saved} matchs sauvegardés ({saved * 2} entrées avec inversions)")
        finally:
            conn.close()

    def collect_and_save(self, years):
        for year in years:
            df = self.collect_historical_data(year)
            if not df.empty:
                self.save_matches(df)