from database import get_connection

def create_map():
    conn = get_connection()
    c = conn.cursor()
    # On crée une table avec la surface la plus fréquente par tournoi
    c.execute("DROP TABLE IF EXISTS tourney_map")
    c.execute('''CREATE TABLE tourney_map AS
                 SELECT tournament, surface FROM (
                     SELECT tournament, surface, COUNT(*) as freq
                     FROM matches
                     WHERE tournament != "" AND surface NOT IN ("", "None", "nan")
                     GROUP BY tournament, surface
                     ORDER BY tournament, freq DESC
                 ) GROUP BY tournament''')
    conn.commit()
    conn.close()
    print("✅ Table tourney_map générée !")

if __name__ == "__main__":
    create_map()