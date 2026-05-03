# 🎾 Tennis Predictor — Context & State

## 📋 Vue d'ensemble
Application multi-agent de prédiction de paris sportifs tennis (ATP + WTA).
Objectif : envoyer un mail quotidien à 8h30 avec 5 prédictions > 80% de confiance.
Stack : Python 3.10, SQLite, scikit-learn, BeautifulSoup, schedule, Gmail SMTP.
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
├── database.py               # init_db() + get_connection()
├── main.py
├── match_collector.py        # Scrape matchs 2025+
├── backfill_rankings.py      # Backfill rankings historiques 2025-2026
├── fix_surfaces.py           # Mappe surfaces inconnues
├── get_ranking.py            # Scrape classements ATP+WTA (top 1000)
├── set_surface.py
├── show_rankings.py
├── clean_old_rankings.py
├── test_feature_builder.py   # Test isolation temporelle H2H
├── test_model_range.py       # Test modèle sur range de dates limité
│
├── agents/
│   ├── orchestrator.py       # Scheduler + setup + retrain
│   ├── collector.py          # Collecte Sackmann 2015-2024
│   ├── live_collector.py     # Matchs du jour via The Odds API
│   ├── predictor.py          # Modèle ML GradientBoosting
│   ├── backtester.py         # Backtest sur matchs historiques
│   ├── feature_builder.py    # Elo, Momentum, H2H, Fatigue
│   ├── qa_engineer.py        # 6 tests unitaires
│   └── reporter.py           # Mail HTML quotidien
│
├── data/
│   ├── tennis.db
│   ├── model.pkl
│   └── csv/
│       └── tennis_global_atp_wta.csv   # CSV global 2025→aujourd'hui
└── reports/
```

---

## 🗄️ Schéma Base de Données

### `matches` — Sackmann 2015-2024 (ATP uniquement)
- ~55 200 matchs bruts → stockés dans les **2 sens** (winner/loser + loser/winner)
- Contient `tourney_level` et stats service complètes (ace, df, svpt, etc.)
- Format date : `YYYYMMDD` (sans tirets)

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
- **Stocké en un seul sens** (pas de duplication)
- À renommer `matches_recent` (migration future)

### `players_rankings`
```sql
name TEXT,      -- Format : "Sinner Jannik" (nom famille + prénom)
rank INTEGER, points INTEGER, country TEXT,
gender TEXT,    -- 'M' ATP / 'F' WTA
date_recorded DATE,
PRIMARY KEY (name, gender, date_recorded)
```
- Top 1000 ATP + WTA via tennisexplorer
- Matching : `LIKE '%last_name%'` + gender + `date_recorded <= date_match`

### Autres : `predictions`, `elo_ratings`, `tournament_surfaces`, `algo_performance`

---

## 🤖 État des agents

### `feature_builder.py` ✅
**Isolation temporelle complète — data leakage corrigé.**

Toutes les méthodes acceptent `date_limit` (YYYYMMDD ou YYYY-MM-DD) et ne regardent
que les matchs strictement antérieurs à cette date.

Déduplication systématique via `match_key = date + '_' + joueurs_triés` dans les 3
méthodes pour éviter le double-comptage dû au stockage Sackmann en 2 sens.

```python
get_h2h(p1, p2, date_limit)      # H2H avant date_limit, dédupliqué
get_momentum(player, n, date_limit)  # Ratio victoires N derniers matchs
get_fatigue(player, date_limit, days=7)  # Nb matchs sur 7 derniers jours
get_elo(player, surface=None)     # Depuis elo_ratings (calculé à l'entraînement)
build_features(p1, p2, surface, date_limit=None)  # Vecteur complet
```

**Validation :** `py test_feature_builder.py` — Dimitrov vs Rune retourne 3 matchs
(pas 6 ou 8) avant le 07/01/2024. ✅

### `predictor.py` ✅
**26 features — FEATURE_COLUMNS (source unique de vérité train/predict) :**
```python
FEATURE_COLUMNS = [
    'rank_diff',
    'elo_diff', 'elo_surface_diff',
    'p1_momentum_l5', 'p2_momentum_l5',
    'p1_momentum_l10', 'p2_momentum_l10',
    'h2h_p1_ratio', 'h2h_total',
    'p1_fatigue_7d', 'p2_fatigue_7d',
    'surface_enc', 'tourney_level_enc', 'best_of',
    'p1_1st_serve_pct', 'p1_1st_won_pct', 'p1_2nd_won_pct', 'p1_bp_saved_pct',
    'p2_1st_serve_pct', 'p2_1st_won_pct', 'p2_2nd_won_pct', 'p2_bp_saved_pct',
    'p1_dr',
    'p1_ace', 'p2_ace', 'p1_df', 'p2_df',
]
```
- Charge `matches` (Sackmann) + `matches_2026` fusionnés
- `_load_recent()` duplique dans les 2 sens (pour avoir les 2 classes)
- `dropna(subset=['p1_rank', 'p2_rank'])` strict
- `_add_elo_momentum_h2h()` passe `row['date']` à `build_features()` → isolation temporelle
- Stats service absentes de `matches_2026` → fillna médianes
- `predict()` accepte `date_limit` optionnel (pour le backtest)

### `backtester.py` ✅
- Accepte `predictor=` optionnel → réutilise l'instance déjà entraînée (pas de rechargement pkl)
- Déduplication des matchs Sackmann avant le backtest
- Teste sur `matches` avec `date >= '20230101'`

### `orchestrator.py` ✅
- `load_csv_to_db()` : charge CSV → `matches_2026` (INSERT OR IGNORE, idempotent)
- `setup()` : Sackmann → CSV → entraîne → backtest (avec `predictor=self.predictor`) → QA
- `retrain_weekly()` : recharge CSV + réentraîne (ne re-télécharge plus Sackmann)
- `daily_job()` : live_collector + collect_yesterday + predict + QA + reporter

### `database.py` ✅
- `matches_2026` et `players_rankings` créées dans `init_db()`
- Index sur matches_2026 (date, player1, player2)

### `qa_engineer.py` ✅
- `test_unknown_player_handling` corrigé : accepte `status='success'` ou `'unknown_player'`
- 6/6 tests passent

### `match_collector.py` ✅
- `EXCLUDED_SUBSTRINGS` + `EXCLUDED_PATTERNS` remplacent `EXCLUDED_TOURNAMENTS`
- Pattern `r'^futures \d{4}$'` → Futures exclus toutes années
- ITF conservés (utile pour Elo/H2H)

### `fix_surfaces.py` ✅
- 27 tournois ajoutés (Hard/Clay/Grass)
- Pattern `r'^Futures \d{4}$'` dans PATTERNS
- Surface Unknown < 0.1% après application

### `backfill_rankings.py` ✅ (⚠️ pas encore lancé)
- Snapshots hebdomadaires tennisexplorer 2025-2026
- URL : `https://www.tennisexplorer.com/ranking/atp-men/2025/?date=YYYY-MM-DD`
- Skip si déjà en base, relançable sans risque

---

## 📊 Résultats validés

### Test sur range limité (test_model_range.py)
```
Train : 2015-2020 (5000 matchs bruts → 5000 après dédup → x2 = 10000)
Test  : 2021-2022 (1000 matchs bruts → x2 = 2000)
Précision globale  : 61.30%  ✅ sans data leakage
Prédictions >80%   : 91/1000
Précision sur >80% : 85.71%  ✅
```

### Top features (sans leakage)
```
rank_diff          : 70.28%  (dominant, cohérent)
p2_momentum_l10    : 6.73%
p1_momentum_l10    : 6.66%
p1_momentum_l5     : 4.17%
h2h_p1_ratio       : 2.55%  (était 72% avec leakage → corrigé ✅)
```

### Setup complet (Sackmann uniquement, matches_2026 vide au moment du test)
```
Précision : 65.45%  ✅ sain
```

---

## ⚠️ Problèmes connus

| # | Priorité | Problème | Fix |
|---|----------|----------|-----|
| 1 | 🟠 Important | `backfill_rankings.py` pas lancé → ranks historiques manquants | `py backfill_rankings.py` (~2h) |
| 2 | 🟠 Important | `matches_2026` chargé mais ranks datés 2026-04-26 sur tout | Corriger après backfill |
| 3 | 🟡 Mineur | `_add_elo_momentum_h2h()` lent (appel DB par ligne) | Calcul vectorisé futur |
| 4 | 🟡 Mineur | `matches_2026` mal nommée | Migration SQLite future |
| 5 | 🟡 Mineur | `fix_surfaces.py` non intégré dans `_init_db` | À faire |
| 6 | 🟡 Mineur | VM non déployée | Après stabilisation |
| 7 | 🟡 Mineur | WTA absente de Sackmann | Couverte via matches_2026 (2025+) |
| 8 | 🟡 Mineur | `feature_builder` calcule depuis `matches` uniquement | Étendre à matches_2026 |

---

## 🚀 Prochaines étapes (dans l'ordre)

1. **Supprimer l'ancien model.pkl et relancer setup complet :**
   ```bash
   del data\model.pkl
   py main.py setup
   ```

2. **Lancer backfill rankings** (~2h, one-shot) :
   ```bash
   py backfill_rankings.py
   ```

3. **Régénérer le CSV avec les bons ranks** :
   ```bash
   py match_collector.py range 2025-01-01 2026-05-03
   ```

4. **Retrain avec données complètes** :
   ```bash
   py main.py retrain
   ```

5. **Tester mail end-to-end** :
   ```bash
   py main.py test
   ```

6. **Déployer VM Google Cloud** + tmux

7. **Optimiser `_add_elo_momentum_h2h()`** si l'entraînement est trop lent

---

## 💡 Commandes utiles

```bash
py main.py setup                                     # Setup complet
py main.py retrain                                   # Réentraînement
py main.py test                                      # Test job quotidien
py main.py run                                       # Scheduler 24/7

py match_collector.py range 2025-01-01 2026-05-03   # Générer CSV global
py match_collector.py yesterday                      # Collecte hier
py backfill_rankings.py                              # Rankings historiques (~2h)
py backfill_rankings.py --dry-run                    # Test sans scraper
py get_ranking.py                                    # Rankings aujourd'hui
py fix_surfaces.py                                   # Mapper surfaces inconnues
py test_feature_builder.py                           # Valider isolation temporelle
py show_rankings.py --gender M --top 100
py show_rankings.py --search sinner
```

---

## 📝 Notes importantes

- **Commandes Python : toujours en fichiers `.py`**, jamais one-liners ou `py -c`
- `matches` stocke chaque match dans **2 sens** (Sackmann) → toujours dédupliquer avant analyse
- `matches_2026` stocke en **1 seul sens** → dupliquer dans `_load_recent()` pour l'entraînement
- Format date `matches` : `YYYYMMDD` (sans tirets)
- Format date `matches_2026` : `YYYY-MM-DD` (avec tirets)
- `feature_builder` normalise les deux formats via `_normalize_date()`
- Noms joueurs `players_rankings` : format `"Sinner Jannik"` (nom famille + prénom)
- tennisexplorer : User-Agent Mozilla requis + `verify=False` (SSL)
- Si `model.pkl` plante au chargement → le supprimer et réentraîner