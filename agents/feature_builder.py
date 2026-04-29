from datetime import datetime, timedelta
import pandas as pd
from database import get_connection


class FeatureBuilder:
    """
    Calcule toutes les features dynamiques avec isolation temporelle stricte.
    Toutes les méthodes acceptent date_limit (format YYYYMMDD ou YYYY-MM-DD)
    et ne regardent que les matchs AVANT cette date.
    """

    ELO_DEFAULT = 1500

    def __init__(self):
        print("✅ FeatureBuilder initialisé (Isolation Temporelle)")

    # ─── UTILITAIRES ──────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_date(date_limit) -> str:
        """Normalise une date en format YYYYMMDD."""
        return str(date_limit).replace('-', '').replace('/', '').strip()

    # ─── H2H ──────────────────────────────────────────────────────────────────

    def get_h2h(self, p1: str, p2: str, date_limit: str) -> dict:
        """
        Head-to-head entre p1 et p2, uniquement pour les matchs avant date_limit.
        Déduplication par (date, joueurs triés) pour éviter le double-comptage
        dû à la duplication Sackmann (chaque match stocké dans les 2 sens).
        """
        date_clean = self._normalize_date(date_limit)
        conn = get_connection()
        try:
            df = pd.read_sql_query('''
                SELECT date, winner, player1, player2
                FROM matches
                WHERE ((player1=? AND player2=?) OR (player1=? AND player2=?))
                AND REPLACE(date, "-", "") < ?
                ORDER BY date ASC
            ''', conn, params=(p1, p2, p2, p1, date_clean))

            if df.empty:
                return {'p1_wins': 0, 'p2_wins': 0, 'total': 0, 'h2h_ratio': 0.5}

            # Déduplication : une seule ligne par (date, paire de joueurs)
            df['match_key'] = df.apply(
                lambda r: r['date'] + '_' + '_'.join(sorted([r['player1'], r['player2']])),
                axis=1
            )
            df = df.drop_duplicates(subset=['match_key'])

            p1_wins = len(df[df['winner'] == p1])
            p2_wins = len(df[df['winner'] == p2])
            total = len(df)

            return {
                'p1_wins': p1_wins,
                'p2_wins': p2_wins,
                'total': total,
                'h2h_ratio': p1_wins / total if total > 0 else 0.5
            }
        finally:
            conn.close()

    # ─── MOMENTUM ─────────────────────────────────────────────────────────────

    def get_momentum(self, player: str, n: int, date_limit: str) -> float:
        """
        Ratio de victoires sur les N derniers matchs avant date_limit.
        Déduplication pour éviter le double-comptage Sackmann.
        """
        date_clean = self._normalize_date(date_limit)
        conn = get_connection()
        try:
            df = pd.read_sql_query('''
                SELECT date, winner, player1, player2
                FROM matches
                WHERE (player1=? OR player2=?)
                AND REPLACE(date, "-", "") < ?
                ORDER BY date DESC
            ''', conn, params=(player, player, date_clean))

            if df.empty:
                return 0.5

            # Déduplication avant de limiter à N
            df['match_key'] = df.apply(
                lambda r: r['date'] + '_' + '_'.join(sorted([r['player1'], r['player2']])),
                axis=1
            )
            df = df.drop_duplicates(subset=['match_key']).head(n)

            wins = len(df[df['winner'] == player])
            return round(wins / len(df), 4)
        finally:
            conn.close()

    # ─── ELO ──────────────────────────────────────────────────────────────────

    def get_elo(self, player: str, surface: str = None) -> float:
        """Récupère l'Elo depuis elo_ratings (calculé à l'entraînement)."""
        conn = get_connection()
        try:
            col = {'Hard': 'elo_hard', 'Clay': 'elo_clay',
                   'Grass': 'elo_grass'}.get(surface, 'elo_global')
            c = conn.cursor()
            c.execute(f'SELECT {col} FROM elo_ratings WHERE player=?', (player,))
            row = c.fetchone()
            return row[0] if row else self.ELO_DEFAULT
        finally:
            conn.close()

    # ─── FATIGUE ──────────────────────────────────────────────────────────────

    def get_fatigue(self, player: str, date_limit: str, days: int = 7) -> int:
        """
        Nombre de matchs joués sur les N derniers jours avant date_limit.
        Déduplication pour éviter le double-comptage Sackmann.
        """
        date_clean = self._normalize_date(date_limit)
        ref_date = datetime.strptime(date_clean, '%Y%m%d')
        cutoff = (ref_date - timedelta(days=days)).strftime('%Y%m%d')

        conn = get_connection()
        try:
            df = pd.read_sql_query('''
                SELECT date, player1, player2
                FROM matches
                WHERE (player1=? OR player2=?)
                AND REPLACE(date, "-", "") >= ?
                AND REPLACE(date, "-", "") < ?
            ''', conn, params=(player, player, cutoff, date_clean))

            if df.empty:
                return 0

            df['match_key'] = df.apply(
                lambda r: r['date'] + '_' + '_'.join(sorted([r['player1'], r['player2']])),
                axis=1
            )
            return len(df.drop_duplicates(subset=['match_key']))
        finally:
            conn.close()

    # ─── BUILD FEATURES ───────────────────────────────────────────────────────

    def build_features(self, p1: str, p2: str, surface: str,
                       date_limit: str = None) -> dict:
        """
        Construit le vecteur de features complet pour une prédiction.
        date_limit : format YYYYMMDD ou YYYY-MM-DD.
        Si None → aujourd'hui (mode prédiction live).
        """
        if not date_limit:
            date_limit = datetime.now().strftime('%Y%m%d')

        h2h = self.get_h2h(p1, p2, date_limit)

        return {
            # Elo (depuis elo_ratings, calculé à l'entraînement)
            'p1_elo': self.get_elo(p1),
            'p2_elo': self.get_elo(p2),
            'p1_elo_surface': self.get_elo(p1, surface),
            'p2_elo_surface': self.get_elo(p2, surface),
            'elo_diff': self.get_elo(p1) - self.get_elo(p2),
            'elo_surface_diff': self.get_elo(p1, surface) - self.get_elo(p2, surface),
            # Momentum
            'p1_momentum_l5': self.get_momentum(p1, 5, date_limit),
            'p2_momentum_l5': self.get_momentum(p2, 5, date_limit),
            'p1_momentum_l10': self.get_momentum(p1, 10, date_limit),
            'p2_momentum_l10': self.get_momentum(p2, 10, date_limit),
            # H2H
            'h2h_p1_wins': h2h['p1_wins'],
            'h2h_p2_wins': h2h['p2_wins'],
            'h2h_total': h2h['total'],
            'h2h_p1_ratio': h2h['h2h_ratio'],
            # Fatigue
            'p1_fatigue_7d': self.get_fatigue(p1, date_limit),
            'p2_fatigue_7d': self.get_fatigue(p2, date_limit),
        }


if __name__ == "__main__":
    # Test de validation
    fb = FeatureBuilder()

    print("\n=== Test isolation temporelle H2H ===")
    # Dimitrov vs Rune : 3 matchs avant 20240107 (20230703, 20230927, 20240101)
    h2h = fb.get_h2h("Grigor Dimitrov", "Holger Rune", "20240107")
    print(f"H2H avant 20240107 : {h2h}")
    assert h2h['total'] == 3, f"Attendu 3, obtenu {h2h['total']}"

    print("\n=== Test momentum ===")
    m = fb.get_momentum("Grigor Dimitrov", 10, "20240107")
    print(f"Momentum Dimitrov (10 matchs avant 20240107) : {m}")

    print("\n=== Test fatigue ===")
    f = fb.get_fatigue("Grigor Dimitrov", "20240107")
    print(f"Fatigue Dimitrov (7j avant 20240107) : {f}")

    print("\n✅ Tous les tests passés")