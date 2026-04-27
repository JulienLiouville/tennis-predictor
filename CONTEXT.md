# 🎾 Tennis Predictor — Context & State

## 📋 Vue d'ensemble
Application multi-agent de prédiction de paris sportifs tennis (ATP + WTA).
Objectif : envoyer un mail quotidien à 8h30 avec 5 prédictions > 80% de confiance.
Stack : Python 3.10, SQLite, scikit-learn, BeautifulSoup, schedule, Gmail SMTP.

---

## 🏗️ Infrastructure

### Environnements
- **Local Windows** : développement principal (PyCharm)
  - Python : `C:\Users\julie\AppData\Local\Python\bin\python.exe`
  - Repo : `C:\Users\julie\OneDrive\Documents\GitHub\tennis-predictor`
- **VM Google Cloud** : production 24/7 (non encore déployée)
  - Type : e2-micro, us-east1-b (gratuit)
  - OS : Ubuntu 22.04 LTS
  - Connexion : SSH via console Google Cloud
  - Process manager : tmux (session `tennis`)
  - Commande relance : `cd tennis-predictor && source venv/bin/activate`
- **GitHub** : github.com/JulienLiouville/tennis-predictor (public)

### Config emails
- Bot Gmail : à renseigner dans `config.py`
- Envoi : Gmail SMTP SSL port 465
- Mot de passe : App Password 16 caractères (pas le vrai mdp)

---

## 📁 Structure des fichiers
```
tennis-predictor/
├── config.py                 # Clés API, email, chemins DB
├── database.py               # get_connection() + init_db() + migrations
├── main.py                   # Point d'entrée (setup/run/test/retrain)
├── feature_builder.py        # Calcul Elo, Momentum, H2H (intégré dans predictor)
├── get_ranking.py            # Scrape classements ATP+WTA (tennisexplorer, 1000 joueurs, paginé)
├── match_collector.py        # Scrape matchs journaliers 2025→aujourd'hui → DB + CSV global
├── fix_surfaces.py           # Mappe en masse les surfaces inconnues en DB
├── set_surface.py            # Corrige une surface manuellement (CLI)
├── show_rankings.py          # Inspecte la table players_rankings (CLI)
├── clean_old_rankings.py     # Supprime les anciennes entrées corrompues de players_rankings
│
├── agents/
│   ├── orchestrator.py       # Scheduler 8h30 + retrain dimanche 2h
│   ├── collector.py          # Collecte historique Jeff Sackmann 2015-2024 → table matches
│   ├── live_collector.py     # Matchs du jour via The Odds API
│   ├── predictor.py          # Modèle ML GradientBoosting
│   ├── backtester.py         # Backtest sur matchs >= 20230101
│   ├── qa_engineer.py        # 6 tests unitaires automatiques
│   └── reporter.py           # Génère et envoie le mail HTML
│
├── data/
│   ├── tennis.db             # Base SQLite principale
│   ├── model.pkl             # Modèle ML sérialisé
│   └── csv/
│       └── tennis_global_atp_wta.csv   # CSV global 2025→aujourd'hui (source de vérité déploiement)
│
├── reports/                  # Rapports HTML quotidiens
└── tests/                    # Tests unitaires
```

---

## 🗄️ Schéma Base de Données

### `matches` — Historique Jeff Sackmann 2015-2024
```sql
id, date, tournament, tourney_level, surface, round, best_of,
player1, player2, winner, score,
p1_rank, p1_rank_points, p1_age, p1_hand, p1_height,
p2_rank, p2_rank_points, p2_age, p2_hand, p2_height,
p1_ace, p1_df, p1_svpt, p1_1stIn, p1_1stWon, p2ndWon,
p1_SvGms, p1_bpSaved, p1_bpFaced,
p2_ace, p2_df, p2_svpt, p2_1stIn, p2_1stWon, p2_2ndWon,
p2_SvGms, p2_bpSaved, p2_bpFaced
```
- Chaque match sauvegardé dans les deux sens (winner/loser + loser/winner)
- ~98 000 matchs ATP après setup complet

### `matches_2026` — Matchs 2025→aujourd'hui scrapés (mal nommée, à renommer)
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

### `players_rankings` — Classements ATP+WTA
```sql
name TEXT,           -- Format : "Sinner Jannik"
rank INTEGER,
points INTEGER,
country TEXT,
gender TEXT,         -- 'M' (ATP) ou 'F' (WTA)
date_recorded DATE,
PRIMARY KEY (name, gender, date_recorded)
```
- Scraping top 1000 ATP + top 1000 WTA via tennisexplorer
- Date dynamique (datetime.now()) depuis le fix de get_ranking.py
- Matching joueur : LIKE '%last_name%' + gender + date_recorded <= date_match

### `tournament_surfaces`
```sql
name TEXT PRIMARY KEY,
surface TEXT          -- 'Clay', 'Hard', 'Grass', 'Unknown'
```
- Alimentée automatiquement au scraping (nouveau tournoi → insère 'Unknown')
- Mappée via fix_surfaces.py (dict + patterns regex pour séries ITF)
- Corrigeable via set_surface.py

### `predictions`
```sql
id, date, tournament, surface, player1, player2,
predicted_winner, confidence,
p1_elo, p2_elo, p1_elo_surface, p2_elo_surface,
p1_momentum, p2_momentum, h2h_p1_wins, h2h_p2_wins,
actual_winner, correct
```

### `elo_ratings`
```sql
player TEXT UNIQUE,
elo_global, elo_hard, elo_clay, elo_grass REAL DEFAULT 1500,
matches_played INTEGER
```

### `algo_performance`
```sql
version, success_rate, total_predictions, correct_predictions, date
```

---

## 🤖 Agents

### `orchestrator.py`
- Coordonne toute l'équipe
- `setup` : collecte Sackmann 2015-2024 → charge CSV global 2025+ → entraînement → backtest → QA
- `daily_job` : live_collector → predictor → QA → reporter (8h30)
- `retrain_weekly` : dimanche 2h00, réentraîne depuis DB (pas de recollecte)

### `collector.py` (Jeff Sackmann)
- Source : `github.com/JeffSackmann/tennis_atp/master/atp_matches_{year}.csv`
- Collecte : 2015-2024
- Inversion des matchs : chaque match sauvegardé dans les deux sens
- Table cible : `matches`

### `match_collector.py` (ex-collect_2026.py)
- Source : tennisexplorer.com/results/?type=atp-single|wta-single
- Couvre : 2025→aujourd'hui
- Table cible : `matches_2026`
- CSV global cumulatif : `data/csv/tennis_global_atp_wta.csv`
- Surfaces : SURFACE_OVERRIDES > tournament_surfaces (DB) > 'Unknown'
- Rankings : `_get_rank_from_db` → players_rankings (LIKE + gender + date <= match)
  - Fallback : date la plus proche si aucune date <= date_match
- Scores tiebreak propres : "7-6(3)"
- Filtres : UTR, Futures, Davis Cup, exhibitions exclus
- CLI : `py match_collector.py yesterday|range YYYY-MM-DD YYYY-MM-DD|month YYYY M`
- `collect_yesterday()` : job quotidien, appende au CSV global

### `get_ranking.py`
- Source : tennisexplorer.com/ranking/atp-men + wta-women
- Pagination : 50 joueurs/page, top 1000 par défaut
- Sauvegarde : table `players_rankings`
- Format nom en DB : "Sinner Jannik"
- Gender : 'M' pour ATP, 'F' pour WTA (fix : `gender_url == 'atp-men'` et non `'men' in gender_url`)
- Date dynamique : `datetime.now().strftime('%Y-%m-%d')`

### `fix_surfaces.py`
- Mappe ~300+ tournois via dict nommé + patterns regex (Monastir X ITF, Sharm El Sheikh X ITF, etc.)
- À lancer après chaque nouvelle collecte couvrant une nouvelle période
- Intégration dans `_init_db` prévue

### `predictor.py`
- Modèle : GradientBoostingClassifier (200 estimators, lr=0.05, max_depth=4)
- Features : surface, rank_diff, tourney_level, best_of, stats service/retour, dominance ratio, aces, df
- Enrichi par `feature_builder.py` : Elo global + par surface, Momentum L10, H2H
- **Précision : 86.61% | Backtest : 92.80%** (backtest suspect, possible data leakage)
- Entraîne sur table `matches` (Sackmann) — à étendre à `matches_2026`
- Sauvegarde modèle : `data/model.pkl`

### `feature_builder.py`
- Elo global + par surface (recalculé depuis historique)
- Momentum L5 et L10
- H2H (head-to-head)
- Fatigue (matchs sur 7 derniers jours)
- Intégré dans `predictor.py` via `FeatureBuilder()`

### `backtester.py`
- Test sur matchs avec `date >= '20230101'`
- Métriques : taux global + taux sur prédictions > 80%

### `qa_engineer.py`
- 6 tests : modèle chargé, format prédiction, confiance 0-1,
  winner valide, DB non vide, joueur inconnu → {}
- Tous passent ✅

### `reporter.py`
- Mail HTML avec : 5 prédictions > 80%, résultats veille, perf algo
- Seuil confiance : 0.80
- Sauvegarde locale : `reports/report_YYYY-MM-DD.html`

---

## 📊 Sources de données

| Source | Usage | Statut |
|--------|-------|--------|
| Jeff Sackmann ATP | Historique 2015-2024 | ✅ |
| TennisExplorer rankings | Classements ATP+WTA live (top 1000) | ✅ |
| TennisExplorer results | Matchs 2025→aujourd'hui | ✅ |
| The Odds API | Cotes bookmaker + matchs du jour | ✅ (clé dans config.py) |

---

## 🚀 Flow déploiement VM

### Setup initial (une seule fois)
1. Local : `py match_collector.py range 2025-01-01 <today>` → génère `tennis_global_atp_wta.csv`
2. Commit + push sur GitHub (CSV inclus)
3. VM : `git pull` → `py main.py setup`
   - Charge Sackmann 2015-2024 → table `matches`
   - Charge CSV global → table `matches_2026`
   - Entraîne le modèle
   - Lance QA

### Daily (automatique via scheduler)
- 8h30 : `daily_job` → `match_collector.py yesterday` → prédictions → mail
- Dimanche 2h : `retrain_weekly` → réentraîne depuis DB (pas de recollecte)

---

## ✅ Ce qui fonctionne

- Collecte Sackmann 2015-2024 → table `matches`
- Scraping matchs 2025+ : scores propres, surfaces en DB, rankings 98%
- Rankings ATP+WTA : top 1000 paginés, gender correct, date dynamique
- `tournament_surfaces` : nouvelles surfaces auto-insérées, fix_surfaces.py couvre ~300+ tournois
- CSV global cumulatif avec `collect_yesterday()` et déduplication
- Modèle 86% + feature_builder (Elo/Momentum/H2H) intégré
- QA 6/6 ✅
- Scripts utilitaires : show_rankings, set_surface, fix_surfaces, clean_old_rankings

---

## ⚠️ Problèmes connus / En cours

1. **`matches_2026` mal nommée** — couvre 2025→aujourd'hui, renommer en `matches_recent`
2. **Backtest 92% suspect** — possible data leakage à investiguer
3. **`predictor.py` entraîne sur `matches` uniquement** — à étendre à `matches_2026` pour utiliser toute la data
4. **`orchestrator.setup()` ne charge pas encore le CSV global** — à implémenter
5. **VM non déployée** — projet tourne en local Windows
6. **WTA absente de Sackmann** — `collector.py` ne collecte que l'ATP; WTA couverte uniquement via match_collector (2025+)
7. **`fix_surfaces.py` non intégré dans `_init_db`** — à faire pour éviter de le lancer manuellement

---

## 🚀 Prochaines étapes (dans l'ordre)

1. Modifier `orchestrator.setup()` pour charger le CSV global en DB
2. Étendre `predictor.py` pour entraîner sur `matches` + `matches_2026`
3. Intégrer `fix_surfaces.py` dans `_init_db`
4. Scraping 2025-01 → aujourd'hui complet + génération CSV global
5. Déployer sur VM Google Cloud + tmux
6. Tester mail end-to-end (`py main.py test`)
7. Vérifier data leakage dans le backtest
8. Ajouter WTA historique (source à identifier)

---

## 💡 Commandes utiles

```bash
# Setup complet
py main.py setup

# Tester le job quotidien
py main.py test

# Lancer le scheduler 24/7
py main.py run

# Forcer le réentraînement
py main.py retrain

# Scraper les classements ATP+WTA (top 1000)
py get_ranking.py

# Collecte hier (job quotidien)
py match_collector.py yesterday

# Collecte une plage
py match_collector.py range 2025-01-01 2025-12-31

# Collecte un mois
py match_collector.py month 2025 4

# Mapper les surfaces inconnues
py fix_surfaces.py

# Corriger une surface
py set_surface.py "Nom tournoi" Clay
py set_surface.py --list
py set_surface.py --all

# Inspecter les classements
py show_rankings.py
py show_rankings.py --gender M --top 100
py show_rankings.py --search sinner

# Supprimer anciennes données rankings corrompues
py clean_old_rankings.py

# Relancer sur VM
cd tennis-predictor && source venv/bin/activate && tmux attach -t tennis
```