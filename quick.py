from agents.feature_builder import FeatureBuilder
from database import get_connection
import pandas as pd

fb = FeatureBuilder()
conn = get_connection()

# On prend un match de 2024 (Dimitrov par exemple)
p1, p2, date_match = "Grigor Dimitrov", "Holger Rune", "20240107"

print(f"🕵️ TEST FLASH SUR : {p1} vs {p2}")

# Test 1 : Avant le match (strict)
stats_avant = fb.get_h2h(p1, p2, date_limit=date_match)

# Test 2 : Après le match (on ajoute 1 jour à la limite)
stats_apres = fb.get_h2h(p1, p2, date_limit="20240108")

print(f"📊 Matchs en H2H AVANT le jour J : {stats_avant['total']}")
print(f"📊 Matchs en H2H APRES le jour J : {stats_apres['total']}")

if stats_apres['total'] > stats_avant['total']:
    print("\n✅ LEAK RÉSOLU : Le filtre 'date < date_limit' fonctionne.")
else:
    print("\n🚨 LEAK TOUJOURS PRÉSENT : Le match du jour est inclus dans les stats.")
conn.close()