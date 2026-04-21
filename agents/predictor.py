from datetime import datetime

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import pickle, os
from database import get_connection

class PredictorAgent:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model_path = "data/model.pkl"
        self.le_surface = LabelEncoder()
        self.le_player = LabelEncoder()
        self.is_trained = False
        print("✅ PredictorAgent initialisé")

    def load_training_data(self):
        conn = get_connection()
        df = pd.read_sql_query('''SELECT player1, player2, winner, surface FROM matches WHERE player1 != "" AND player2 != "" AND winner != "" AND surface NOT IN ("", "None") ''', conn)
        conn.close()
        print(f"📊 {len(df)} matchs chargés")
        return df

    def prepare_features(self, df):
        all_players = pd.concat([df["player1"], df["player2"], df["winner"]])
        self.le_player.fit(all_players.unique())
        self.le_surface.fit(df["surface"].unique())
        df = df.copy()
        df["player1_enc"] = self.le_player.transform(df["player1"])
        df["player2_enc"] = self.le_player.transform(df["player2"])
        df["surface_enc"] = self.le_surface.transform(df["surface"])
        df["target"] = (df["player1"] == df["winner"]).astype(int)
        return df[["player1_enc","player2_enc","surface_enc"]], df["target"]

    def train(self):
        print("🧠 Entrainement...")
        df = self.load_training_data()
        if df.empty or len(df) < 100:
            print("❌ Pas assez de données")
            return 0.0
        X, y = self.prepare_features(df)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)
        accuracy = accuracy_score(y_test, self.model.predict(X_test))
        self.is_trained = True
        self.save_model()
        print(f"✅ Précision : {accuracy:.2%}")
        return accuracy

    def predict(self, player1, player2, surface):
        try:
            if not self.is_trained:
                self.load_model()

            # 1. Normalisation de la surface (KISS)
            # On force une surface connue si l'API renvoie None ou une valeur exotique
            if not surface or surface not in self.le_surface.classes_:
                surface = "Hard"  # Surface par défaut la plus commune

            # 2. Gestion des joueurs inconnus (Sécurité)
            known_players = self.le_player.classes_

            # Si un joueur est inconnu, on ne crash pas, on renvoie une proba neutre
            if player1 not in known_players or player2 not in known_players:
                return {
                    "player1": player1, "player2": player2, "surface": surface,
                    "predicted_winner": "Inconnu (Nouveau joueur)",
                    "confidence": 0.50,
                    "above_threshold": False,
                    "status": "unknown_player"
                }

            # 3. Préparation des données (Vérifie bien que l'ordre correspond à l'entraînement)
            features = pd.DataFrame([[
                self.le_player.transform([player1])[0],
                self.le_player.transform([player2])[0],
                self.le_surface.transform([surface])[0]
            ]], columns=["player1_enc", "player2_enc", "surface_enc"])

            # 4. Calcul des probabilités
            proba = self.model.predict_proba(features)[0]

            # Pour un Random Forest, proba[1] est généralement la classe 1 (le gagnant dans ton cas)
            # Mais pour être sûr, on prend l'index de la probabilité max
            winner_idx = np.argmax(proba)
            # On récupère le nom du joueur correspondant à l'index prédit
            # (Attention : cette logique dépend de comment tu as fit ton LabelEncoder)
            predicted_winner = player1 if proba[1] > proba[0] else player2

            confidence = float(max(proba))

            return {
                "player1": player1, "player2": player2, "surface": surface,
                "predicted_winner": predicted_winner,
                "confidence": round(confidence, 4),
                "above_threshold": confidence >= 0.80,
                "status": "success"
            }

        except Exception as e:
            print(f"❌ Erreur lors de la prédiction ({player1} vs {player2}): {e}")
            return {
                "player1": player1, "player2": player2, "surface": surface,
                "predicted_winner": "Erreur",
                "confidence": 0.0,
                "above_threshold": False
            }

    def save_model(self):
        with open(self.model_path, "wb") as f:
            pickle.dump({"model": self.model, "le_player": self.le_player, "le_surface": self.le_surface}, f)
        print("💾 Modèle sauvegardé")

    def load_model(self):
        if os.path.exists(self.model_path):
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
                self.model = data["model"]
                self.le_player = data["le_player"]
                self.le_surface = data["le_surface"]
                self.is_trained = True
            print("✅ Modèle chargé")
        else:
            print("⚠️ Aucun modèle sauvegardé")

    def process_pending_predictions(self):
        """Calcule les prédictions pour les matchs qui n'ont pas encore de vainqueur prédit"""
        print("🧠 Calcul des prédictions pour les matchs du jour...")
        conn = get_connection()
        today = datetime.now().strftime('%Y-%m-%d')

        # On récupère les matchs créés par le LiveCollector qui sont vides
        df_pending = pd.read_sql_query(
            "SELECT id, player1, player2, surface FROM predictions WHERE predicted_winner = '' AND date = ?",
            conn, params=(today,)
        )

        if df_pending.empty:
            print("ℹ️ Aucun match en attente de prédiction.")
            return

        for _, row in df_pending.iterrows():
            # Par défaut le LiveCollector ne connaît pas la surface, on met "Hard" si vide
            surf = row['surface'] if row['surface'] else "Hard"

            res = self.predict(row['player1'], row['player2'], surf)

            if res:
                c = conn.cursor()
                c.execute("""
                    UPDATE predictions 
                    SET predicted_winner = ?, confidence = ?, surface = ?
                    WHERE id = ?
                """, (res['predicted_winner'], res['confidence'], surf, row['id']))

        conn.commit()
        conn.close()
        print(f"✅ {len(df_pending)} prédictions mises à jour.")