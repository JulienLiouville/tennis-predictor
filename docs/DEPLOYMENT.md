# Deployment

## Environments

| Env | OS | Python | DB |
|---|---|---|---|
| Local | Windows / PyCharm | 3.9 | SQLite |
| Production | Google Cloud VM e2-micro / Ubuntu 22.04 | python3 | SQLite |

---

## Contraintes VM

- **RAM : 1 Go** — `precompute_features.py` fait crasher le VM sur le calcul complet
- `precompute_features.py` tourne **en local uniquement**, puis `scp` de `tennis.db` + `model.pkl`

---

## Setup depuis zéro (VM vierge)

```bash
git clone https://github.com/ton-user/tennis-predictor.git
cd tennis-predictor
bash setup_vm.sh
```

`setup_vm.sh` vérifie la présence de `tennis.db` et `model.pkl`. S'ils sont absents, copier depuis le PC local :

```bash
# depuis PowerShell local
scp data/tennis.db liouville_julien@VM_IP:~/tennis-predictor/data/
scp data/model.pkl liouville_julien@VM_IP:~/tennis-predictor/data/
scp data/csv/tennis_global_atp_wta.csv liouville_julien@VM_IP:~/tennis-predictor/data/csv/
```

---

## Workflow local avant déploiement

```bash
# 1. Collecte delta depuis dernière date CSV
python match_collector.py

# 2. Fix surfaces
python fix_surfaces.py

# 3. Précalcul features (local uniquement)
python precompute_features.py

# 4. Réentraînement
python main.py retrain

# 5. Validation
python quick.py

# 6. Copier vers VM
scp data/tennis.db liouville_julien@VM_IP:~/tennis-predictor/data/
scp data/model.pkl liouville_julien@VM_IP:~/tennis-predictor/data/
scp data/csv/tennis_global_atp_wta.csv liouville_julien@VM_IP:~/tennis-predictor/data/csv/
```

---

## Mise à jour code VM

```bash
cd ~/tennis-predictor
git pull origin main
```

---

## Lancer le scheduler

```bash
tmux new -s tennis
python3 main.py run
# Ctrl+B puis D pour détacher
```

---

## Commandes utiles

```bash
# Tester le job quotidien une fois
python3 main.py test

# Vérifier l'état de la DB
python3 quick.py

# Collecter le delta CSV
python3 match_collector.py

# Naviguer dans tmux
tmux attach -t tennis
Ctrl+B puis C   # nouvelle fenêtre
Ctrl+B puis 0/1 # changer de fenêtre
Ctrl+B puis D   # détacher
tmux kill-session -t tennis  # tuer la session
```

---

## Scheduler prod

| Heure | Job |
|---|---|
| 08h30 quotidien | `daily_job` |
| Dimanche 02h00 | `retrain_weekly` |

`daily_job` :
1. Scrape cotes du jour (The Odds API)
2. Collecte matchs hier (TennisExplorer) → `matches_2026` + CSV
3. Calcule prédictions pending
4. QA
5. Email si QA ok

`retrain_weekly` :
1. Recharge CSV → `matches_2026`
2. Réentraîne modèle
3. Backtest + QA