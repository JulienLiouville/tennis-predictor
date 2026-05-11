import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score

DB_PATH = Path("data/tennis.db")


class ValidationReport:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.successes = []

    def success(self, message):
        print(f"✅ {message}")
        self.successes.append(message)

    def warning(self, message):
        print(f"⚠️  {message}")
        self.warnings.append(message)

    def issue(self, message):
        print(f"❌ {message}")
        self.issues.append(message)

    def summary(self):
        print("\n" + "=" * 70)
        print("📊 VALIDATION SUMMARY")
        print("=" * 70)
        print(f"✅ Successes : {len(self.successes)}")
        print(f"⚠️  Warnings : {len(self.warnings)}")
        print(f"❌ Issues    : {len(self.issues)}")

        if self.issues:
            print("\n🚨 CRITICAL ISSUES:")
            for issue in self.issues:
                print(f"- {issue}")


report = ValidationReport()


def get_connection():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    return sqlite3.connect(DB_PATH)


# ============================================================
# DATABASE CHECKS
# ============================================================

def check_tables(conn):
    print("\n🔍 Checking database tables...")

    expected_tables = [
        'matches',
        'matches_2026',
        'match_features',
        'players_rankings',
        'predictions'
    ]

    query = "SELECT name FROM sqlite_master WHERE type='table'"
    existing = pd.read_sql(query, conn)['name'].tolist()

    for table in expected_tables:
        if table in existing:
            report.success(f"Table exists: {table}")
        else:
            report.issue(f"Missing table: {table}")


# ============================================================
# SURFACE CHECKS
# ============================================================

def check_surfaces(conn):
    print("\n🎾 Checking surfaces...")

    query = """
    SELECT surface, COUNT(*) as count
    FROM matches_2026
    GROUP BY surface
    ORDER BY count DESC
    """

    df = pd.read_sql(query, conn)

    print(df)

    null_query = """
    SELECT COUNT(*) as count
    FROM matches_2026
    WHERE surface IS NULL
       OR surface = 'Unknown'
    """

    null_count = pd.read_sql(null_query, conn)['count'].iloc[0]

    if null_count > 0:
        report.issue(f"{null_count} matches with NULL/Unknown surfaces")
    else:
        report.success("All recent matches have valid surfaces")


# ============================================================
# DUPLICATE CHECKS
# ============================================================

def check_duplicates(conn):
    print("\n🧬 Checking duplicates...")

    query = """
    SELECT date, player1, player2, COUNT(*) as c
    FROM matches_2026
    GROUP BY date, player1, player2
    HAVING c > 1
    LIMIT 10
    """

    df = pd.read_sql(query, conn)

    if len(df) > 0:
        report.issue(f"Found {len(df)} duplicate recent matches")
        print(df)
    else:
        report.success("No duplicate recent matches found")


# ============================================================
# RANKING CHECKS
# ============================================================

def check_rankings(conn):
    print("\n🏆 Checking rankings...")

    query = """
    SELECT COUNT(*) as count
    FROM matches_2026
    WHERE p1_rank IS NULL
       OR p2_rank IS NULL
    """

    missing = pd.read_sql(query, conn)['count'].iloc[0]

    if missing > 0:
        report.warning(f"{missing} matches have missing rankings")
    else:
        report.success("All recent matches have rankings")


# ============================================================
# FEATURE CHECKS
# ============================================================

def check_features(conn):
    print("\n🧠 Checking features...")

    query = "SELECT COUNT(*) as count FROM match_features"
    total = pd.read_sql(query, conn)['count'].iloc[0]

    if total == 0:
        report.issue("match_features table is empty")
        return

    report.success(f"match_features contains {total} rows")

    feature_query = """
    SELECT *
    FROM match_features
    LIMIT 10000
    """

    df = pd.read_sql(feature_query, conn)

    columns_to_check = [
        'p1_momentum_l5',
        'p1_momentum_l10',
        'h2h_p1_ratio',
        'p1_fatigue_7d'
    ]

    for col in columns_to_check:
        if col not in df.columns:
            report.issue(f"Missing feature column: {col}")
            continue

        unique_values = df[col].nunique()
        std = df[col].std()

        print(f"\n📈 {col}")
        print(df[col].describe())

        if unique_values <= 2:
            report.warning(f"{col} has very low variability")

        if std == 0:
            report.issue(f"{col} is constant")


# ============================================================
# NAME NORMALIZATION CHECKS
# ============================================================

def check_names(conn):
    print("\n👤 Checking player names...")

    query = """
    SELECT player1
    FROM matches_2026
    WHERE player1 LIKE '%.%'
    LIMIT 20
    """

    df = pd.read_sql(query, conn)

    if len(df) > 0:
        report.warning("Found abbreviated player names")
        print(df)
    else:
        report.success("Player names appear normalized")


# ============================================================
# TEMPORAL LEAKAGE CHECKS
# ============================================================

def check_temporal_leakage(conn):
    print("\n⏳ Checking temporal consistency...")

    query = """
    SELECT COUNT(*) as count
    FROM matches_2026 m
    JOIN players_rankings r
        ON m.player1 = r.name
    WHERE r.date_recorded > m.date
    """

    try:
        count = pd.read_sql(query, conn)['count'].iloc[0]

        if count > 0:
            report.issue(f"{count} ranking records use future data")
        else:
            report.success("No obvious ranking leakage detected")

    except Exception as e:
        report.warning(f"Temporal leakage check failed: {e}")


# ============================================================
# MODEL SIGNAL CHECK
# ============================================================

def check_model_signal(conn):
    print("\n🤖 Checking model signal...")

    query = """
    SELECT
        m.p1_rank,
        m.p2_rank,
        CASE WHEN m.player1 = m.winner THEN 1 ELSE 0 END as target
    FROM matches_2026 m
    WHERE m.p1_rank IS NOT NULL
      AND m.p2_rank IS NOT NULL
      AND m.winner IS NOT NULL
    LIMIT 10000
    """



    df = pd.read_sql(query, conn)

    if len(df) < 100:
        report.warning("Not enough data for signal validation")
        return

    df['rank_diff'] = df['p2_rank'] - df['p1_rank']

    X = df[['rank_diff']]
    y = df['target']

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42
    )

    model = GradientBoostingClassifier()

    print("\n========== DEBUG TARGET ==========")

    print("\nFULL TARGET:")
    print(y.value_counts(dropna=False))

    print("\nTRAIN TARGET:")
    print(y_train.value_counts(dropna=False))

    print("\nTEST TARGET:")
    print(y_test.value_counts(dropna=False))

    print("\nSHAPES:")
    print("X_train:", X_train.shape)
    print("y_train:", y_train.shape)

    print("\nUNIQUE VALUES:")
    print(y_train.unique())

    print("\n==================================")

    model.fit(X_train, y_train)

    preds = model.predict(X_test)

    acc = accuracy_score(y_test, preds)

    print(f"\n📊 Rank-only accuracy: {acc:.4f}")


    if acc > 0.72:
        report.warning(
            "Ranking alone is extremely predictive. "
            "Model may mostly learn rankings."
        )
    else:
        report.success("Model likely uses more than ranking alone")


# ============================================================
# TEMPORAL SPLIT VALIDATION
# ============================================================

def check_temporal_split(conn):
    print("\n📅 Checking temporal split feasibility...")

    query = """
    SELECT date
    FROM matches_2026
    ORDER BY date
    """

    df = pd.read_sql(query, conn)

    if len(df) == 0:
        report.issue("No recent matches found")
        return

    print(f"First recent match : {df['date'].min()}")
    print(f"Last recent match  : {df['date'].max()}")

    report.success("Temporal split appears feasible")


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 70)
    print("🎾 TENNIS PREDICTOR — FULL VALIDATION")
    print("=" * 70)

    conn = get_connection()

    try:
        check_tables(conn)
        check_surfaces(conn)
        check_duplicates(conn)
        check_rankings(conn)
        check_features(conn)
        check_names(conn)
        check_temporal_leakage(conn)
        check_model_signal(conn)
        check_temporal_split(conn)

    finally:
        conn.close()

    report.summary()


if __name__ == '__main__':
    main()
