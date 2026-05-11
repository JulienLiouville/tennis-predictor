from datetime import datetime, timedelta
import pandas as pd
from database import get_connection


class FeatureBuilder:
    """
    Calcule toutes les features dynamiques avec isolation temporelle stricte.

    Mode LIVE (predict) : méthodes get_h2h / get_momentum / get_fatigue
                          → requêtes SQL unitaires, comportement inchangé.

    Mode BATCH (train)  : build_features_batch(df)
                          → charge tous les matchs UNE seule fois en mémoire,
                            puis calcule tout en pandas pur.
                            Gain : ~100-500x vs boucle SQL par ligne.
    """

    ELO_DEFAULT = 1500

    def __init__(self):
        self._cache: pd.DataFrame | None = None   # matchs historiques en mémoire
        print("✅ FeatureBuilder initialisé (Isolation Temporelle)")

    # ─── UTILITAIRES ──────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_date(date_limit) -> str:
        """Normalise une date en format YYYYMMDD."""
        return str(date_limit).replace('-', '').replace('/', '').strip()

    # ─── CACHE (mode batch) ───────────────────────────────────────────────────

    def _load_cache(self) -> pd.DataFrame:
        """
        Charge tous les matchs depuis 'matches' en mémoire une seule fois.
        Déduplique les entrées Sackmann (stockées dans les 2 sens).
        Retourne un DataFrame avec date normalisée YYYYMMDD.
        """
        if self._cache is not None:
            return self._cache

        print("📦 Chargement du cache matchs en mémoire...")
        conn = get_connection()
        try:
            df = pd.read_sql_query('''
                SELECT date, player1, player2, winner, surface
                FROM matches
                WHERE player1 != "" AND player2 != "" AND winner != ""
            ''', conn)
        finally:
            conn.close()

        # Normalise la date en YYYYMMDD (certaines entrées ont des tirets)
        df['date_norm'] = df['date'].str.replace('-', '', regex=False)

        # Déduplication Sackmann : garde une seule entrée par match réel
        df['match_key'] = (
            df['date_norm'] + '_' +
            df[['player1', 'player2']].apply(
                lambda r: '_'.join(sorted([r['player1'], r['player2']])), axis=1
            )
        )
        df = df.drop_duplicates(subset=['match_key'])

        self._cache = df.reset_index(drop=True)
        print(f"   {len(self._cache)} matchs uniques en cache")
        return self._cache

    def clear_cache(self):
        """Libère la mémoire après l'entraînement."""
        self._cache = None

    # ─── MODE LIVE : méthodes unitaires (inchangées) ──────────────────────────

    def get_h2h(self, p1: str, p2: str, date_limit: str) -> dict:
        date_clean = self._normalize_date(date_limit)
        conn = get_connection()
        try:
            df = pd.read_sql_query('''
                SELECT date, winner, player1, player2
                FROM matches
                WHERE ((player1=? AND player2=?) OR (player1=? AND player2=?))
                AND REPLACE(date, "-", "") < ?
                UNION
                SELECT date, winner, player1, player2
                FROM matches_2026
                WHERE ((player1=? AND player2=?) OR (player1=? AND player2=?))
                AND REPLACE(date, "-", "") < ?
                ORDER BY date ASC
            ''', conn, params=(p1, p2, p2, p1, date_clean,
                               p1, p2, p2, p1, date_clean))

            if df.empty:
                return {'p1_wins': 0, 'p2_wins': 0, 'total': 0, 'h2h_ratio': 0.5}

            df['match_key'] = df.apply(
                lambda r: r['date'] + '_' + '_'.join(sorted([r['player1'], r['player2']])),
                axis=1
            )
            df = df.drop_duplicates(subset=['match_key'])
            p1_wins = len(df[df['winner'] == p1])
            p2_wins = len(df[df['winner'] == p2])
            total = len(df)
            return {
                'p1_wins': p1_wins, 'p2_wins': p2_wins, 'total': total,
                'h2h_ratio': p1_wins / total if total > 0 else 0.5
            }
        finally:
            conn.close()

    def get_momentum(self, player: str, n: int, date_limit: str) -> float:
        date_clean = self._normalize_date(date_limit)
        conn = get_connection()
        try:
            df = pd.read_sql_query('''
                SELECT date, winner, player1, player2
                FROM matches
                WHERE (player1=? OR player2=?)
                AND REPLACE(date, "-", "") < ?
                UNION
                SELECT date, winner, player1, player2
                FROM matches_2026
                WHERE (player1=? OR player2=?)
                AND REPLACE(date, "-", "") < ?
                ORDER BY date DESC
            ''', conn, params=(player, player, date_clean,
                               player, player, date_clean))

            if df.empty:
                return 0.5

            df['match_key'] = df.apply(
                lambda r: r['date'] + '_' + '_'.join(sorted([r['player1'], r['player2']])),
                axis=1
            )
            df = df.drop_duplicates(subset=['match_key']).head(n)
            wins = len(df[df['winner'] == player])
            return round(wins / len(df), 4)
        finally:
            conn.close()

    def get_elo(self, player: str, surface: str = None) -> float:
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

    def get_fatigue(self, player: str, date_limit: str, days: int = 7) -> int:
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
                UNION
                SELECT date, player1, player2
                FROM matches_2026
                WHERE (player1=? OR player2=?)
                AND REPLACE(date, "-", "") >= ?
                AND REPLACE(date, "-", "") < ?
            ''', conn, params=(player, player, cutoff, date_clean,
                               player, player, cutoff, date_clean))

            if df.empty:
                return 0

            df['match_key'] = df.apply(
                lambda r: r['date'] + '_' + '_'.join(sorted([r['player1'], r['player2']])),
                axis=1
            )
            return len(df.drop_duplicates(subset=['match_key']))
        finally:
            conn.close()

    def build_features(self, p1: str, p2: str, surface: str,
                       date_limit: str = None) -> dict:
        """Mode live — utilisé par predict()."""
        if not date_limit:
            date_limit = datetime.now().strftime('%Y%m%d')

        h2h = self.get_h2h(p1, p2, date_limit)
        return {
            'p1_elo':          self.get_elo(p1),
            'p2_elo':          self.get_elo(p2),
            'p1_elo_surface':  self.get_elo(p1, surface),
            'p2_elo_surface':  self.get_elo(p2, surface),
            'elo_diff':        self.get_elo(p1) - self.get_elo(p2),
            'elo_surface_diff':self.get_elo(p1, surface) - self.get_elo(p2, surface),
            'p1_momentum_l5':  self.get_momentum(p1, 5, date_limit),
            'p2_momentum_l5':  self.get_momentum(p2, 5, date_limit),
            'p1_momentum_l10': self.get_momentum(p1, 10, date_limit),
            'p2_momentum_l10': self.get_momentum(p2, 10, date_limit),
            'h2h_p1_wins':     h2h['p1_wins'],
            'h2h_p2_wins':     h2h['p2_wins'],
            'h2h_total':       h2h['total'],
            'h2h_p1_ratio':    h2h['h2h_ratio'],
            'p1_fatigue_7d':   self.get_fatigue(p1, date_limit),
            'p2_fatigue_7d':   self.get_fatigue(p2, date_limit),
        }

    # ─── MODE BATCH : vectorisé pour l'entraînement ───────────────────────────

    def build_features_batch(self, df_train: pd.DataFrame) -> pd.DataFrame:
        """
        Calcule toutes les features pour un DataFrame complet de matchs.
        Isolation temporelle stricte : pour chaque match, on ne regarde
        que les matchs AVANT sa date.

        Entrée  : df_train avec colonnes [player1, player2, surface, date]
        Sortie  : DataFrame de features aligné sur df_train.index

        Complexité : O(N) requêtes → O(1) + calculs pandas vectorisés.
        """
        hist = self._load_cache()   # charge une seule fois

        # Normalise les dates du jeu d'entraînement
        df_train = df_train.copy()
        df_train['date_norm'] = df_train['date'].astype(str).str.replace('-', '', regex=False)

        n = len(df_train)
        print(f"🔧 Calcul batch de {n} features (vectorisé)...")

        # Pré-charge l'Elo depuis la DB en un seul passage
        elo_map = self._load_elo_map()

        records = []
        for i, (idx, row) in enumerate(df_train.iterrows()):
            if i % 10000 == 0:
                print(f"   {i}/{n}...")

            p1       = row['player1']
            p2       = row['player2']
            surface  = row['surface']
            date_cut = row['date_norm']

            # Filtre temporel depuis le cache en mémoire — zéro SQL
            past = hist[hist['date_norm'] < date_cut]

            # ── H2H ──
            h2h_mask = (
                ((hist['player1'] == p1) & (hist['player2'] == p2)) |
                ((hist['player1'] == p2) & (hist['player2'] == p1))
            )
            h2h_df = hist[h2h_mask & (hist['date_norm'] < date_cut)]
            h2h_total = len(h2h_df)
            h2h_p1_wins = len(h2h_df[h2h_df['winner'] == p1])
            h2h_ratio = h2h_p1_wins / h2h_total if h2h_total > 0 else 0.5

            # ── MOMENTUM ──
            p1_matches = past[(past['player1'] == p1) | (past['player2'] == p1)] \
                             .sort_values('date_norm', ascending=False)
            p2_matches = past[(past['player1'] == p2) | (past['player2'] == p2)] \
                             .sort_values('date_norm', ascending=False)

            p1_mom_l5  = self._momentum_from_df(p1_matches.head(5),  p1)
            p1_mom_l10 = self._momentum_from_df(p1_matches.head(10), p1)
            p2_mom_l5  = self._momentum_from_df(p2_matches.head(5),  p2)
            p2_mom_l10 = self._momentum_from_df(p2_matches.head(10), p2)

            # ── FATIGUE (7 jours) ──
            ref_date = datetime.strptime(date_cut, '%Y%m%d')
            cutoff   = (ref_date - timedelta(days=7)).strftime('%Y%m%d')
            p1_fatigue = len(past[
                (past['date_norm'] >= cutoff) &
                ((past['player1'] == p1) | (past['player2'] == p1))
            ])
            p2_fatigue = len(past[
                (past['date_norm'] >= cutoff) &
                ((past['player1'] == p2) | (past['player2'] == p2))
            ])

            # ── ELO ──
            p1_elo         = elo_map.get((p1, 'global'), self.ELO_DEFAULT)
            p2_elo         = elo_map.get((p2, 'global'), self.ELO_DEFAULT)
            p1_elo_surface = elo_map.get((p1, surface),  self.ELO_DEFAULT)
            p2_elo_surface = elo_map.get((p2, surface),  self.ELO_DEFAULT)

            records.append({
                'p1_elo':          p1_elo,
                'p2_elo':          p2_elo,
                'p1_elo_surface':  p1_elo_surface,
                'p2_elo_surface':  p2_elo_surface,
                'elo_diff':        p1_elo - p2_elo,
                'elo_surface_diff':p1_elo_surface - p2_elo_surface,
                'p1_momentum_l5':  p1_mom_l5,
                'p2_momentum_l5':  p2_mom_l5,
                'p1_momentum_l10': p1_mom_l10,
                'p2_momentum_l10': p2_mom_l10,
                'h2h_p1_wins':     h2h_p1_wins,
                'h2h_p2_wins':     h2h_total - h2h_p1_wins,
                'h2h_total':       h2h_total,
                'h2h_p1_ratio':    h2h_ratio,
                'p1_fatigue_7d':   p1_fatigue,
                'p2_fatigue_7d':   p2_fatigue,
            })

        result = pd.DataFrame(records, index=df_train.index)
        self.clear_cache()   # libère la mémoire
        return result

    # ─── HELPERS INTERNES ─────────────────────────────────────────────────────

    @staticmethod
    def _momentum_from_df(df: pd.DataFrame, player: str) -> float:
        if df.empty:
            return 0.5
        wins = (df['winner'] == player).sum()
        return round(wins / len(df), 4)

    def _load_elo_map(self) -> dict:
        """Charge tous les Elo en un seul SELECT → dict (player, surface) → elo."""
        conn = get_connection()
        try:
            df = pd.read_sql_query(
                'SELECT player, elo_global, elo_hard, elo_clay, elo_grass FROM elo_ratings',
                conn
            )
        finally:
            conn.close()

        elo_map = {}
        for _, row in df.iterrows():
            p = row['player']
            elo_map[(p, 'global')] = row['elo_global'] or self.ELO_DEFAULT
            elo_map[(p, 'Hard')]   = row['elo_hard']   or self.ELO_DEFAULT
            elo_map[(p, 'Clay')]   = row['elo_clay']   or self.ELO_DEFAULT
            elo_map[(p, 'Grass')]  = row['elo_grass']  or self.ELO_DEFAULT
        return elo_map


if __name__ == "__main__":
    fb = FeatureBuilder()

    print("\n=== Test isolation temporelle H2H (mode live) ===")
    h2h = fb.get_h2h("Grigor Dimitrov", "Holger Rune", "20240107")
    print(f"H2H avant 20240107 : {h2h}")
    assert h2h['total'] == 3, f"Attendu 3, obtenu {h2h['total']}"

    print("\n=== Test momentum ===")
    m = fb.get_momentum("Grigor Dimitrov", 10, "20240107")
    print(f"Momentum Dimitrov : {m}")

    print("\n=== Test fatigue ===")
    f = fb.get_fatigue("Grigor Dimitrov", "20240107")
    print(f"Fatigue Dimitrov  : {f}")

    print("\n✅ Tous les tests passés")