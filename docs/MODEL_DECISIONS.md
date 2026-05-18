# Model Decisions

## Algorithme : GradientBoostingClassifier

**Raisons initiales :**
- simplicité
- intégration sklearn stable
- déploiement lightweight
- expérimentation rapide

**Alternatives futures :**
- XGBoost
- LightGBM

---

## Features actuelles

| Feature | Source | Leakage risk |
|---|---|---|
| `rank_diff` | `matches_2026.p1_rank` / `p2_rank` | low |
| `p1_momentum_l5` | `match_features` | medium |
| `p1_momentum_l10` | `match_features` | medium |
| `p2_momentum_l5` | `match_features` | medium |
| `p2_momentum_l10` | `match_features` | medium |
| `h2h_p1_ratio` | `match_features` | high |
| `h2h_total` | `match_features` | medium |
| `p1_fatigue_7d` | `match_features` | medium |
| `p2_fatigue_7d` | `match_features` | medium |
| `surface_enc` | `matches_2026.surface` | low |

**⚠️ Problème actuel :** pour `matches_2026`, toutes les features `match_features` sont à 0.5/0 (hardcodées dans `_load_recent()`). Le modèle apprend uniquement `rank_diff` pour les matchs 2025+.

---

## Validation

**Actuel :** `train_test_split(random_state=42)` — split aléatoire.
**Problème :** optimiste, permet au modèle de voir des matchs futurs.
**À faire :** split temporel (80% premiers matchs → train, 20% derniers → test).

**Backtest prod (17/05/2026) :**
- 1324 matchs testés
- Taux global : 62.61%
- Prédictions >80% confiance : 30 matchs, taux 93.33% (échantillon trop petit)

---

## Pourquoi SQLite ?

- VM e2-micro : peu de RAM et stockage
- simplicité
- déploiement lightweight

---

## Pourquoi features préCalculées ?

- entraînement réduit de plusieurs heures à quelques secondes
- `precompute_features.py` tourne en local (RAM VM insuffisante)

---

## Pourquoi ATP/WTA ensemble ?

- simplicité au développement initial
- **À benchmarker** : modèles séparés potentiellement plus précis

---

## Seuil 80% confiance

- seuil psychologique initial
- **Non calibré** : 80% modèle ≠ 80% réel
- À calibrer avec `CalibratedClassifierCV` avant d'optimiser pour le ROI