# Roadmap

## Phase 1 — Stabilisation (en cours)

### Terminé ✅
- Fix CSV sans header (518k lignes nulles dans `matches_2026`)
- Fix surfaces dans `tournament_surfaces`
- `precompute_features.py` optimisé RAM (index tuples, -70% RAM)
- `precompute_features.py` couvre `matches` + `matches_2026` en un seul script
- Pipeline déployé en prod (VM Google Cloud, scheduler 08h30)
- Email quotidien fonctionnel

### En cours / À faire
- [ ] Fix `_load_recent()` dans `predictor.py` : joindre `match_features` au lieu de hardcoder 0.5
- [ ] Split temporel dans `predictor.train()` (remplacer `random_state=42`)
- [ ] Intégrer `get_ranking.py` dans le scheduler (quotidien ou hebdo)
- [ ] Réconciliation `predictions` ↔ `matches_2026` : remplir `actual_winner` après `collect_yesterday()`
- [ ] Calibration probabilités (`CalibratedClassifierCV`)
- [ ] Compléter la Leakage Checklist dans `LEAKAGE_PREVENTION.md`

---

## Phase 2 — Betting Metrics

- Probabilités implicites bookmakers
- Value betting
- ROI tracking
- Calcul EV
- Simulation bankroll

---

## Phase 3 — MLOps

- Versioning modèle
- Experiment tracking
- Drift monitoring
- Analyse des échecs
- Validation réentraînement automatique

---

## Phase 4 — Scalabilité

- PostgreSQL
- API
- Dashboard
- Intégration Discord
- Multi-sport