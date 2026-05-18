# 🎾 Tennis Predictor — Project Context

## Overview

Tennis Predictor est une plateforme multi-agents de machine learning pour la prédiction de matchs ATP/WTA.

**Goal :**
- collecter les matchs tennis (historique + quotidien)
- calculer des features temporelles (momentum, H2H, fatigue)
- entraîner des modèles prédictifs
- générer des prédictions de paris
- détecter à terme les inefficacités de pricing des bookmakers

**Long-term vision :**
- système autonome de betting intelligence
- potentiel Discord premium
- expansion multi-sport

---

## Current Stack

- Python 3.10+
- SQLite
- scikit-learn (GradientBoostingClassifier)
- BeautifulSoup (scraping TennisExplorer)
- schedule + Gmail SMTP
- Google Cloud VM e2-micro (production)

---

## Core Architecture

```
Sackmann CSV (2015-2024)
    ↓ collector.py
    → matches

TennisExplorer scraping
    ↓ match_collector.py
    → matches_2026 + CSV global

matches + matches_2026
    ↓ precompute_features.py
    → match_features

match_features
    ↓ predictor.py (train)
    → model.pkl

The Odds API
    ↓ live_collector.py
    → predictions (matchs du jour)

predictions
    ↓ predictor.py (inference)
    → predictions (avec predicted_winner)
    ↓ reporter.py
    → Email quotidien 08h30
```

---

## Main Agents

| Agent | Rôle |
|---|---|
| `collector.py` | Collecte historique Sackmann 2015-2024 |
| `match_collector.py` | Scraping TennisExplorer quotidien + CSV global |
| `live_collector.py` | Scraping The Odds API (matchs + cotes du jour) |
| `predictor.py` | Entraînement ML + inférence |
| `backtester.py` | Évaluation historique |
| `reporter.py` | Génération email quotidien |
| `orchestrator.py` | Orchestration pipeline |
| `qa_engineer.py` | Validation pipeline |
| `precompute_features.py` | Précalcul features (opération manuelle) |

---

## Scheduler (prod)

| Heure | Job |
|---|---|
| 08h30 quotidien | `daily_job` : collecte + prédictions + email |
| Dimanche 02h00 | `retrain_weekly` : reload CSV + réentraînement |

---

## Current ML Strategy

**Focus actuel :**
- précision et robustesse
- prévention des leakages
- calibration des probabilités (pending)

**Pas encore :**
- optimisation ROI
- Kelly betting
- live betting
- bankroll management

---

## NON-NEGOTIABLE RULES

- NEVER use future data
- ALWAYS use temporal validation (pas random_state=42 en prod)
- NEVER trust raw probabilities without calibration
- NEVER delete tennis.db in production
- ALWAYS prevent train/test leakage
- ALWAYS verify rankings date consistency
- ALWAYS run surface normalization before training
- NEVER use post-match information in features
- `precompute_features.py` tourne en LOCAL uniquement (RAM e2-micro insuffisante)