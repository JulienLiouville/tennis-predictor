import sqlite3
from config import DB_PATH

def init_db():
    """Initialise la base de données SQLite"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Table des matchs historiques
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

    # Table des prédictions
    c.execute('''CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        player1 TEXT,
        player2 TEXT,
        predicted_winner TEXT,
        confidence REAL,
        actual_winner TEXT,
        correct INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Table des performances de l'algo
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
    print("✅ Base de données initialisée")

def get_connection():
    return sqlite3.connect(DB_PATH)

if __name__ == "__main__":
    init_db()
