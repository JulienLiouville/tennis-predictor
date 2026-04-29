"""
Test rapide du modèle avec isolation temporelle.
Entraînement : 2015-2020
Test         : 2021-2022
Lance depuis la racine : py test_model_range.py
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import LabelEncoder
from database import get_connection
from agents.feature_builder import FeatureBuilder

TRAIN_END = "20210101"   # entraîne sur tout ce qui est < cette date
TEST_START = "20210101"  # teste sur cette période
TEST_END   = "20230101"

FEATURE_COLUMNS = [
    'rank_diff',
    'elo_diff', 'elo_surface_diff',
    'p1_momentum_l5', 'p2_momentum_l5',
    'p1_momentum_l10', 'p2_momentum_l10',
    'h2h_p1_ratio', 'h2h_total',
    'p1_fatigue_7d', 'p2_fatigue_7d',
    'surface_enc', 'best_of',
]

SURFACE_LABELS = ['Hard', 'Clay', 'Grass']
le_surface = LabelEncoder()
le_surface.fit(SURFACE_LABELS)
fb = FeatureBuilder()


def load_matches(date_start=None, date_end=None, limit=None):
    conn = get_connection()
    where = ["player1 != ''", "player2 != ''", "winner != ''",
             "surface IN ('Hard','Clay','Grass')",
             "p1_rank IS NOT NULL", "p2_rank IS NOT NULL"]
    if date_start:
        where.append(f"date >= '{date_start}'")
    if date_end:
        where.append(f"date < '{date_end}'")

    query = f"SELECT * FROM matches WHERE {' AND '.join(where)} ORDER BY date ASC"
    if limit:
        query += f" LIMIT {limit}"

    df = pd.read_sql_query(query, conn)
    conn.close()

    # Déduplication (Sackmann stocke dans les 2 sens)
    df['match_key'] = df.apply(
        lambda r: r['date'] + '_' + '_'.join(sorted([r['player1'], r['player2']])),
        axis=1
    )
    df = df.drop_duplicates(subset=['match_key'])

    # Re-duplication pour avoir les deux classes (winner en p1 et en p2)
    df_inv = df.copy()
    df_inv['player1'] = df['player2']
    df_inv['player2'] = df['player1']
    df_inv['p1_rank'] = df['p2_rank']
    df_inv['p2_rank'] = df['p1_rank']
    df = pd.concat([df, df_inv], ignore_index=True)
    return df


def enrich(df, label=""):
    records = []
    total = len(df)
    print(f"  Enrichissement {label} ({total} matchs)...")
    for i, (_, row) in enumerate(df.iterrows()):
        if i % 1000 == 0:
            print(f"    {i}/{total}...")
        feats = fb.build_features(row['player1'], row['player2'],
                                   row['surface'], row['date'])
        records.append(feats)
    feats_df = pd.DataFrame(records, index=df.index)
    for col in feats_df.columns:
        df[col] = feats_df[col]
    return df


def prepare(df):
    df = df.copy()
    df['target'] = (df['player1'] == df['winner']).astype(int)
    df['surface_enc'] = le_surface.transform(df['surface'])
    df['rank_diff'] = df['p2_rank'] - df['p1_rank']
    df['best_of'] = pd.to_numeric(df['best_of'], errors='coerce').fillna(3)

    # Elo diff depuis elo_ratings (approximation — pas de calcul temporel ici)
    df['elo_diff'] = 0
    df['elo_surface_diff'] = 0

    X = df[FEATURE_COLUMNS].fillna(0)
    y = df['target']
    return X, y


if __name__ == "__main__":
    print("=" * 50)
    print("🧪 TEST MODÈLE SUR RANGE LIMITÉ")
    print(f"   Train : 2015 → {TRAIN_END}")
    print(f"   Test  : {TEST_START} → {TEST_END}")
    print("=" * 50)

    # Chargement — petit subset pour aller vite
    print("\n📥 Chargement train (limit 5000)...")
    df_train = load_matches(date_end=TRAIN_END, limit=5000)
    print(f"   {len(df_train)} matchs train")

    print("\n📥 Chargement test (limit 1000)...")
    df_test = load_matches(date_start=TEST_START, date_end=TEST_END, limit=1000)
    print(f"   {len(df_test)} matchs test")

    # Enrichissement
    df_train = enrich(df_train, "train")
    df_test  = enrich(df_test,  "test")

    # Préparation features
    X_train, y_train = prepare(df_train)
    X_test,  y_test  = prepare(df_test)

    print(f"\n   Classes train : {y_train.value_counts().to_dict()}")
    print(f"   Classes test  : {y_test.value_counts().to_dict()}")

    # Entraînement
    print("\n🧠 Entraînement...")
    model = GradientBoostingClassifier(n_estimators=100, learning_rate=0.05,
                                       max_depth=4, random_state=42)
    model.fit(X_train, y_train)

    # Évaluation
    acc = accuracy_score(y_test, model.predict(X_test))
    probas = model.predict_proba(X_test)
    confidence = probas.max(axis=1)

    high_conf = confidence >= 0.80
    if high_conf.sum() > 0:
        acc_high = accuracy_score(y_test[high_conf], model.predict(X_test)[high_conf])
    else:
        acc_high = 0.0

    print(f"\n{'='*50}")
    print(f"📊 RÉSULTATS")
    print(f"{'='*50}")
    print(f"Précision globale   : {acc:.2%}")
    print(f"Prédictions >80%    : {high_conf.sum()} / {len(y_test)}")
    print(f"Précision sur >80%  : {acc_high:.2%}")

    # Feature importance
    print(f"\n📊 Top features :")
    for name, imp in sorted(zip(FEATURE_COLUMNS, model.feature_importances_),
                            key=lambda x: x[1], reverse=True):
        print(f"   {name:30s} {imp:.4f}")

    print("\n✅ Test terminé")
    if acc > 0.95:
        print("⚠️  Précision > 95% — data leakage probable, vérifier")
    elif 0.60 <= acc <= 0.80:
        print("✅ Précision dans la plage attendue sans leakage")
    else:
        print(f"ℹ️  Précision {acc:.2%} — à analyser")