"""
verify_fixes.py
Vérifie les 2 bugs corrigés sans réentraîner le modèle complet.
Lance depuis la racine du projet : py verify_fixes.py
"""

import os
import pickle
import tempfile
import traceback
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder

print("=" * 55)
print("🔍 VÉRIFICATION DES CORRECTIONS — predictor.py")
print("=" * 55)

PASS = "✅"
FAIL = "❌"
results = []

# ─── TEST 1 : save_model / load_model cohérents ───────────────────────────

print("\n[1/3] Cohérence save_model → load_model")

try:
    # Simule ce que save_model() fait
    fake_model = GradientBoostingClassifier(n_estimators=5)
    fake_le = LabelEncoder().fit(["Hard", "Clay", "Grass"])
    fake_cols = ["rank_diff", "elo_diff"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pkl") as tmp:
        tmp_path = tmp.name
        pickle.dump({
            "model": fake_model,
            "le_surface": fake_le,
            "feature_columns": fake_cols,
        }, tmp)

    # Simule ce que load_model() fait
    with open(tmp_path, "rb") as f:
        data = pickle.load(f)
        loaded_model    = data["model"]
        loaded_le       = data["le_surface"]
        loaded_cols     = data["feature_columns"]

    os.unlink(tmp_path)
    print(f"  {PASS} save_model → load_model : OK")
    results.append(True)

except Exception as e:
    print(f"  {FAIL} Erreur : {e}")
    results.append(False)

# ─── TEST 2 : train() utilise save_model() (pas pickle.dump brut) ─────────

print("\n[2/3] train() sauvegarde via save_model() (pas pickle brut)")

try:
    from agents.predictor import PredictorAgent
    import inspect

    src = inspect.getsource(PredictorAgent.train)

    # Le bug = pickle.dump(self.model, f) dans train()
    has_raw_dump = "pickle.dump(self.model" in src
    has_save_model_call = "self.save_model()" in src

    if has_raw_dump and not has_save_model_call:
        print(f"  {FAIL} train() utilise encore pickle.dump brut → bug NON corrigé")
        results.append(False)
    elif has_save_model_call and not has_raw_dump:
        print(f"  {PASS} train() appelle self.save_model() → bug corrigé")
        results.append(True)
    elif has_save_model_call and has_raw_dump:
        print(f"  {FAIL} train() contient les DEUX — nettoie le pickle.dump résiduel")
        results.append(False)
    else:
        print(f"  ⚠️  Impossible de détecter automatiquement — vérifie manuellement train()")
        results.append(False)

except Exception as e:
    print(f"  {FAIL} Impossible d'inspecter predictor.py : {e}")
    results.append(False)

# ─── TEST 3 : predict() accepte date_limit et le passe à build_features ───

print("\n[3/3] predict() accepte date_limit et le transmet à build_features()")

try:
    src_predict = inspect.getsource(PredictorAgent.predict)

    has_date_limit_param = "date_limit" in src_predict
    passes_to_build      = "date_limit=date_limit" in src_predict or \
                           "build_features(" in src_predict and "date_limit" in src_predict

    if not has_date_limit_param:
        print(f"  {FAIL} predict() n'a pas de paramètre date_limit")
        results.append(False)
    elif not passes_to_build:
        print(f"  {FAIL} date_limit non transmis à build_features()")
        results.append(False)
    else:
        print(f"  {PASS} predict() accepte et transmet date_limit → bug corrigé")
        results.append(True)

except Exception as e:
    print(f"  {FAIL} Impossible d'inspecter predict() : {e}")
    results.append(False)

# ─── RÉSUMÉ ───────────────────────────────────────────────────────────────

print("\n" + "=" * 55)
passed = sum(results)
total  = len(results)
print(f"Résultat : {passed}/{total} checks passés")

if passed == total:
    print("✅ Corrections validées — tu peux relancer py main.py setup")
else:
    print("❌ Des bugs subsistent — relis les messages ci-dessus")
print("=" * 55)