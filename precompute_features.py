"""
precompute_features_2026.py

Calcule les features (momentum, H2H, fatigue) pour matches_2026
et les insère dans match_features — même table, pas de collision d'IDs
car matches_2026.id commence à 518533.

L'historique utilisé pour les calculs = matches (Sackmann) + matches_2026,
triés chronologiquement, pour que les matchs récents bénéficient du
contexte complet.

Usage :
    python precompute_features_2026.py
    python precompute_features_2026.py --reset   # recalcule tout
"""

import argparse
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from database import get_connection

parser = argparse.ArgumentParser()
parser.add_argument('--reset', action='store_true', help='Supprime les features 2026 et recalcule')
args = parser.parse_args()


# ─── CHARGEMENT ───────────────────────────────────────────────────────────────

def load_targets(conn) -> pd.DataFrame:
    """Matchs 2026 à calculer (player1 = toujours le gagnant dans ce dataset)."""
    return pd.read_sql_query('''
        SELECT id, date, player1, player2, surface, winner
        FROM matches_2026
        WHERE player1 IS NOT NULL AND player1 != ''
          AND player2 IS NOT NULL AND player2 != ''
          AND winner IS NOT NULL AND winner != ''
          AND surface IN ('Hard', 'Clay', 'Grass')
        ORDER BY date ASC
    ''', conn)


def load_history(conn) -> pd.DataFrame:
    """
    Historique complet = Sackmann + matches_2026, dédupliqué.
    Utilisé comme contexte pour calculer momentum/H2H/fatigue.
    On prend uniquement les colonnes nécessaires.
    """
    df_hist = pd.read_sql_query('''
        SELECT date, player1, player2, winner FROM matches
        WHERE player1 != '' AND player2 != '' AND winner != ''
        ORDER BY date ASC
    ''', conn)

    df_recent = pd.read_sql_query('''
        SELECT date, player1, player2, winner FROM matches_2026
        WHERE player1 IS NOT NULL AND player1 != ''
          AND player2 IS NOT NULL AND player2 != ''
          AND winner IS NOT NULL AND winner != ''
        ORDER BY date ASC
    ''', conn)

    df = pd.concat([df_hist, df_recent], ignore_index=True)

    # Normalise le format de date (matches = YYYYMMDD, matches_2026 = YYYY-MM-DD)
    df['date_norm'] = df['date'].astype(str).str.replace('-', '', regex=False).str[:8]

    # Clé de déduplication
    df['match_key'] = (
        df['date_norm'] + '_' +
        df[['player1', 'player2']].apply(
            lambda r: '_'.join(sorted([str(r['player1']), str(r['player2'])])), axis=1
        )
    )
    df = df.drop_duplicates(subset=['match_key']).reset_index(drop=True)
    print(f"   Historique chargé : {len(df)} matchs uniques")
    return df


# ─── INDEX ────────────────────────────────────────────────────────────────────

def build_player_index(hist: pd.DataFrame) -> dict:
    print("📦 Index joueurs...")
    index = {}
    for _, row in hist.iterrows():
        for player in [row['player1'], row['player2']]:
            if player not in index:
                index[player] = []
            index[player].append({
                'date_norm': row['date_norm'],
                'winner': row['winner'],
                'player1': row['player1'],
                'player2': row['player2'],
            })
    result = {
        p: pd.DataFrame(rows).sort_values('date_norm').reset_index(drop=True)
        for p, rows in index.items()
    }
    print(f"   {len(result)} joueurs indexés")
    return result


def build_pair_index(hist: pd.DataFrame) -> dict:
    print("📦 Index H2H...")
    index = {}
    for _, row in hist.iterrows():
        key = frozenset([row['player1'], row['player2']])
        if key not in index:
            index[key] = []
        index[key].append({'date_norm': row['date_norm'], 'winner': row['winner']})
    result = {
        k: pd.DataFrame(rows).sort_values('date_norm').reset_index(drop=True)
        for k, rows in index.items()
    }
    print(f"   {len(result)} paires indexées")
    return result


# ─── CALCULS ──────────────────────────────────────────────────────────────────

def momentum(player_df: pd.DataFrame, player: str, date_cut: str, n: int) -> float:
    past = player_df[player_df['date_norm'] < date_cut].tail(n)
    if past.empty:
        return 0.5
    return round((past['winner'] == player).sum() / len(past), 4)


def fatigue(player_df: pd.DataFrame, date_cut: str, days: int = 7) -> int:
    ref = datetime.strptime(date_cut, '%Y%m%d')
    cutoff = (ref - timedelta(days=days)).strftime('%Y%m%d')
    past = player_df[
        (player_df['date_norm'] >= cutoff) &
        (player_df['date_norm'] < date_cut)
    ]
    return len(past)


def h2h(pair_df: pd.DataFrame, p1: str, date_cut: str) -> tuple:
    past = pair_df[pair_df['date_norm'] < date_cut]
    total = len(past)
    p1_wins = (past['winner'] == p1).sum()
    ratio = round(p1_wins / total, 4) if total > 0 else 0.5
    return int(p1_wins), total, ratio


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    conn = get_connection()

    if args.reset:
        # Supprime uniquement les features des matchs_2026 (IDs >= 518533)
        deleted = conn.execute(
            "DELETE FROM match_features WHERE match_id >= 518533"
        ).rowcount
        conn.commit()
        print(f"🗑️  {deleted} features 2026 supprimées")

    # IDs déjà calculés
    done_ids = set(
        row[0] for row in conn.execute(
            "SELECT match_id FROM match_features WHERE match_id >= 518533"
        ).fetchall()
    )
    print(f"   {len(done_ids)} matchs 2026 déjà calculés → skip")

    df_targets = load_targets(conn)
    df_targets = df_targets[~df_targets['id'].isin(done_ids)]
    print(f"   {len(df_targets)} matchs 2026 à calculer")

    if df_targets.empty:
        print("✅ Tout est déjà calculé")
        conn.close()
        return

    hist = load_history(conn)
    player_idx = build_player_index(hist)
    pair_idx   = build_pair_index(hist)

    n = len(df_targets)
    batch = []
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print(f"\n⚙️  Calcul des features ({n} matchs)...")

    for i, (_, row) in enumerate(df_targets.iterrows()):
        if i % 2000 == 0:
            print(f"   {i}/{n}...")
            if batch:
                conn.executemany('''
                    INSERT OR IGNORE INTO match_features
                    (match_id, p1_momentum_l5, p1_momentum_l10,
                     p2_momentum_l5, p2_momentum_l10,
                     h2h_p1_ratio, h2h_total,
                     p1_fatigue_7d, p2_fatigue_7d, computed_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                ''', batch)
                conn.commit()
                batch = []

        p1 = str(row['player1'])
        p2 = str(row['player2'])
        # matches_2026 dates sont YYYY-MM-DD
        date_cut = str(row['date']).replace('-', '')[:8]

        p1_df    = player_idx.get(p1, pd.DataFrame())
        p2_df    = player_idx.get(p2, pd.DataFrame())
        pair_key = frozenset([p1, p2])
        pair_df  = pair_idx.get(pair_key, pd.DataFrame())

        p1_m5  = momentum(p1_df, p1, date_cut, 5)  if not p1_df.empty else 0.5
        p1_m10 = momentum(p1_df, p1, date_cut, 10) if not p1_df.empty else 0.5
        p2_m5  = momentum(p2_df, p2, date_cut, 5)  if not p2_df.empty else 0.5
        p2_m10 = momentum(p2_df, p2, date_cut, 10) if not p2_df.empty else 0.5
        fat1   = fatigue(p1_df, date_cut)           if not p1_df.empty else 0
        fat2   = fatigue(p2_df, date_cut)           if not p2_df.empty else 0
        _, h2h_tot, h2h_rat = h2h(pair_df, p1, date_cut) if not pair_df.empty else (0, 0, 0.5)

        batch.append((
            int(row['id']),
            p1_m5, p1_m10, p2_m5, p2_m10,
            h2h_rat, h2h_tot, fat1, fat2, now
        ))

    # Flush final
    if batch:
        conn.executemany('''
            INSERT OR IGNORE INTO match_features
            (match_id, p1_momentum_l5, p1_momentum_l10,
             p2_momentum_l5, p2_momentum_l10,
             h2h_p1_ratio, h2h_total,
             p1_fatigue_7d, p2_fatigue_7d, computed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        ''', batch)
        conn.commit()

    total_2026 = conn.execute(
        "SELECT COUNT(*) FROM match_features WHERE match_id >= 518533"
    ).fetchone()[0]
    total_all = conn.execute(
        "SELECT COUNT(*) FROM match_features"
    ).fetchone()[0]

    print(f"\n✅ Terminé")
    print(f"   Features 2026 : {total_2026}")
    print(f"   Total match_features : {total_all}")
    conn.close()


if __name__ == '__main__':
    main()