import sqlite3
from pathlib import Path

conn = sqlite3.connect("data/tennis.db")

for table in ("match_features", "matches_2026"):
    print(f"\n=== PRAGMA {table} ===")
    for row in conn.execute(f"PRAGMA table_info({table})"):
        print(row)

# Range des IDs dans chaque table
print("\n=== ID ranges ===")
print("matches:     ", conn.execute("SELECT MIN(id), MAX(id) FROM matches").fetchone())
print("matches_2026:", conn.execute("SELECT MIN(id), MAX(id) FROM matches_2026").fetchone())
print("match_features:", conn.execute("SELECT MIN(match_id), MAX(match_id) FROM match_features").fetchone())

conn.close()