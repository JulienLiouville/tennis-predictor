import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import pickle
import os
from database import get_connection
from feature_builder import FeatureBuilder


class PredictorAgent:
    def __init__(self):
        # GradientBoosting >> RandomForest sur ce type de données
        self.model = GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=4,
            random_state=42
        )
        self.model_path = "data/model.pkl"
        self.le_surface = LabelEncoder()
        self.feature_builder = FeatureBuilder()
        self.is_trained = False
        self.feature_columns = []
        print("✅ PredictorAgent initialisé")

    def load_training_data(self):
        conn = get_connection()
        try:
            df = pd.read_sql_query('''
                SELECT player1, player2, winner, surface,
                       p1_rank, p2_rank,
                       p1_ace, p1_df, p1_svpt, p1_1stIn, p1_1stWon,
                       p2ndWon, p1_bpSaved, p1_bpFaced,
                       p2_ace, p2_df, p2_svpt, p2_1stIn, p2_1stWon,
                       p2_2ndWon, p2_bpSaved, p2_bpFaced,
                       tourney_level, best_of, date
                FROM matches
                WHERE player1 != "" AND player2 != ""
                AND winner != ""
                AND surface IN ("Hard", "Clay", "Grass")
            ''', conn)
            print(f"📊 {len(df)} matchs chargés")
            return df
        finally:
            conn.close()

    def prepare_features(self, df):
        """Prépare les features enrichies pour l'entraînement"""
        print("🔧 Calcul des features enrichies...")

        # Surface encodée
        self.le_surface.fit(['Hard', 'Clay', 'Grass'])
        df['surface_enc'] = self.le_surface.transform(df['surface'])

        # Target
        df['target'] = (df['player1'] == df['winner']).astype(int)

        # Différence de ranking (très prédictive)
        df['rank_diff'] = df['p2_rank'].fillna(200) - df['p1_rank'].fillna(200)

        # Stats de service joueur 1
        df['p1_1st_serve_pct'] = (df['p1_1stIn'] / df['p1_svpt'].replace(0, np.nan)).fillna(0.6)
        df['p1_1st_won_pct'] = (df['p1_1stWon'] / df['p1_1stIn'].replace(0, np.nan)).fillna(0.7)
        df['p1_2nd_won_pct'] = (df['p2ndWon'] / (df['p1_svpt'] - df['p1_1stIn']).replace(0, np.nan)).fillna(0.5)
        df['p1_bp_saved_pct'] = (df['p1_bpSaved'] / df['p1_bpFaced'].replace(0, np.nan)).fillna(0.6)

        # Stats de service joueur 2
        df['p2_1st_serve_pct'] = (df['p2_1stIn'] / df['p2_svpt'].replace(0, np.nan)).fillna(0.6)
        df['p2_1st_won_pct'] = (df['p2_1stWon'] / df['p2_1stIn'].replace(0, np.nan)).fillna(0.7)
        df['p2_2nd_won_pct'] = (df['p2_2ndWon'] / (df['p2_svpt'] - df['p2_1stIn']).replace(0, np.nan)).fillna(0.5)
        df['p2_bp_saved_pct'] = (df['p2_bpSaved'] / df['p2_bpFaced'].replace(0, np.nan)).fillna(0.6)

        # Dominance Ratio approximatif
        df['p1_dr'] = df['p1_1st_won_pct'] - df['p2_1st_won_pct']

        # Niveau tournoi encodé
        level_map = {'G': 4, 'M': 3, 'A': 2, 'D': 1, 'F': 3}
        df['tourney_level_enc'] = df['tourney_level'].map(level_map).fillna(2)

        # Best of
        df['best_of'] = df['best_of'].fillna(3)

        self.feature_columns = [
            'surface_enc', 'rank_diff', 'tourney_level_enc', 'best_of',
            'p1_1st_serve_pct', 'p1_1st_won_pct', 'p1_2nd_won_pct', 'p1_bp_saved_pct',
            'p2_1st_serve_pct', 'p2_1st_won_pct', 'p2_2nd_won_pct', 'p2_bp_saved_pct',
            'p1_dr',
            'p1_ace', 'p2_ace', 'p1_df', 'p2_df',
        ]

        # Remplace NaN par 0
        X = df[self.feature_columns].fillna(0)
        y = df['target']
        return X, y

    def train(self):
        print("🧠 Entrainement...")
        df = self.load_training_data()
        if df.empty or len(df) < 100:
            print("❌ Pas assez de données")
            return 0.0

        X, y = self.prepare_features(df)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        self.model.fit(X_train, y_train)
        accuracy = accuracy_score(y_test, self.model.predict(X_test))
        self.is_trained = True
        self.save_model()
        print(f"✅ Précision : {accuracy:.2%}")
        return accuracy

    def predict(self, player1: str, player2: str, surface: str,
                p1_rank: int = 100, p2_rank: int = 100) -> dict:
        try:
            if not self.is_trained:
                self.load_model()

            # Récupère les features dynamiques
            features = self.feature_builder.build_features(player1, player2, surface)

            # Surface encodée
            if surface not in self.le_surface.classes_:
                surface = 'Hard'
            surface_enc = self.le_surface.transform([surface])[0]

            rank_diff = p2_rank - p1_rank

            # Vecteur de features (ordre identique à l'entraînement)
            X = pd.DataFrame([[
                surface_enc, rank_diff, 2, 3,
                0.6, 0.7, 0.5, 0.6,
                0.6, 0.7, 0.5, 0.6,
                features['elo_surface_diff'] / 400,
                0, 0, 0, 0,
            ]], columns=self.feature_columns)

            proba = self.model.predict_proba(X)[0]
            confidence = float(max(proba))
            predicted_winner = player1 if proba[1] > proba[0] else player2

            return {
                "player1": player1,
                "player2": player2,
                "surface": surface,
                "predicted_winner": predicted_winner,
                "confidence": round(confidence, 4),
                "above_threshold": confidence >= 0.80,
                "features": features,
                "status": "success"
            }

        except Exception as e:
            print(f"❌ Erreur prédiction ({player1} vs {player2}): {e}")
            return {
                "player1": player1, "player2": player2, "surface": surface,
                "predicted_winner": "Erreur", "confidence": 0.0,
                "above_threshold": False, "status": "error"
            }

    def save_model(self):
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
            print("⚠️ Aucun modèle sauvegardé")

    def process_pending_predictions(self):
        """Calcule les prédictions pour les matchs du jour sans prédiction"""
        from datetime import datetime
        print("🧠 Calcul des prédictions pour les matchs du jour...")
        conn = get_connection()
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            df = pd.read_sql_query(
                "SELECT id, player1, player2, surface FROM predictions WHERE predicted_winner = '' AND date = ?",
                conn, params=(today,)
            )
            if df.empty:
                print("ℹ️ Aucun match en attente")
                return

            for _, row in df.iterrows():
                surf = row['surface'] if row['surface'] else "Hard"
                res = self.predict(row['player1'], row['player2'], surf)
                if res:
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
            conn.commit()
            print(f"✅ {len(df)} prédictions mises à jour")
        finally:
            conn.close()


if __name__ == "__main__":
    agent = PredictorAgent()
    agent.train()