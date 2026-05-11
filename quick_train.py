"""
quick_train.py
Entraîne sur un échantillon réduit pour valider le pipeline sans attendre.
Lance depuis la racine : py quick_train.py

Options :
  --size 2000    nombre de matchs (défaut : 3000)
  --no-backtest  skip le backtest
"""

import sys
import argparse
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from database import get_connection

# ─── ARGS ─────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser()
parser.add_argument("--size", type=int, default=3000,
                    help="Nombre de matchs d'entraînement (défaut: 3000)")
parser.add_argument("--no-backtest", action="store_true",
                    help="Skip le backtest")
args = parser.parse_args()

print("=" * 55)
print(f"⚡ QUICK TRAIN — {args.size} matchs")
print("=" * 55)

# ─── IMPORT PREDICTOR ─────────────────────────────────────────────────────

from agents.predictor import PredictorAgent
agent = PredictorAgent()

# ─── CHARGEMENT DONNÉES RÉDUITES ──────────────────────────────────────────

print(f"\n📥 Chargement de {args.size} matchs depuis la DB...")
conn = get_connection()
df = pd.read_sql_query(f"""
    SELECT * FROM matches
    WHERE p1_rank IS NOT NULL
      AND p2_rank IS NOT NULL
      AND surface IN ('Hard', 'Clay', 'Grass')
    ORDER BY date DESC
    LIMIT {args.size}
""", conn)
conn.close()
print(f"   {len(df)} matchs chargés")

# ─── PATCH TEMPORAIRE : injecte les données réduites dans train() ─────────
# On monkey-patche get_connection pour que train() utilise ce sous-ensemble

import sqlite3, tempfile, os

# Crée une DB temporaire en mémoire avec uniquement ce sous-ensemble
print("🔧 Création DB temporaire...")
tmp_db = tempfile.mktemp(suffix=".db")

tmp_conn = sqlite3.connect(tmp_db)
df.to_sql("matches", tmp_conn, if_exists="replace", index=False)

# Table matches_2026 vide (pour que _load_recent() ne plante pas)
tmp_conn.execute("""
    CREATE TABLE IF NOT EXISTS matches_2026 (
        id INTEGER PRIMARY KEY,
        date TEXT, time TEXT, tour TEXT, tournament TEXT, surface TEXT,
        best_of INTEGER, player1 TEXT, player2 TEXT, winner TEXT, score TEXT,
        sets_won_p1 INTEGER, sets_won_p2 INTEGER, num_sets INTEGER,
        odds_p1 REAL, odds_p2 REAL,
        p1_rank INTEGER, p1_points INTEGER, p1_country TEXT,
        p2_rank INTEGER, p2_points INTEGER, p2_country TEXT,
        ranking_date_used TEXT,
        UNIQUE(date, player1, player2, tour)
    )
""")
tmp_conn.execute("CREATE TABLE IF NOT EXISTS elo_ratings (player TEXT PRIMARY KEY, elo_global REAL, elo_hard REAL, elo_clay REAL, elo_grass REAL)")
tmp_conn.commit()
tmp_conn.close()

# Patch get_connection pour pointer vers la DB temporaire
import database
_original_get_connection = database.get_connection

def _patched_get_connection():
    return sqlite3.connect(tmp_db)

database.get_connection = _patched_get_connection
print(f"   DB temporaire : {tmp_db}")

# ─── ENTRAÎNEMENT ─────────────────────────────────────────────────────────

print("\n🧠 Entraînement...")
try:
    accuracy = agent.train()
    print(f"\n✅ Précision : {accuracy:.2%}")
except AttributeError as e:
    print(f"\n❌ AttributeError : {e}")
    print("   → C'est probablement le bug feature_columns dans __init__ ou save_model()")
    database.get_connection = _original_get_connection
    os.unlink(tmp_db)
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Erreur inattendue : {e}")
    import traceback; traceback.print_exc()
    database.get_connection = _original_get_connection
    os.unlink(tmp_db)
    sys.exit(1)

# ─── BACKTEST RAPIDE ──────────────────────────────────────────────────────

if not args.no_backtest and agent.is_trained:
    print("\n📊 Backtest rapide (200 matchs)...")
    from agents.backtester import BacktesterAgent
    bt = BacktesterAgent()
    results = bt.run(test_size=200, predictor=agent)

# ─── TEST PREDICT ─────────────────────────────────────────────────────────

print("\n🎾 Test predict() avec date_limit...")
pred = agent.predict("Novak Djokovic", "Rafael Nadal", "Clay", date_limit="20230101")
if pred:
    print(f"   Gagnant prédit : {pred.get('predicted_winner')}")
    print(f"   Confiance      : {pred.get('confidence')}")
    print(f"   Status         : {pred.get('status')}")
    if pred.get('status') == 'success':
        print("   ✅ predict() fonctionne avec date_limit")
    else:
        print("   ⚠️  Status inattendu")
else:
    print("   ❌ predict() a retourné None")

# ─── NETTOYAGE ────────────────────────────────────────────────────────────

database.get_connection = _original_get_connection
os.unlink(tmp_db)
print(f"\n🗑️  DB temporaire supprimée")

print("\n" + "=" * 55)
print("⚡ Quick train terminé")
print("=" * 55)