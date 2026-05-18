# Known Issues

## Critical

### match_features vide pour matches_2026
**Impact :** le modèle s'entraîne avec momentum/H2H/fatigue = 0.5/0 pour tous les matchs 2025+.
**Cause :** `precompute_features.py` calcule les features mais `_load_recent()` dans `predictor.py` hardcode les features à 0.5 au lieu de joindre `match_features`.
**Fix :** faire une INNER JOIN `matches_2026` ↔ `match_features` dans `_load_recent()`, comme `_load_sackmann()`.
**Status :** non implémenté

### Train/test split random
**Impact :** accuracy backtestée optimiste — le modèle peut voir des matchs futurs.
**Cause :** `train_test_split(X, y, test_size=0.2, random_state=42)` dans `predictor.py`.
**Fix :** split temporel — trier par date, prendre les 80% premiers pour train.
**Status :** non implémenté

### Rankings non mis à jour automatiquement
**Impact :** `p1_rank` / `p2_rank` dans `matches_2026` deviennent obsolètes. Prédictions basées sur des classements périmés.
**Cause :** `get_ranking.py` absent du `daily_job` dans `orchestrator.py`.
**Fix :** ajouter `get_ranking.py` dans `daily_job` ou `retrain_weekly`.
**Status :** non implémenté

### Réconciliation predictions ↔ résultats réelle absente
**Impact :** impossible de calculer le taux de réussite réel en production.
**Cause :** `collect_yesterday()` insère de nouvelles lignes dans `matches_2026` mais ne met pas à jour `predictions` avec `actual_winner`.
**Fix :** après `collect_yesterday()`, matcher par `(date, player1, player2)` et remplir `actual_winner` dans `predictions`.
**Status :** non implémenté

---

## Important

### Calibration des probabilités absente
**Impact :** 80% de confiance du modèle ne correspond pas à 80% réel.
**Fix :** ajouter `CalibratedClassifierCV`.
**Status :** pending

### CSV sans header (bug historique corrigé)
**Impact :** 518k lignes nulles insérées dans `matches_2026`.
**Cause :** `_append_to_global_csv()` lisait le CSV sans header → première ligne de données utilisée comme noms de colonnes.
**Fix :** `fix_csv_and_db.py` — corrigé le 17/05/2026.
**Status :** ✅ corrigé

### ATP/WTA modèle combiné non benchmarké
**Impact :** comportements statistiques différents entre circuits.
**Status :** not benchmarked

### precompute_features.py fait crasher le VM
**Impact :** e2-micro (1 Go RAM) OOM sur le calcul complet.
**Fix :** version optimisée avec index tuples au lieu de DataFrames — réduit la RAM de ~70%.
**Status :** ✅ optimisé, tourne en local uniquement