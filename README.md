# 🎾 Tennis Predictor

Plateforme multi-agents de machine learning pour prédictions ATP/WTA.

## Features

- Scraping ATP/WTA (TennisExplorer + The Odds API)
- Base historique Sackmann 2015-2024
- Feature engineering (momentum, H2H, fatigue)
- Modèle GradientBoosting
- Backtesting
- Email quotidien automatisé (08h30)
- Architecture multi-agents

## Quick Start

```bash
# 1. Setup initial (local)
python match_collector.py          # collecte CSV 2025+
python fix_surfaces.py             # normalise les surfaces
python precompute_features.py      # calcule les features (local uniquement)
python main.py retrain             # entraîne le modèle
python quick.py                    # validation

# 2. Déploiement VM
scp data/tennis.db liouville_julien@VM_IP:~/tennis-predictor/data/
scp data/model.pkl liouville_julien@VM_IP:~/tennis-predictor/data/
scp data/csv/tennis_global_atp_wta.csv liouville_julien@VM_IP:~/tennis-predictor/data/csv/

# 3. VM
git pull origin main
tmux new -s tennis
python3 main.py run
```

## Main Commands

| Commande | Description |
|---|---|
| `python main.py setup` | Setup initial complet |
| `python main.py run` | Lance le scheduler prod |
| `python main.py test` | Teste le job quotidien une fois |
| `python main.py retrain` | Force le réentraînement |
| `python precompute_features.py` | Calcule les features (local) |
| `python match_collector.py` | Collecte delta CSV |
| `python fix_surfaces.py` | Normalise les surfaces |
| `python quick.py` | Validation complète de la DB |

## ⚠️ Contraintes importantes

- `precompute_features.py` tourne **en local uniquement** (VM e2-micro OOM)
- Split train/test **temporel obligatoire** — pas de `random_state=42`
- Ne jamais supprimer `tennis.db` en production

## Documentation

- `docs/ARCHITECTURE.md`
- `docs/KNOWN_ISSUES.md`
- `docs/ROADMAP.md`
- `docs/DEPLOYMENT.md`
- `docs/LEAKAGE_PREVENTION.md`
- `docs/MODEL_DECISIONS.md`
- `docs/PROJECT_CONTEXT.md`