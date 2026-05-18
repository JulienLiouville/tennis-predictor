# Architecture

## Data Flow

```
Sackmann CSV (2015-2024)
    ↓ collector.py
    → matches (386k lignes, dupliquées winner/loser)

TennisExplorer scraping
    ↓ match_collector.py
    → matches_2026 (74k+ lignes, player1 = toujours gagnant)
    → data/csv/tennis_global_atp_wta.csv (CSV global)

matches + matches_2026
    ↓ precompute_features.py  [LOCAL UNIQUEMENT]
    → match_features (127k features matches, 0 pour matches_2026 — TODO)

The Odds API
    ↓ live_collector.py
    → predictions (matchs + cotes du jour)

match_features + players_rankings
    ↓ predictor.py (train)
    → model.pkl

predictions (pending)
    ↓ predictor.py (inference)
    → predictions (avec predicted_winner + confidence)
    ↓ reporter.py
    → Email 08h30
```

---

## Database Tables

| Table | Purpose | Rows (prod) |
|---|---|---|
| `matches` | Matchs historiques ATP Sackmann 2015-2024 | ~128k |
| `matches_2026` | Matchs ATP/WTA récents 2025+ | ~74k |
| `match_features` | Features précalculées (momentum, H2H, fatigue) | ~127k |
| `players_rankings` | Historique classements ATP/WTA | — |
| `predictions` | Outputs modèle + cotes The Odds API | — |
| `tournament_surfaces` | Map tournoi → surface | — |

**Notes importantes :**
- `matches` : IDs 1 → 386666
- `matches_2026` : IDs 518533 → 592608+ (pas de collision avec `matches`)
- `matches` duplique chaque match (winner vs loser + loser vs winner) → ratio p1_win = 50%
- `matches_2026` : player1 = toujours le gagnant (format TennisExplorer) → ratio p1_win = 100%
- `_load_recent()` dans `predictor.py` corrige ce biais en dupliquant les lignes

---

## Design Decisions

### SQLite
- lightweight, déploiement simple, faible usage RAM sur VM

### Precomputed Features
- entraînement réduit de plusieurs heures à quelques secondes
- tourne en LOCAL uniquement (RAM e2-micro insuffisante pour le calcul complet)

### Multi-Agent Architecture
- modularité, maintenabilité, scalabilité future

### CSV Global
- buffer intermédiaire entre scraping quotidien et DB
- permet de recharger la DB from scratch sans re-scraper
- fichier : `data/csv/tennis_global_atp_wta.csv`

---

## Known Data Quirks

- `matches_2026.player1` = toujours le gagnant (contrairement à `matches`)
- Features `matches_2026` dans `match_features` = 0 lignes (TODO : fix `_load_recent()`)
- Rankings manquants sur ~30k matchs `matches_2026` (joueurs hors top, noms abrégés)
- `get_ranking.py` non intégré dans le scheduler — rankings non rafraîchis automatiquement