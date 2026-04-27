import sqlite3
import argparse

DB_PATH = "data/tennis.db"

def show_rankings(gender=None, top=50, date=None, search=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Date la plus récente dispo si non précisée
    if not date:
        cursor.execute("SELECT MAX(date_recorded) FROM players_rankings")
        date = cursor.fetchone()[0]
        if not date:
            print("❌ Table players_rankings vide.")
            conn.close()
            return

    print(f"\n📅 Date utilisée : {date}")

    conditions = ["date_recorded = ?"]
    params = [date]

    if gender:
        conditions.append("gender = ?")
        params.append(gender.upper())

    if search:
        conditions.append("LOWER(name) LIKE ?")
        params.append(f"%{search.lower()}%")

    where = " AND ".join(conditions)

    cursor.execute(f"""
        SELECT rank, name, points, country, gender
        FROM players_rankings
        WHERE {where}
        ORDER BY gender, rank
        LIMIT ?
    """, params + [top])

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("⚠️ Aucun résultat.")
        return

    print(f"\n{'Rank':<6} {'Nom':<30} {'Points':<10} {'Pays':<6} {'Tour'}")
    print("-" * 60)
    for rank, name, points, country, g in rows:
        tour = "ATP" if g == "M" else "WTA"
        print(f"{rank:<6} {name:<30} {points:<10} {country:<6} {tour}")

    print(f"\n✅ {len(rows)} joueurs affichés.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspecte la table players_rankings")
    parser.add_argument("--gender", choices=["M", "F"], help="M=ATP, F=WTA")
    parser.add_argument("--top", type=int, default=50, help="Nombre de joueurs (défaut: 50)")
    parser.add_argument("--date", help="Date au format YYYY-MM-DD (défaut: la plus récente)")
    parser.add_argument("--search", help="Rechercher un joueur par nom")
    args = parser.parse_args()

    show_rankings(gender=args.gender, top=args.top, date=args.date, search=args.search)