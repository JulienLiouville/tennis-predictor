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
        df = pd.read_sql_query('''SELECT player1, player2, winner, surface FROM matches WHERE player1 != "" AND player2 != "" AND winner != "" AND surface NOT IN ("", "None") LIMIT 50000''', conn)
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
        if not self.is_trained:
            self.load_model()
        try:
            if player1 not in self.le_player.classes_ or player2 not in self.le_player.classes_:
                print(f"⚠️ Joueur inconnu")
                return {}
            if surface not in self.le_surface.classes_:
                print(f"⚠️ Surface inconnue")
                return {}
            features = pd.DataFrame([[
                self.le_player.transform([player1])[0],
                self.le_player.transform([player2])[0],
                self.le_surface.transform([surface])[0]
            ]], columns=["player1_enc","player2_enc","surface_enc"])
            proba = self.model.predict_proba(features)[0]
            confidence = max(proba)
            return {
                "player1": player1, "player2": player2, "surface": surface,
                "predicted_winner": player1 if proba[1] > proba[0] else player2,
                "confidence": round(confidence, 4),
                "above_threshold": confidence >= 0.80
            }
        except Exception as e:
            print(f"❌ {e}")
            return {}

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