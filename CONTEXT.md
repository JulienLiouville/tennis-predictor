# 🎾 Tennis Predictor — Context & State

## 📋 Vue d'ensemble
Application multi-agent de prédiction de paris sportifs tennis (ATP + WTA).
Objectif : envoyer un mail quotidien à 8h30 avec 5 prédictions > 80% de confiance.
Stack : Python 3.10+, SQLite, scikit-learn, BeautifulSoup, schedule, Gmail SMTP.
Repo GitHub public : github.com/JulienLiouville/tennis-predictor

---

## 🏗️ Infrastructure

### Environnements
- **Local Windows** : développement principal (PyCharm)
  - Python : `C:\Users\julie\AppData\Local\Python\bin\python.exe`
  - Repo : `C:\Users\julie\OneDrive\Documents\GitHub\tennis-predictor`
- **VM Google Cloud** : production 24/7 (non encore déployée)
  - Type : e2-micro, us-east1-b (gratuit)
  - OS : Ubuntu 22.04 LTS
  - Process manager : tmux (session `tennis`)
- **GitHub** : github.com/JulienLiouville/tennis-predictor (public)

### Config emails
- Gmail SMTP SSL port 465
- App Password 16 caractères (dans `config.py`)

---

## 📁 Structure des fichiers

```
tennis-predictor/
├── config.py
├── database.py               # init_db() + get_connection() + _run_migrations()
├── main.py
├── precompute_features.py    # ⭐ One-shot local — peuple match_features en DB
├── match_collector.py        # Scrape matchs 2025+ — delta auto depuis CSV, résolution noms, migrate_names()
├── backfill_rankings.py      # Backfill rankings historiques 2025-2026
├── fix_surfaces.py           # Mappe surfaces inconnues
├── get_ranking.py            # Scrape classements ATP+WTA (top 1000)
├── set_surface.py
├── show_rankings.py
├── clean_old_rankings.py
├── verify_fixes.py           # Vérifie les corrections pkl/date_limit
├── quick_train.py            # Train rapide sur dataset réduit (debug)
├── debug_backtest.py         # Diagnostique backtest
├── test_feature_builder.py   # Test isolation temporelle H2H
├── test_model_range.py       # Test modèle sur range de dates limité
│
├── agents/
│   ├── orchestrator.py       # Scheduler + setup + retrain
│   ├── collector.py          # Collecte Sackmann 2015-2024
│   ├── live_collector.py     # Hybride tennisexplorer + Odds API
│   ├── predictor.py          # Modèle ML GradientBoosting
│   ├── backtester.py         # Backtest sur matchs historiques
│   ├── feature_builder.py    # UNION matches + matches_2026 dans get_h2h/get_momentum/get_fatigue ✅
│   ├── qa_engineer.py        # 6 tests unitaires
│   └── reporter.py           # Mail HTML quotidien
│
├── data/
│   ├── tennis.db             # ⚠️ NE JAMAIS SUPPRIMER EN PROD
│   ├── model.pkl             # Peut être supprimé et régénéré
│   └── csv/
│       └── tennis_global_atp_wta.csv
└── reports/
```

---

## 🗄️ Schéma Base de Données

### `matches` — Sackmann 2015-2024 (ATP uniquement)
- ~55 200 matchs bruts → stockés dans les **2 sens** (winner/loser + loser/winner)
- Contient `tourney_level` et stats service complètes (ace, df, svpt, etc.)
- Format date : `YYYYMMDD` (sans tirets)

### `match_features` — Features pré-calculées ⭐
```sql
match_id         INTEGER PRIMARY KEY  -- FK → matches.id
p1_momentum_l5   REAL
p1_momentum_l10  REAL
p2_momentum_l5   REAL
p2_momentum_l10  REAL
h2h_p1_ratio     REAL
h2h_total        INTEGER
p1_fatigue_7d    INTEGER
p2_fatigue_7d    INTEGER
computed_at      TEXT
```
- Peuplée par `precompute_features.py` (one-shot local, ~15 min)
- **Idempotente** : skip les match_id déjà présents
- Jointure dans `predictor._load_sackmann()` → `train()` rapide (secondes)
- ⚠️ NE PAS supprimer — coûteux à recalculer

### `matches_2026` — 2025→aujourd'hui (ATP + WTA)
```sql
id, date, time, tour, tournament, surface, best_of,
player1, player2, winner, score,
sets_won_p1, sets_won_p2, num_sets,
odds_p1, odds_p2,
p1_rank, p1_points, p1_country,
p2_rank, p2_points, p2_country,
ranking_date_used
UNIQUE(date, player1, player2, tour)
```
- PAS de stats service, PAS de `tourney_level`
- Stocké en **un seul sens** (pas de duplication)
- Format date : `YYYY-MM-DD` (avec tirets)

### `players_rankings`
```sql
name TEXT,      -- Format : "Sinner Jannik" (nom famille + prénom)
rank INTEGER, points INTEGER, country TEXT,
gender TEXT,    -- 'M' ATP / 'F' WTA
date_recorded DATE,
PRIMARY KEY (name, gender, date_recorded)
```
- 110 snapshots hebdomadaires 2025-2026 (backfill terminé ✅)

### `predictions`
```sql
id, date, tournament, surface,
player1, player2, predicted_winner, confidence,
p1_rank, p2_rank, odds_p1, odds_p2,
p1_elo, p2_elo, p1_elo_surface, p2_elo_surface,
p1_momentum, p2_momentum,
h2h_p1_wins, h2h_p2_wins,
actual_winner, correct
```

### Autres : `elo_ratings`, `tournament_surfaces`, `algo_performance`

---

## 🤖 État des agents

### `feature_builder.py` ✅ FIXÉ
**UNION avec `matches_2026` ajoutée dans `get_h2h`, `get_momentum`, `get_fatigue`.**

Problème racine découvert : `matches_2026` stockait les noms en format abrégé
(`"Sinner J."`) alors que `feature_builder` cherche en format complet (`"Sinner Jannik"`).
Fix appliqué dans `match_collector.py` : résolution des noms via `players_rankings`
à la collecte + méthode `migrate_names()` pour normaliser l'existant.

### `predictor.py` ✅ FIXÉ
**`train()` utilise `match_features` (pré-calculées) — rapide (secondes).**

- `_load_recent()` : filtre `p1_rank IS NOT NULL` supprimé (ranks souvent NULL dans matches_2026, fallback 150 dans prepare_features)
- `load_training_data()` : `dropna(subset=['p1_rank','p2_rank'])` supprimé

```python
FEATURE_COLUMNS = [
    'rank_diff',
    'p1_momentum_l5', 'p2_momentum_l5',
    'p1_momentum_l10', 'p2_momentum_l10',
    'h2h_p1_ratio', 'h2h_total',
    'p1_fatigue_7d', 'p2_fatigue_7d',
    'surface_enc',
]
```

- `_load_sackmann()` : INNER JOIN avec `match_features`
- `_load_recent()` : matches_2026 avec features à 0.5/0 par défaut
- `save_model()` / `load_model()` : dict `{model, le_surface, feature_columns}` ✅
- `predict()` : accepte `date_limit` optionnel
- `process_pending_predictions()` : lookup rank depuis `players_rankings` si NULL ✅

### `backtester.py` ✅
- Requête `player1 = winner` → ground truth cohérent
- Passe `p1_rank`/`p2_rank` et `date_limit` à `predict()`
- Résultats : 63.50% global, **85.19% sur prédictions >80%** ✅

### `live_collector.py` ✅
**Architecture hybride tennisexplorer + Odds API.**
- Scraping tennisexplorer : 77 matchs/jour ATP+WTA ✅
- Résolution noms abrégés → noms complets via `players_rankings` ✅
  - `"Hurkacz H."` → `"Hurkacz Hubert"` via LIKE sur nom de famille
  - Cache en mémoire pour éviter requêtes répétées
- Merge Odds API par nom normalisé (sans accents, lowercase)
- Sauvegarde robuste : tournament_surfaces et odds_p1/p2 en try/except

### `orchestrator.py` 🔴 BUG EN COURS
- `setup()` : Sackmann → CSV → entraîne → backtest → QA
- `retrain_weekly()` : recharge CSV + réentraîne
- `daily_job()` : live_collector + collect_yesterday + predict + QA + reporter
- **BUG** : `load_csv_to_db()` insère les surfaces telles quelles depuis le CSV (`"Unknown"`) → `_load_recent()` filtre `surface IN ("Hard","Clay","Grass")` → 0 matchs chargés → entraînement impossible
- **Fix appliqué** : résoudre la surface via `tournament_surfaces` au moment du chargement CSV (non encore validé)

### `database.py` ✅
- Toutes les tables présentes dont `match_features`
- `_run_migrations()` : ajoute colonnes manquantes sur DB existantes
- Colonnes `p1_rank`, `p2_rank`, `odds_p1`, `odds_p2`, `tournament` dans predictions

### `qa_engineer.py` ✅ — 6/6 tests

### `precompute_features.py` ✅ (one-shot local)
- 54 350 matchs dans `match_features`
- Idempotent, RAM-safe (batch 5000)

---

## 📊 Résultats validés

```
Précision modèle   : 61.71%  ✅ (ancien run, à revalider)
Backtest global    : 63.50%  ✅ (ancien run, à revalider)
Backtest >80%      : 85.19% sur 54 prédictions  ✅ (ancien run)
QA                 : 6/6  ✅ (ancien run)
Mail end-to-end    : ✅
Scraping           : 36-77 matchs/jour  ✅
Prédictions >80%   : 0 — pipeline entraînement bloqué (surfaces NULL)  🔴
```

---

## ⚠️ Problèmes connus

| # | Priorité | Problème | Fix |
|---|----------|----------|-----|
| 1 | 🔴 **TOP PRIO** | `orchestrator.load_csv_to_db()` insère surfaces `"Unknown"` → `_load_recent()` filtre Hard/Clay/Grass → 0 matchs → entraînement impossible | Résoudre surface via `tournament_surfaces` avant insertion — fix écrit, non encore validé |
| 2 | 🔴 **TOP PRIO** | `matches_2026` contient 444k lignes (doublons setup multiple) et surfaces toutes NULL | Vider la table, lancer `fix_surfaces.py`, puis `py main.py setup` |
| 3 | 🔴 **TOP PRIO** | `match_features` vide (0 lignes) | Lancer `py precompute_features.py` après setup Sackmann (~15 min) |
| 4 | 🟠 Important | Noms dans `matches_2026` en format abrégé (`"Sinner J."`) au lieu de complet (`"Sinner Jannik"`) | `py match_collector.py migrate` — résolution via `players_rankings` |
| 5 | 🟠 Important | `matches_2026` sans `match_features` → features à 0.5 à l'entraînement | Étendre `precompute_features.py` à `matches_2026` |
| 6 | 🟠 Important | Merge Odds API : 0/77 matchs enrichis | Résolution noms faite pour TE→DB, Odds API à investiguer |
| 7 | 🟡 Mineur | Doublons dans `predictions` si `daily_job` lancé 2× | Ajouter UNIQUE(date, player1, player2) |
| 8 | 🟡 Mineur | `matches_2026` mal nommée (contient 2025+) | Migration SQLite → `matches_recent` |
| 9 | 🟡 Mineur | VM non déployée | Après stabilisation |

---

## 🚀 Prochaines étapes (dans l'ordre)

### 1. 🔴 Vider matches_2026 et corriger le pipeline setup
```bash
# Vider la table corrompue (444k lignes avec surfaces NULL)
# Dans SQLite : DELETE FROM matches_2026;

# Mapper les surfaces
py fix_surfaces.py

# Normaliser les noms existants dans le CSV
py match_collector.py migrate

# Relancer le setup (avec orchestrator.py fixé)
py main.py setup
```

### 2. 🔴 Recalculer match_features (après setup Sackmann)
```bash
py precompute_features.py    # ~15 min, idempotent
```

### 3. Valider le pipeline complet
```bash
py main.py test              # job quotidien complet
```

### 4. Déployer VM Google Cloud
```bash
scp data/tennis.db user@vm-ip:~/tennis-predictor/data/
scp data/model.pkl user@vm-ip:~/tennis-predictor/data/
tmux new -s tennis
python main.py run
```

---

## 💡 Commandes utiles

```bash
# Pipeline principal
py main.py setup          # Setup complet
py main.py retrain        # Réentraînement (rapide)
py main.py test           # Test job quotidien
py main.py run            # Scheduler 24/7

# Collecte données
py match_collector.py                          # delta auto depuis CSV (date max → aujourd'hui)
py match_collector.py range 2025-01-01 2026-05-09
py match_collector.py yesterday
py match_collector.py migrate                  # normalise noms abrégés → complets en DB+CSV
py backfill_rankings.py
py get_ranking.py

# Surfaces
py fix_surfaces.py                             # mappe toutes les surfaces connues
py set_surface.py 'Nom tournoi' Clay           # setter manuellement

# Features & modèle
py precompute_features.py
py precompute_features.py --test 500
py precompute_features.py --reset

# Debug
py verify_fixes.py
py quick_train.py --size 3000
py debug_backtest.py
py test_feature_builder.py
py show_rankings.py --gender M --top 100
py show_rankings.py --search sinner
```

---

## 📝 Notes importantes

- **Commandes Python : toujours en fichiers `.py`**, jamais one-liners
- `tennis.db` : **NE JAMAIS SUPPRIMER** — contient `match_features`
- `model.pkl` : peut être supprimé et régénéré librement
- `matches` : 2 sens (Sackmann) → toujours dédupliquer par `match_key`
- `matches_2026` : 1 seul sens → dupliquer dans `_load_recent()` pour l'entraînement
- `matches_2026` : mal nommée — contient 2025+ (amélioration non obligatoire : renommer en `matches_recent`)
- Format date `matches` : `YYYYMMDD` | `matches_2026` : `YYYY-MM-DD`
- Noms `players_rankings` : `"Sinner Jannik"` (famille + prénom)
- Noms tennisexplorer : `"Sinner J."` (famille + initiale) → résolution via `_resolve_name()` dans `match_collector` et `_resolve_player_name()` dans `live_collector`
- Surfaces dans CSV : `"Unknown"` pour tournois non mappés → toujours lancer `fix_surfaces.py` avant `setup`
- ITF et UTR Pro exclus du scraping (`EXCLUDED_SUBSTRINGS` dans `match_collector.py`)
- tennisexplorer : User-Agent Mozilla requis + `verify=False`
- Backtest : requête `player1 = winner` pour ground truth cohérent

## 🏛️ Architecture décisions

| Décision | Raison |
|----------|--------|
| `match_features` en DB | train() 10h → quelques secondes |
| Précalcul local uniquement | VM e2-micro 1 Go RAM insuffisante |
| `save_model()` dict | Cohérence avec `load_model()` |
| `predict()` accepte `date_limit` | Isolation temporelle backtest |
| Déduplication Sackmann systématique | Chaque match stocké 2× dans `matches` |
| Backtest `player1 = winner` | Ground truth cohérent sans dédup |
| live_collector hybride TE + Odds API | Volume (TE) + cotes (Odds API) |
| Résolution noms à la collecte | Fix une fois → tout le pipeline bénéficie |
| ITF/UTR exclus du scraping | Joueurs hors `players_rankings`, polluent les features |
| `fix_surfaces.py` avant setup | Surfaces `"Unknown"` dans CSV → 0 matchs chargés sinon |
| delta auto dans `match_collector.py` | Évite de re-scraper l'existant |