import sqlite3
from datetime import datetime
from config import DB_PATH


def show_all_predictions():
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # On récupère tout sans filtre de confiance
    query = """
        SELECT DISTINCT player1, player2, surface, predicted_winner, confidence 
        FROM predictions 
        WHERE date = ? 
        AND predicted_winner != 'Inconnu (Nouveau joueur)'
        ORDER BY confidence DESC
    """

    print(f"\n--- TOUTES LES PRÉDICTIONS DU {today} ---")
    cursor.execute(query, (today,))
    rows = cursor.fetchall()

    if not rows:
        print("⚠️ Aucune prédiction trouvée en base pour aujourd'hui.")
        print("Lance 'py main.py test' pour en générer.")
    else:
        for row in rows:
            p1, p2, surf, winner, conf = row
            # On affiche tout, même le "bruit"
            status = "🔥" if conf >= 0.8 else "⚖️"
            print(f"{status} {p1} vs {p2} ({surf}) -> Vainqueur : {winner} | Confiance : {conf * 100:.2f}%")

    conn.close()


if __name__ == "__main__":
    show_all_predictions()