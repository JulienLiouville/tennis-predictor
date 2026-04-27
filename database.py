import sqlite3
import os
from config import DB_PATH


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()

        c.execute('''CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT, tournament TEXT, tourney_level TEXT,
            surface TEXT, round TEXT, best_of INTEGER,
            player1 TEXT, player2 TEXT, winner TEXT, score TEXT,
            p1_rank INTEGER, p1_rank_points INTEGER, p1_age REAL,
            p1_hand TEXT, p1_height INTEGER,
            p2_rank INTEGER, p2_rank_points INTEGER, p2_age REAL,
            p2_hand TEXT, p2_height INTEGER,
            p1_ace INTEGER, p1_df INTEGER, p1_svpt INTEGER,
            p1_1stIn INTEGER, p1_1stWon INTEGER, p2ndWon INTEGER,
            p1_SvGms INTEGER, p1_bpSaved INTEGER, p1_bpFaced INTEGER,
            p2_ace INTEGER, p2_df INTEGER, p2_svpt INTEGER,
            p2_1stIn INTEGER, p2_1stWon INTEGER, p2_2ndWon INTEGER,
            p2_SvGms INTEGER, p2_bpSaved INTEGER, p2_bpFaced INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_matches_player1 ON matches(player1)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_matches_player2 ON matches(player2)')

        c.execute('''CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT, tournament TEXT, surface TEXT,
            player1 TEXT, player2 TEXT,
            predicted_winner TEXT, confidence REAL,
            p1_elo REAL, p2_elo REAL,
            p1_elo_surface REAL, p2_elo_surface REAL,
            p1_momentum REAL, p2_momentum REAL,
            h2h_p1_wins INTEGER, h2h_p2_wins INTEGER,
            actual_winner TEXT, correct INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS elo_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player TEXT UNIQUE,
            elo_global REAL DEFAULT 1500,
            elo_hard REAL DEFAULT 1500,
            elo_clay REAL DEFAULT 1500,
            elo_grass REAL DEFAULT 1500,
            matches_played INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS algo_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT, success_rate REAL,
            total_predictions INTEGER, correct_predictions INTEGER,
            date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS tournament_surfaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_key TEXT UNIQUE,
            tournament_name TEXT, surface TEXT, source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        _run_migrations(c)
        conn.commit()
        print("✅ Base de données initialisée et synchronisée")
    finally:
        conn.close()


def _run_migrations(c):
    new_columns = [
        ("matches", "tourney_level", "TEXT"),
        ("matches", "round", "TEXT"),
        ("matches", "best_of", "INTEGER"),
        ("matches", "p1_rank", "INTEGER"),
        ("matches", "p2_rank", "INTEGER"),
        ("matches", "p1_rank_points", "INTEGER"),
        ("matches", "p2_rank_points", "INTEGER"),
        ("matches", "p1_age", "REAL"),
        ("matches", "p2_age", "REAL"),
        ("matches", "p1_hand", "TEXT"),
        ("matches", "p2_hand", "TEXT"),
        ("matches", "p1_height", "INTEGER"),
        ("matches", "p2_height", "INTEGER"),
        ("matches", "p1_ace", "INTEGER"),
        ("matches", "p1_df", "INTEGER"),
        ("matches", "p1_svpt", "INTEGER"),
        ("matches", "p1_1stIn", "INTEGER"),
        ("matches", "p1_1stWon", "INTEGER"),
        ("matches", "p2ndWon", "INTEGER"),
        ("matches", "p1_SvGms", "INTEGER"),
        ("matches", "p1_bpSaved", "INTEGER"),
        ("matches", "p1_bpFaced", "INTEGER"),
        ("matches", "p2_ace", "INTEGER"),
        ("matches", "p2_df", "INTEGER"),
        ("matches", "p2_svpt", "INTEGER"),
        ("matches", "p2_1stIn", "INTEGER"),
        ("matches", "p2_1stWon", "INTEGER"),
        ("matches", "p2_2ndWon", "INTEGER"),
        ("matches", "p2_SvGms", "INTEGER"),
        ("matches", "p2_bpSaved", "INTEGER"),
        ("matches", "p2_bpFaced", "INTEGER"),
        ("predictions", "surface", "TEXT"),
        ("predictions", "p1_elo", "REAL"),
        ("predictions", "p2_elo", "REAL"),
        ("predictions", "p1_elo_surface", "REAL"),
        ("predictions", "p2_elo_surface", "REAL"),
        ("predictions", "p1_momentum", "REAL"),
        ("predictions", "p2_momentum", "REAL"),
        ("predictions", "h2h_p1_wins", "INTEGER"),
        ("predictions", "h2h_p2_wins", "INTEGER"),
    ]
    for table, col, col_type in new_columns:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


if __name__ == "__main__":
    init_db()