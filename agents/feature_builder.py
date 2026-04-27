import pandas as pd
from database import get_connection


class FeatureBuilder:
    """
    Calcule toutes les features dynamiques :
    Elo global + par surface, Momentum, H2H, Fatigue
    """

    ELO_K = 32
    ELO_DEFAULT = 1500

    def __init__(self):
        print("✅ FeatureBuilder initialisé")

    # ─── ELO ──────────────────────────────────────────────

    def compute_all_elo(self):
        """Recalcule tous les Elo depuis l'historique complet"""
        print("🧮 Calcul des Elo ratings...")
        conn = get_connection()
        try:
            df = pd.read_sql_query('''
                SELECT player1, player2, winner, surface, date
                FROM matches
                WHERE winner != "" AND surface IN ("Hard","Clay","Grass")
                ORDER BY date ASC
            ''', conn)

            elo = {}  # {player: {global, Hard, Clay, Grass}}

            def get_elo(player, surface=None):
                if player not in elo:
                    elo[player] = {
                        'global': self.ELO_DEFAULT,
                        'Hard': self.ELO_DEFAULT,
                        'Clay': self.ELO_DEFAULT,
                        'Grass': self.ELO_DEFAULT,
                        'matches': 0
                    }
                if surface:
                    return elo[player][surface]
                return elo[player]['global']

            def update_elo(winner, loser, surface):
                # Elo global
                r1 = get_elo(winner)
                r2 = get_elo(loser)
                e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
                e2 = 1 - e1
                elo[winner]['global'] = r1 + self.ELO_K * (1 - e1)
                elo[loser]['global'] = r2 + self.ELO_K * (0 - e2)

                # Elo par surface
                r1s = get_elo(winner, surface)
                r2s = get_elo(loser, surface)
                e1s = 1 / (1 + 10 ** ((r2s - r1s) / 400))
                e2s = 1 - e1s
                elo[winner][surface] = r1s + self.ELO_K * (1 - e1s)
                elo[loser][surface] = r2s + self.ELO_K * (0 - e2s)

                elo[winner]['matches'] = elo[winner].get('matches', 0) + 1
                elo[loser]['matches'] = elo[loser].get('matches', 0) + 1

            for _, row in df.iterrows():
                update_elo(row['winner'],
                           row['player2'] if row['winner'] == row['player1'] else row['player1'],
                           row['surface'])

            # Sauvegarde en DB
            c = conn.cursor()
            for player, ratings in elo.items():
                c.execute('''INSERT OR REPLACE INTO elo_ratings
                    (player, elo_global, elo_hard, elo_clay, elo_grass, matches_played, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (player,
                      round(ratings['global'], 2),
                      round(ratings['Hard'], 2),
                      round(ratings['Clay'], 2),
                      round(ratings['Grass'], 2),
                      ratings['matches']))
            conn.commit()
            print(f"✅ Elo calculé pour {len(elo)} joueurs")
        finally:
            conn.close()

    def get_elo(self, player: str, surface: str = None) -> float:
        conn = get_connection()
        try:
            c = conn.cursor()
            col = {'Hard': 'elo_hard', 'Clay': 'elo_clay',
                   'Grass': 'elo_grass'}.get(surface, 'elo_global')
            c.execute(f'SELECT {col} FROM elo_ratings WHERE player = ?', (player,))
            row = c.fetchone()
            return row[0] if row else self.ELO_DEFAULT
        finally:
            conn.close()

    # ─── MOMENTUM ─────────────────────────────────────────

    def get_momentum(self, player: str, n: int = 10) -> float:
        """Ratio de victoires sur les N derniers matchs"""
        conn = get_connection()
        try:
            c = conn.cursor()
            c.execute('''
                SELECT winner FROM matches
                WHERE (player1 = ? OR player2 = ?)
                ORDER BY date DESC
                LIMIT ?
            ''', (player, player, n))
            rows = c.fetchall()
            if not rows:
                return 0.5
            wins = sum(1 for r in rows if r[0] == player)
            return round(wins / len(rows), 4)
        finally:
            conn.close()

    # ─── H2H ──────────────────────────────────────────────

    def get_h2h(self, player1: str, player2: str) -> dict:
        """Head-to-head entre deux joueurs"""
        conn = get_connection()
        try:
            c = conn.cursor()
            c.execute('''
                SELECT winner FROM matches
                WHERE (player1 = ? AND player2 = ?)
                OR (player1 = ? AND player2 = ?)
            ''', (player1, player2, player2, player1))
            rows = c.fetchall()
            p1_wins = sum(1 for r in rows if r[0] == player1)
            p2_wins = sum(1 for r in rows if r[0] == player2)
            return {'p1_wins': p1_wins, 'p2_wins': p2_wins, 'total': len(rows)}
        finally:
            conn.close()

    # ─── FATIGUE ──────────────────────────────────────────

    def get_fatigue(self, player: str, days: int = 7) -> int:
        """Nombre de matchs joués sur les N derniers jours"""
        conn = get_connection()
        try:
            c = conn.cursor()
            from datetime import datetime, timedelta
            cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
            c.execute('''
                SELECT COUNT(*) FROM matches
                WHERE (player1 = ? OR player2 = ?)
                AND date >= ?
            ''', (player, player, cutoff))
            return c.fetchone()[0]
        finally:
            conn.close()

    # ─── FEATURES COMPLÈTES ───────────────────────────────

    def build_features(self, player1: str, player2: str, surface: str) -> dict:
        """Construit le vecteur de features complet pour une prédiction"""
        h2h = self.get_h2h(player1, player2)

        return {
            # Elo
            'p1_elo': self.get_elo(player1),
            'p2_elo': self.get_elo(player2),
            'p1_elo_surface': self.get_elo(player1, surface),
            'p2_elo_surface': self.get_elo(player2, surface),
            'elo_diff': self.get_elo(player1) - self.get_elo(player2),
            'elo_surface_diff': self.get_elo(player1, surface) - self.get_elo(player2, surface),
            # Momentum
            'p1_momentum_l5': self.get_momentum(player1, 5),
            'p2_momentum_l5': self.get_momentum(player2, 5),
            'p1_momentum_l10': self.get_momentum(player1, 10),
            'p2_momentum_l10': self.get_momentum(player2, 10),
            # H2H
            'h2h_p1_wins': h2h['p1_wins'],
            'h2h_p2_wins': h2h['p2_wins'],
            'h2h_total': h2h['total'],
            'h2h_p1_ratio': h2h['p1_wins'] / h2h['total'] if h2h['total'] > 0 else 0.5,
            # Fatigue
            'p1_fatigue_7d': self.get_fatigue(player1, 7),
            'p2_fatigue_7d': self.get_fatigue(player2, 7),
            # Surface encodée
            'surface': surface,
        }


if __name__ == "__main__":
    fb = FeatureBuilder()
    fb.compute_all_elo()

    # Test
    features = fb.build_features("Novak Djokovic", "Rafael Nadal", "Clay")
    for k, v in features.items():
        print(f"  {k}: {v}")