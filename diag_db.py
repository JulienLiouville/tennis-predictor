import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("data/tennis.db")
conn = sqlite3.connect(DB_PATH)

# 1. Schema de matches_2026
print("=== SCHEMA matches_2026 ===")
schema = pd.read_sql("PRAGMA table_info(matches_2026)", conn)
print(schema[['name', 'type', 'notnull', 'dflt_value']].to_string())

# 2. Comptage brut
print("\n=== ROW COUNT ===")
print(pd.read_sql("SELECT COUNT(*) as total FROM matches_2026", conn))

# 3. Quelques lignes brutes
print("\n=== 5 FIRST ROWS (raw) ===")
print(pd.read_sql("SELECT * FROM matches_2026 LIMIT 5", conn).to_string())

# 4. Combien ont une date non nulle
print("\n=== NON-NULL DATES ===")
print(pd.read_sql("SELECT COUNT(*) as with_date FROM matches_2026 WHERE date IS NOT NULL", conn))

# 5. Idem pour matches (historique)
print("\n=== matches table: count + sample ===")
print(pd.read_sql("SELECT COUNT(*) as total FROM matches", conn))
print(pd.read_sql("SELECT * FROM matches LIMIT 3", conn).to_string())

conn.close()