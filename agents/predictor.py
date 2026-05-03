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
        self.model = GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, max_depth=3, random_state=42)
        self.model_path = "data/model.pkl"
        self.fb = FeatureBuilder()
        self.le_surface = LabelEncoder().fit(['Hard', 'Clay', 'Grass'])
        self.is_trained = False

    def _add_elo_momentum_h2h(self, df: pd.DataFrame) -> pd.DataFrame:
        print("🔧 Enrichissement Elo / Momentum / H2H avec Isolation Temporelle...")
        records = []
        total = len(df)
        for i, (_, row) in enumerate(df.iterrows()):
            if i % 5000 == 0:
                print(f"   {i}/{total}...")

            # CORRECTION : On passe row['date'] pour ne regarder que le passé
            feats = self.feature_builder.build_features(
                row['player1'], row['player2'], row['surface'], date_limit=row['date']
            )
            records.append(feats)

        feats_df = pd.DataFrame(records, index=df.index)
        for col in ['elo_diff', 'elo_surface_diff', 'p1_momentum_l5', 'p2_momentum_l5',
                    'p1_momentum_l10', 'p2_momentum_l10', 'h2h_p1_ratio', 'h2h_total',
                    'p1_fatigue_7d', 'p2_fatigue_7d']:
            df[col] = feats_df[col]
        return df

    # ─── CHARGEMENT DES DONNÉES ───────────────────────────────────────────────


    def _load_sackmann(self, conn) -> pd.DataFrame:
        """Charge les matchs historiques Sackmann 2015-2024 (ATP)."""
        df = pd.read_sql_query('''
                SELECT player1, player2, winner, surface,
                       p1_rank, p2_rank,
                       p1_ace, p1_df, p1_svpt, p1_1stIn, p1_1stWon,
                       p2ndWon AS p1_2ndWon_raw,
                       p1_bpSaved, p1_bpFaced,
                       p2_ace, p2_df, p2_svpt, p2_1stIn, p2_1stWon,
                       p2_2ndWon, p2_bpSaved, p2_bpFaced,
                       tourney_level, best_of, date
                FROM matches
                WHERE player1 != "" AND player2 != "" AND winner != ""
                AND surface IN ("Hard", "Clay", "Grass")
            ''', conn)
        df['source'] = 'sackmann'
        df['p1_2ndWon'] = df['p1_2ndWon_raw']
        return df


    def _load_recent(self, conn) -> pd.DataFrame:
        """Charge les matchs récents 2025+ (ATP + WTA), dupliqués dans les deux sens."""
        df = pd.read_sql_query('''
                SELECT player1, player2, winner, surface,
                       p1_rank, p2_rank,
                       NULL AS p1_ace, NULL AS p1_df,
                       NULL AS p1_svpt, NULL AS p1_1stIn, NULL AS p1_1stWon,
                       NULL AS p1_2ndWon,
                       NULL AS p1_bpSaved, NULL AS p1_bpFaced,
                       NULL AS p2_ace, NULL AS p2_df,
                       NULL AS p2_svpt, NULL AS p2_1stIn, NULL AS p2_1stWon,
                       NULL AS p2_2ndWon, NULL AS p2_bpSaved, NULL AS p2_bpFaced,
                       NULL AS tourney_level,
                       best_of, date
                FROM matches_2026
                WHERE player1 != "" AND player2 != "" AND winner != ""
                AND surface IN ("Hard", "Clay", "Grass")
                AND p1_rank IS NOT NULL AND p2_rank IS NOT NULL
            ''', conn)

        # Dupliquer dans le sens inverse (comme Sackmann) pour avoir les deux classes
        df_inv = df.copy()
        df_inv['player1'] = df['player2']
        df_inv['player2'] = df['player1']
        df_inv['p1_rank'] = df['p2_rank']
        df_inv['p2_rank'] = df['p1_rank']

        df = pd.concat([df, df_inv], ignore_index=True)
        df['source'] = 'recent'
        return df


    def load_training_data(self) -> pd.DataFrame:
        """Charge et fusionne Sackmann + récents, filtre les ranks manquants."""
        conn = get_connection()
        try:
            df_sackmann = self._load_sackmann(conn)
            df_recent = self._load_recent(conn)

            df = pd.concat([df_sackmann, df_recent], ignore_index=True)

            # Filtre strict : les deux ranks obligatoires
            before = len(df)
            df = df.dropna(subset=['p1_rank', 'p2_rank'])
            after = len(df)
            print(f"📊 {before} matchs chargés → {after} après filtre ranks "
                  f"({before - after} ignorés)")
            print(f"   Sackmann ATP : {len(df[df['source'] == 'sackmann'])} | "
                  f"Récents ATP+WTA : {len(df[df['source'] == 'recent'])}")
            return df
        finally:
            conn.close()

        # ─── FEATURES ─────────────────────────────────────────────────────────────


    def _compute_service_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcule les stats service — NaN pour les matchs sans ces données."""
        df['p1_1st_serve_pct'] = (
                df['p1_1stIn'] / df['p1_svpt'].replace(0, np.nan)
        )
        df['p1_1st_won_pct'] = (
                df['p1_1stWon'] / df['p1_1stIn'].replace(0, np.nan)
        )
        df['p1_2nd_won_pct'] = (
                df['p1_2ndWon'] / (df['p1_svpt'] - df['p1_1stIn']).replace(0, np.nan)
        )
        df['p1_bp_saved_pct'] = (
                df['p1_bpSaved'] / df['p1_bpFaced'].replace(0, np.nan)
        )
        df['p2_1st_serve_pct'] = (
                df['p2_1stIn'] / df['p2_svpt'].replace(0, np.nan)
        )
        df['p2_1st_won_pct'] = (
                df['p2_1stWon'] / df['p2_1stIn'].replace(0, np.nan)
        )
        df['p2_2nd_won_pct'] = (
                df['p2_2ndWon'] / (df['p2_svpt'] - df['p2_1stIn']).replace(0, np.nan)
        )
        df['p2_bp_saved_pct'] = (
                df['p2_bpSaved'] / df['p2_bpFaced'].replace(0, np.nan)
        )
        # Dominance ratio — cohérent avec predict()
        df['p1_dr'] = df['p1_1st_won_pct'] - df['p2_1st_won_pct']
        return df


    def _add_elo_momentum_h2h(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enrichit le DataFrame avec Elo, Momentum, H2H depuis feature_builder.
        Opère ligne par ligne — lent mais exact. Utilisé uniquement à l'entraînement.
        """
        print("🔧 Enrichissement Elo / Momentum / H2H (peut prendre quelques minutes)...")
        records = []
        total = len(df)
        for i, (_, row) in enumerate(df.iterrows()):
            if i % 5000 == 0:
                print(f"   {i}/{total}...")
            feats = self.feature_builder.build_features(
                row['player1'], row['player2'], row['surface']
            )
            records.append(feats)

        feats_df = pd.DataFrame(records, index=df.index)
        for col in ['elo_diff', 'elo_surface_diff',
                    'p1_momentum_l5', 'p2_momentum_l5',
                    'p1_momentum_l10', 'p2_momentum_l10',
                    'h2h_p1_ratio', 'h2h_total',
                    'p1_fatigue_7d', 'p2_fatigue_7d']:
            df[col] = feats_df[col]
        return df

    def prepare_features(self, df: pd.DataFrame) -> tuple:
        print(f"🔧 Préparation de {len(df)} matchs (Mode Anti-Leak)...")
        records = []

        for _, row in df.iterrows():
            # 1. On calcule uniquement le PASSÉ via le builder
            # On passe bien la date du match pour filtrer
            date_str = str(row['date']).replace('-', '')
            feats = self.fb.build_features(
                row['player1'],
                row['player2'],
                row['surface'],
                date_limit=date_str
            )

            # 2. Ajout des données de contexte (Ranks)
            p1_rank = row['p1_rank'] if pd.notnull(row['p1_rank']) else 150
            p2_rank = row['p2_rank'] if pd.notnull(row['p2_rank']) else 150
            feats['rank_diff'] = p2_rank - p1_rank

            # 3. Encodage Surface
            surf = row['surface'] if row['surface'] in ['Hard', 'Clay', 'Grass'] else 'Hard'
            # Utilisation de ton LabelEncoder déjà initialisé
            try:
                feats['surface_enc'] = self.le_surface.transform([surf])[0]
            except:
                feats['surface_enc'] = 0

            records.append(feats)

        X = pd.DataFrame(records)
        y = (df['winner'] == df['player1']).astype(int)

        # SÉCURITÉ : On ne retourne QUE les colonnes définies dans FEATURE_COLUMNS
        # Cela garantit l'absence de KeyError et de Data Leak
        return X[FEATURE_COLUMNS], y

    # ─── ENTRAÎNEMENT ─────────────────────────────────────────────────────────

    def train(self):
        conn = get_connection()
        query = "SELECT * FROM matches WHERE p1_rank IS NOT NULL AND p2_rank IS NOT NULL"
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            print("❌ Aucune donnée pour l'entraînement.")
            return 0

        X, y = self.prepare_features(df)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        print("🧠 Entraînement du modèle...")
        self.model.fit(X_train, y_train)

        acc = accuracy_score(y_test, self.model.predict(X_test))
        print(f"✅ Entraînement terminé. Précision : {acc:.2%}")

        os.makedirs("data", exist_ok=True)
        self.save_model()
        self.is_trained = True
        return acc

        # ─── PRÉDICTION ───────────────────────────────────────────────────────────

    def predict(self, p1, p2, surface, p1_rank=100, p2_rank=100,date_limit=None):
        if not self.is_trained:
            if os.path.exists(self.model_path):
                self.load_model()  # ← utilise load_model() plutôt que pickle brut
            else:
                return {"status": "error", "message": "Modèle non entraîné"}

        feats = self.fb.build_features(p1, p2, surface, date_limit=date_limit)
        feats['rank_diff'] = p2_rank - p1_rank
        feats['surface_enc'] = self.le_surface.transform([surface if surface in ['Hard', 'Clay', 'Grass'] else 'Hard'])[
            0]

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
                "feature_columns": self.feature_columns
            }, f)
        print("💾 Modèle sauvegardé")


    def load_model(self):
        if os.path.exists(self.model_path):
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
                self.model = data["model"]
                self.le_surface = data["le_surface"]
                self.feature_columns = data["feature_columns"]
                self.is_trained = True
            print("✅ Modèle chargé")
        else:
            print("⚠️ Aucun modèle sauvegardé, entraînement requis")

        # ─── PRÉDICTIONS PENDING ──────────────────────────────────────────────────


    def process_pending_predictions(self):
        """Calcule les prédictions pour les matchs du jour sans prédiction."""
        from datetime import datetime
        print("🧠 Calcul des prédictions pour les matchs du jour...")
        conn = get_connection()
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            df = pd.read_sql_query(
                "SELECT id, player1, player2, surface, p1_rank, p2_rank "
                "FROM predictions WHERE predicted_winner = '' AND date = ?",
                conn, params=(today,)
            )
            if df.empty:
                print("ℹ️ Aucun match en attente")
                return

            updated = 0
            for _, row in df.iterrows():
                surf = row['surface'] if row['surface'] in SURFACE_LABELS else 'Hard'
                p1_rank = int(row['p1_rank']) if row['p1_rank'] else 100
                p2_rank = int(row['p2_rank']) if row['p2_rank'] else 100
                res = self.predict(row['player1'], row['player2'], surf, p1_rank, p2_rank)
                if res['status'] == 'success':
                    c = conn.cursor()
                    c.execute('''UPDATE predictions
                            SET predicted_winner=?, confidence=?,
                                p1_elo=?, p2_elo=?,
                                p1_elo_surface=?, p2_elo_surface=?,
                                p1_momentum=?, p2_momentum=?,
                                h2h_p1_wins=?, h2h_p2_wins=?
                            WHERE id=?''', (
                        res['predicted_winner'],
                        res['confidence'],
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
            conn.commit()
            print(f"✅ {updated} prédictions mises à jour")
        finally:
            conn.close()


if __name__ == "__main__":
    agent = PredictorAgent()
    agent.train()
