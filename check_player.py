from database import get_connection

conn = get_connection()
c = conn.cursor()
c.execute("DELETE FROM players_rankings WHERE date_recorded = '2026-04-20'")
conn.commit()
print(f"Supprimé : {c.rowcount} entrées")
conn.close()