import sqlite3
import os
from config import DB_PATH


def init_db():
    """Initialise la base de données SQLite avec le schéma complet"""
    # S'assurer que le dossier data existe
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. Table des matchs historiques
    c.execute('''CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        tournament TEXT,
        player1 TEXT,
        player2 TEXT,
        winner TEXT,
        surface TEXT,
        score TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # 2. Table des prédictions (Correction : ajout de la colonne surface)
    c.execute('''CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        player1 TEXT,
        player2 TEXT,
        surface TEXT,          -- Ajouté pour corriger l'OperationalError
        predicted_winner TEXT,
        confidence REAL,
        actual_winner TEXT,
        correct INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Migration automatique : Si la table existe déjà mais sans la colonne surface
    try:
        c.execute("ALTER TABLE predictions ADD COLUMN surface TEXT")
    except sqlite3.OperationalError:
        # La colonne existe déjà, on ne fait rien
        pass

    # 3. Table des performances de l'algo
    c.execute('''CREATE TABLE IF NOT EXISTS algo_performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version TEXT,
        success_rate REAL,
        total_predictions INTEGER,
        correct_predictions INTEGER,
        date TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()
    print("✅ Base de données initialisée et synchronisée")


def create_tournament_surface_mapping():
    conn = get_connection()
    c = conn.cursor()

    # On crée une table de référence
    c.execute('''CREATE TABLE IF NOT EXISTS tournament_surfaces AS
                     SELECT tournament, surface, COUNT(*) as freq
                     FROM matches
                     WHERE tournament != "" AND surface NOT IN ("", "None", "nan")
                     GROUP BY tournament, surface
                     ORDER BY tournament, freq DESC''')

    # On ne garde que la surface la plus fréquente pour chaque tournoi (doublons de noms)
    c.execute('''CREATE TABLE IF NOT EXISTS tourney_map AS
                     SELECT tournament, surface FROM tournament_surfaces
                     GROUP BY tournament''')

    conn.commit()
    conn.close()
    print("✅ Table de correspondance Tournoi -> Surface créée !")


def get_connection():
    """Retourne une connexion à la base de données"""
    return sqlite3.connect(DB_PATH)


if __name__ == "__main__":
    init_db()
