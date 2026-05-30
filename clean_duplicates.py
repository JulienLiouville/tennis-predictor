#!/usr/bin/env python3
"""
Script de cleanup des doublons dans la table predictions.
À lancer avant de redémarrer l'app.
"""

from database import get_connection


def cleanup_duplicates():
    """Supprime les doublons en gardant le premier (rowid min)."""
    conn = get_connection()
    c = conn.cursor()

    print("🧹 Nettoyage des doublons dans predictions...")

    # Compte les doublons
    c.execute("""
        SELECT date, player1, player2, COUNT(*) as count
        FROM predictions
        GROUP BY date, player1, player2
        HAVING count > 1
    """)
    duplicates = c.fetchall()

    if duplicates:
        print(f"⚠️  {len(duplicates)} groupe(s) de doublons détecté(s)\n")
        for date, p1, p2, count in duplicates:
            print(f"  {date} | {p1} vs {p2} : {count} copies")
    else:
        print("✅ Aucun doublon détecté")
        conn.close()
        return

    # Supprime les doublons (garde le premier)
    c.execute("""
        DELETE FROM predictions 
        WHERE rowid NOT IN (
            SELECT MIN(rowid) 
            FROM predictions 
            GROUP BY date, player1, player2
        )
    """)

    deleted = c.rowcount
    conn.commit()
    conn.close()

    print(f"\n✅ {deleted} ligne(s) supprimée(s)")


if __name__ == "__main__":
    cleanup_duplicates()