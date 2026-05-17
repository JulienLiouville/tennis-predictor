"""
precompute_features.py

Calcule toutes les features (momentum, H2H, fatigue) UNE SEULE FOIS
et les stocke dans match_features.

Couvre matches (Sackmann) ET matches_2026 — même script, même table.
Les IDs ne se chevauchent pas (matches: 1-386666, matches_2026: 518533+).

Optimisations RAM vs version originale :
- Index joueur/paire = listes de tuples au lieu de DataFrames  → -70% RAM
- load_history() retourne des listes directement, pas de DataFrame global
- Pas de pandas dans les boucles de calcul

Usage :
  python3 precompute_features.py              # calcul complet
  python3 precompute_features.py --test 500   # test rapide
  python3 precompute_features.py --reset      # repart de zéro
"""

import argparse
import sqlite3
from datetime import datetime, timedelta
from database import get_connection

parser = argparse.ArgumentParser()
parser.add_argument('--test',  type=int, default=0,     help='Limite pour test rapide')
parser.add_argument('--reset', action='store_true',     help='Recrée la table from scratch')
args = parser.parse_args()


# ─── TABLE ────────────────────────────────────────────────────────────────────

def create_table(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS match_features (
            match_id         INTEGER PRIMARY KEY,
            p1_momentum_l5   REAL,
            p1_momentum_l10  REAL,
            p2_momentum_l5   REAL,
            p2_momentum_l10  REAL,
            h2h_p1_ratio     REAL,
            h2h_total        INTEGER,
            p1_fatigue_7d    INTEGER,
            p2_fatigue_7d    INTEGER,
            computed_at      TEXT
        )
    ''')
    if args.reset:
        conn.execute('DELETE FROM match_features')
        print("🗑️  Table match_features vidée")
    conn.commit()


# ─── CHARGEMENT ───────────────────────────────────────────────────────────────

def load_targets(conn, limit=0):
    """
    Matchs à calculer = matches + matches_2026, filtrés sur les critères qualité.
    Retourne une liste de tuples (id, date_norm, player1, player2).
    """
    rows = []

    q_hist = '''
        SELECT id, date, player1, player2
        FROM matches
        WHERE player1 != "" AND player2 != "" AND winner != ""
          AND surface IN ("Hard", "Clay", "Grass")
          AND p1_rank IS NOT NULL AND p2_rank IS NOT NULL
        ORDER BY date ASC
    '''
    if limit:
        q_hist += f' LIMIT {limit}'

    for row in conn.execute(q_hist):
        date_norm = str(row[1]).replace('-', '')[:8]
        rows.append((row[0], date_norm, row[2], row[3]))

    if not limit:
        q_recent = '''
            SELECT id, date, player1, player2
            FROM matches_2026
            WHERE player1 IS NOT NULL AND player1 != ""
              AND player2 IS NOT NULL AND player2 != ""
              AND winner IS NOT NULL AND winner != ""
              AND surface IN ("Hard", "Clay", "Grass")
            ORDER BY date ASC
        '''
        for row in conn.execute(q_recent):
            date_norm = str(row[1]).replace('-', '')[:8]
            rows.append((row[0], date_norm, row[2], row[3]))

    return rows


def load_history(conn):
    """
    Charge l'historique complet (matches + matches_2026) sous forme de
    structures légères pour minimiser la RAM.

    Retourne :
        player_idx : dict[player -> list[(date_norm, winner, opponent)]]
        pair_idx   : dict[frozenset -> list[(date_norm, winner)]]
    """
    print("📦 Chargement historique...")

    player_idx = {}
    pair_idx   = {}
    seen       = set()

    def _add(date_norm, p1, p2, winner):
        key = (date_norm, p1, p2)
        if key in seen:
            return
        seen.add(key)

        # Index joueur : tuple (date_norm, winner, opponent)
        for player, opponent in [(p1, p2), (p2, p1)]:
            if player not in player_idx:
                player_idx[player] = []
            player_idx[player].append((date_norm, winner, opponent))

        # Index paire
        pk = frozenset([p1, p2])
        if pk not in pair_idx:
            pair_idx[pk] = []
        pair_idx[pk].append((date_norm, winner))

    for row in conn.execute('''
        SELECT date, player1, player2, winner FROM matches
        WHERE player1 != "" AND player2 != "" AND winner != ""
        ORDER BY date ASC
    '''):
        date_norm = str(row[0]).replace('-', '')[:8]
        _add(date_norm, row[1], row[2], row[3])

    for row in conn.execute('''
        SELECT date, player1, player2, winner FROM matches_2026
        WHERE player1 IS NOT NULL AND player1 != ""
          AND player2 IS NOT NULL AND player2 != ""
          AND winner IS NOT NULL AND winner != ""
        ORDER BY date ASC
    '''):
        date_norm = str(row[0]).replace('-', '')[:8]
        _add(date_norm, row[1], row[2], row[3])

    # Tri chronologique — nécessaire pour tail(n) et slices
    for p in player_idx:
        player_idx[p].sort(key=lambda x: x[0])
    for pk in pair_idx:
        pair_idx[pk].sort(key=lambda x: x[0])

    print(f"   {len(player_idx)} joueurs, {len(pair_idx)} paires, {len(seen)} matchs uniques")
    return player_idx, pair_idx


# ─── CALCULS ──────────────────────────────────────────────────────────────────

def momentum(entries: list, player: str, date_cut: str, n: int) -> float:
    """entries = [(date_norm, winner, opponent), ...]  triés ASC"""
    past = [e for e in entries if e[0] < date_cut]
    past = past[-n:]  # derniers n matchs
    if not past:
        return 0.5
    wins = sum(1 for e in past if e[1] == player)
    return round(wins / len(past), 4)


def fatigue(entries: list, date_cut: str, days: int = 7) -> int:
    """entries = [(date_norm, winner, opponent), ...]  triés ASC"""
    ref     = datetime.strptime(date_cut, '%Y%m%d')
    cutoff  = (ref - timedelta(days=days)).strftime('%Y%m%d')
    return sum(1 for e in entries if cutoff <= e[0] < date_cut)


def h2h(entries: list, p1: str, date_cut: str) -> tuple:
    """entries = [(date_norm, winner), ...]  triés ASC"""
    past   = [e for e in entries if e[0] < date_cut]
    total  = len(past)
    p1_wins = sum(1 for e in past if e[1] == p1)
    ratio  = round(p1_wins / total, 4) if total > 0 else 0.5
    return p1_wins, total, ratio


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    conn = get_connection()
    create_table(conn)

    done_ids = set(
        row[0] for row in conn.execute('SELECT match_id FROM match_features')
    )
    print(f"   {len(done_ids)} matchs déjà calculés → skip")

    targets = load_targets(conn, limit=args.test)
    targets = [t for t in targets if t[0] not in done_ids]
    print(f"   {len(targets)} matchs à calculer")

    if not targets:
        print("✅ Tout est déjà calculé")
        conn.close()
        return

    player_idx, pair_idx = load_history(conn)

    n     = len(targets)
    batch = []
    now   = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    INSERT = '''
        INSERT OR IGNORE INTO match_features
        (match_id, p1_momentum_l5, p1_momentum_l10,
         p2_momentum_l5, p2_momentum_l10,
         h2h_p1_ratio, h2h_total,
         p1_fatigue_7d, p2_fatigue_7d, computed_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    '''

    print(f"\n⚙️  Calcul des features ({n} matchs)...")

    for i, (match_id, date_cut, p1, p2) in enumerate(targets):

        if i % 5000 == 0:
            print(f"   {i}/{n}...")
            if batch:
                conn.executemany(INSERT, batch)
                conn.commit()
                batch = []

        p1_entries   = player_idx.get(p1, [])
        p2_entries   = player_idx.get(p2, [])
        pair_entries = pair_idx.get(frozenset([p1, p2]), [])

        p1_m5  = momentum(p1_entries, p1, date_cut, 5)
        p1_m10 = momentum(p1_entries, p1, date_cut, 10)
        p2_m5  = momentum(p2_entries, p2, date_cut, 5)
        p2_m10 = momentum(p2_entries, p2, date_cut, 10)
        fat1   = fatigue(p1_entries, date_cut)
        fat2   = fatigue(p2_entries, date_cut)
        _, h2h_tot, h2h_rat = h2h(pair_entries, p1, date_cut)

        batch.append((
            match_id,
            p1_m5, p1_m10, p2_m5, p2_m10,
            h2h_rat, h2h_tot, fat1, fat2,
            now
        ))

    if batch:
        conn.executemany(INSERT, batch)
        conn.commit()

    total = conn.execute('SELECT COUNT(*) FROM match_features').fetchone()[0]
    print(f"\n✅ Terminé — {total} matchs dans match_features")
    conn.close()


if __name__ == '__main__':
    main()