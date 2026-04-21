import pandas as pd
from database import get_connection


def show_entries(limit=20, filter_2026=True):
    """
    Affiche les dernières entrées de la base de données.
    """
    conn = get_connection()

    # On construit la requête SQL
    query = "SELECT date, tournament, player1, player2, winner, surface FROM matches"

    if filter_2026:
        query += " WHERE date LIKE '2026%'"

    query += f" ORDER BY date DESC LIMIT {limit}"

    try:
        # Lecture avec Pandas pour un affichage propre en tableau
        df = pd.read_sql(query, conn)

        if df.empty:
            print("⚠️ La base de données est vide pour les critères sélectionnés.")
        else:
            print(f"\n📊 Aperçu des {len(df)} dernières entrées (2026) :")
            print("=" * 100)
            # On configure Pandas pour ne pas couper les colonnes à l'affichage
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', 1000)
            pd.set_option('display.colheader_justify', 'left')

            print(df.to_string(index=False))
            print("=" * 100)

            # Petit résumé rapide
            count_query = "SELECT surface, COUNT(*) as nb FROM matches GROUP BY surface"
            df_stats = pd.read_sql(count_query, conn)
            print("\n📈 Statistiques par surface dans toute la base :")
            print(df_stats.to_string(index=False))

    except Exception as e:
        print(f"❌ Erreur lors de la lecture : {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    # Tu peux changer limit pour voir plus de lignes
    show_entries(limit=30)