from database import get_connection


def clean_database():
    conn = get_connection()
    c = conn.cursor()

    print("🧹 Nettoyage de la base de données...")
    # On vide les matchs (historique et 2026)
    c.execute("DELETE FROM matches")

    # On s'assure que la table des surfaces (notre nouveau référentiel) existe
    c.execute("""
        CREATE TABLE IF NOT EXISTS tournament_surfaces (
            tournament_lower TEXT PRIMARY KEY,
            surface TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("✨ Base de données vidée et prête.")


if __name__ == "__main__":
    clean_database()