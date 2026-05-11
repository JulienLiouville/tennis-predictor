import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import pickle
import os

from agents.feature_builder import FeatureBuilder
from database import get_connection

# Features utilisées à l'entraînement ET à la prédiction — source unique de vérité
FEATURE_COLUMNS = [
    'rank_diff',
    'p1_momentum_l5', 'p2_momentum_l5',
    'p1_momentum_l10', 'p2_momentum_l10',
    'h2h_p1_ratio', 'h2h_total',
    'p1_fatigue_7d', 'p2_fatigue_7d',
    'surface_enc'
]
SURFACE_LABELS = ['Hard', 'Clay', 'Grass']
LEVEL_MAP = {'G': 4, 'M': 3, 'A': 2, 'F': 3, 'D': 1}


class PredictorAgent:
    def __init__(self):
        self.model = GradientBoostingClassifier(
            n_estimators=100, learning_rate=0.1, max_depth=3, random_state=42
        )
        self.model_path = "data/model.pkl"
        self.fb = FeatureBuilder()
        self.le_surface = LabelEncoder().fit(['Hard', 'Clay', 'Grass'])
        self.is_trained = False

    # ─── CHARGEMENT DES DONNÉES ───────────────────────────────────────────────

    def _load_sackmann(self, conn) -> pd.DataFrame:
        """Charge les matchs historiques Sackmann 2015-2024 (ATP)."""
        return pd.read_sql_query('''
            SELECT m.id, m.player1, m.player2, m.winner, m.surface,
                   m.p1_rank, m.p2_rank, m.tourney_level, m.best_of, m.date,
                   f.p1_momentum_l5, f.p1_momentum_l10,
                   f.p2_momentum_l5, f.p2_momentum_l10,
                   f.h2h_p1_ratio, f.h2h_total,
                   f.p1_fatigue_7d, f.p2_fatigue_7d
            FROM matches m
            INNER JOIN match_features f ON f.match_id = m.id
            WHERE m.player1 != "" AND m.player2 != "" AND m.winner != ""
            AND m.surface IN ("Hard", "Clay", "Grass")
            AND m.p1_rank IS NOT NULL AND m.p2_rank IS NOT NULL
        ''', conn)

    def _load_recent(self, conn) -> pd.DataFrame:
        """Charge les matchs récents 2025+ (ATP + WTA), dupliqués dans les deux sens."""
        df = pd.read_sql_query('''
            SELECT player1, player2, winner, surface,
                   p1_rank, p2_rank, best_of, date,
                   NULL AS tourney_level
            FROM matches_2026
            WHERE player1 != "" AND player2 != "" AND winner != ""
            AND surface IN ("Hard", "Clay", "Grass")
        ''', conn)

        # Dupliquer dans le sens inverse pour avoir les deux classes
        df_inv = df.copy()
        df_inv['player1'], df_inv['player2'] = df['player2'].copy(), df['player1'].copy()
        df_inv['p1_rank'], df_inv['p2_rank'] = df['p2_rank'].copy(), df['p1_rank'].copy()

        result = pd.concat([df, df_inv], ignore_index=True)

        # Ajoute les colonnes features avec valeurs par défaut — après le concat
        result['p1_momentum_l5'] = 0.5
        result['p1_momentum_l10'] = 0.5
        result['p2_momentum_l5'] = 0.5
        result['p2_momentum_l10'] = 0.5
        result['h2h_p1_ratio'] = 0.5
        result['h2h_total'] = 0
        result['p1_fatigue_7d'] = 0
        result['p2_fatigue_7d'] = 0

        return result

    def load_training_data(self) -> pd.DataFrame:
        """Charge et fusionne Sackmann + récents."""
        conn = get_connection()
        try:
            df_sackmann = self._load_sackmann(conn)
            df_recent   = self._load_recent(conn)
            df = pd.concat([df_sackmann, df_recent], ignore_index=True)
            print(f"📊 {len(df)} matchs chargés ({len(df_sackmann)} Sackmann + {len(df_recent)} récents)")
            return df
        finally:
            conn.close()

    # ─── FEATURES ─────────────────────────────────────────────────────────────

    def prepare_features(self, df: pd.DataFrame) -> tuple:
        """
        Lit les features depuis match_features (pré-calculées).
        Fallback 0.5 / 0 pour les matchs sans entrée (matches_2026).
        Aucune requête SQL par ligne — O(1).
        """
        print(f"🔧 Préparation de {len(df)} matchs (lecture match_features)...")

        feats = pd.DataFrame(index=df.index)

        # Features pré-calculées — déjà jointes dans _load_sackmann
        feats['p1_momentum_l5']  = df['p1_momentum_l5'].fillna(0.5)
        feats['p2_momentum_l5']  = df['p2_momentum_l5'].fillna(0.5)
        feats['p1_momentum_l10'] = df['p1_momentum_l10'].fillna(0.5)
        feats['p2_momentum_l10'] = df['p2_momentum_l10'].fillna(0.5)
        feats['h2h_p1_ratio']    = df['h2h_p1_ratio'].fillna(0.5)
        feats['h2h_total']       = df['h2h_total'].fillna(0).astype(int)
        feats['p1_fatigue_7d']   = df['p1_fatigue_7d'].fillna(0).astype(int)
        feats['p2_fatigue_7d']   = df['p2_fatigue_7d'].fillna(0).astype(int)

        # Features calculées à la volée (vectorisées)
        feats['rank_diff'] = (df['p2_rank'].fillna(150) - df['p1_rank'].fillna(150)).values

        surf_series = df['surface'].where(df['surface'].isin(SURFACE_LABELS), other='Hard')
        feats['surface_enc'] = self.le_surface.transform(surf_series)

        y = (df['winner'] == df['player1']).astype(int)
        return feats[FEATURE_COLUMNS], y

    # ─── ENTRAÎNEMENT ─────────────────────────────────────────────────────────

    def train(self) -> float:
        """
        Entraîne le modèle depuis match_features (pré-calculées).
        Rapide : aucune requête SQL par ligne.
        """
        df = self.load_training_data()
        if df.empty:
            print("❌ Aucune donnée pour l'entraînement.")
            return 0.0

        X, y = self.prepare_features(df)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        print("🧠 Entraînement du modèle...")
        self.model.fit(X_train, y_train)

        acc = accuracy_score(y_test, self.model.predict(X_test))
        print(f"✅ Entraînement terminé. Précision : {acc:.2%}")

        self.save_model()
        self.is_trained = True
        return acc

    # ─── PRÉDICTION ───────────────────────────────────────────────────────────

    def predict(self, p1, p2, surface, p1_rank=100, p2_rank=100, date_limit=None):
        if not self.is_trained:
            if os.path.exists(self.model_path):
                self.load_model()
            else:
                return {"status": "error", "message": "Modèle non entraîné"}

        feats = self.fb.build_features(p1, p2, surface, date_limit=date_limit)
        feats['rank_diff']   = p2_rank - p1_rank
        feats['surface_enc'] = self.le_surface.transform(
            [surface if surface in SURFACE_LABELS else 'Hard']
        )[0]

        X = pd.DataFrame([feats])[FEATURE_COLUMNS]
        proba = self.model.predict_proba(X)[0]

        return {
            "predicted_winner": p1 if proba[1] > proba[0] else p2,
            "confidence": round(float(max(proba)), 4),
            "status": "success",
            "features": feats
        }

    # ─── PERSISTANCE ──────────────────────────────────────────────────────────

    def save_model(self):
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        with open(self.model_path, "wb") as f:
            pickle.dump({
                "model": self.model,
                "le_surface": self.le_surface,
                "feature_columns": FEATURE_COLUMNS,
            }, f)
        print("💾 Modèle sauvegardé")

    def load_model(self):
        if os.path.exists(self.model_path):
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
                self.model          = data["model"]
                self.le_surface     = data["le_surface"]
                self.feature_columns = data.get("feature_columns", FEATURE_COLUMNS)
                self.is_trained     = True
            print("✅ Modèle chargé")
        else:
            print("⚠️  Aucun modèle sauvegardé, entraînement requis")

    # ─── PRÉDICTIONS PENDING ──────────────────────────────────────────────────

    def process_pending_predictions(self):
        """Calcule les prédictions pour les matchs du jour sans prédiction."""
        from datetime import datetime
        print("🧠 Calcul des prédictions pour les matchs du jour...")
        conn = get_connection()
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            df = pd.read_sql_query(
                "SELECT id, player1, player2, surface, tournament, p1_rank, p2_rank "
                "FROM predictions WHERE predicted_winner = '' AND date = ?",
                conn, params=(today,)
            )
            if df.empty:
                print("ℹ️  Aucun match en attente")
                return

            updated = 0
            for _, row in df.iterrows():
                surf   = row['surface'] if row['surface'] in SURFACE_LABELS else 'Hard'
                today = datetime.now().strftime('%Y-%m-%d')

                # Détecte le genre depuis le tournoi ou fallback M
                gender = 'F' if any(w in str(row.get('tournament', '')).upper()
                                    for w in ['WTA', 'WOMEN']) else 'M'

                p1_rank = int(row['p1_rank']) if pd.notna(row['p1_rank']) and row['p1_rank'] else \
                    self._get_rank(conn, row['player1'], gender, today)
                p2_rank = int(row['p2_rank']) if pd.notna(row['p2_rank']) and row['p2_rank'] else \
                    self._get_rank(conn, row['player2'], gender, today)
                res = self.predict(row['player1'], row['player2'], surf, p1_rank, p2_rank)
                if res and res.get('status') == 'success':
                    c = conn.cursor()
                    c.execute('''UPDATE predictions
                        SET predicted_winner=?, confidence=?,
                            p1_elo=?, p2_elo=?,
                            p1_elo_surface=?, p2_elo_surface=?,
                            p1_momentum=?, p2_momentum=?,
                            h2h_p1_wins=?, h2h_p2_wins=?
                        WHERE id=?''', (
                        res['predicted_winner'], res['confidence'],
                        res['features'].get('p1_elo', 1500),
                        res['features'].get('p2_elo', 1500),
                        res['features'].get('p1_elo_surface', 1500),
                        res['features'].get('p2_elo_surface', 1500),
                        res['features'].get('p1_momentum_l10', 0.5),
                        res['features'].get('p2_momentum_l10', 0.5),
                        res['features'].get('h2h_p1_wins', 0),
                        res['features'].get('h2h_p2_wins', 0),
                        row['id']
                    ))
                    updated += 1
                    print(
                        f"  🎾 {row['player1']} vs {row['player2']} → {res['predicted_winner']} ({res['confidence']:.0%})")
            conn.commit()
            print(f"✅ {updated} prédictions mises à jour")
        finally:
            conn.close()

    def _get_rank(self, conn, player: str, gender: str, date: str) -> int:
        """Récupère le rang depuis players_rankings pour une date donnée."""
        c = conn.cursor()
        c.execute('''
            SELECT rank FROM players_rankings
            WHERE name LIKE ? AND gender = ?
            AND date_recorded <= ?
            ORDER BY date_recorded DESC LIMIT 1
        ''', (f'%{player.split(".")[0].strip()}%', gender, date))
        row = c.fetchone()
        return int(row[0]) if row else 100


if __name__ == "__main__":
    agent = PredictorAgent()
    agent.train()