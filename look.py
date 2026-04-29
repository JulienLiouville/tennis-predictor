"""
Test de validation du feature_builder — isolation temporelle H2H.
À lancer depuis la racine du projet : py test_feature_builder.py
"""
from agents.feature_builder import FeatureBuilder

fb = FeatureBuilder()

print("\n=== Test isolation temporelle H2H ===")
print("Dimitrov vs Rune — 4 matchs en DB : 20230703, 20230927, 20240101, 20240408")
print("Filtre < 20240107 → attendu : 3 matchs (exclu 20240408)")

h2h = fb.get_h2h("Grigor Dimitrov", "Holger Rune", "20240107")
print(f"Résultat : {h2h}")

if h2h['total'] == 3:
    print("✅ Isolation temporelle OK — pas de data leakage")
elif h2h['total'] == 0:
    print("❌ total=0 : problème de connexion DB ou format de date")
    print("   Vérifie que database.py est accessible depuis ce répertoire")
elif h2h['total'] == 4:
    print("❌ total=4 : filtre temporel ignoré — data leakage présent")
elif h2h['total'] == 6:
    print("❌ total=6 : duplication non corrigée + pas de filtre temporel")
elif h2h['total'] == 8:
    print("❌ total=8 : duplication non corrigée ET pas de filtre temporel")
else:
    print(f"❌ Résultat inattendu : total={h2h['total']}")

print("\n=== Test momentum ===")
m = fb.get_momentum("Grigor Dimitrov", 10, "20240107")
print(f"Momentum Dimitrov (10 matchs avant 20240107) : {m}")

print("\n=== Test fatigue ===")
f = fb.get_fatigue("Grigor Dimitrov", "20240107")
print(f"Fatigue Dimitrov (7j avant 20240107) : {f}")