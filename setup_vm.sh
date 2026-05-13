#!/bin/bash
# =============================================================================
# setup_vm.sh — Tennis Predictor — Setup complet depuis zéro
# Usage : bash setup_vm.sh
# =============================================================================

set -e  # arrête le script si une commande échoue

echo ""
echo "============================================================"
echo " TENNIS PREDICTOR — SETUP VM"
echo "============================================================"

# ─── 1. SYSTÈME ──────────────────────────────────────────────────────────────
echo ""
echo "[1/6] Mise à jour système..."
sudo apt-get update -q
sudo apt-get install -y python3 python3-pip python3-venv tmux git

# ─── 2. REPO ─────────────────────────────────────────────────────────────────
echo ""
echo "[2/6] Récupération du repo..."
if [ -d "tennis-predictor" ]; then
    echo "  Repo existant → git pull"
    cd tennis-predictor
    git pull origin main
else
    git clone https://github.com/ton-user/tennis-predictor.git
    cd tennis-predictor
fi

# ─── 3. DÉPENDANCES ──────────────────────────────────────────────────────────
echo ""
echo "[3/6] Installation des dépendances Python..."
pip3 install -r requirements.txt --quiet

# ─── 4. DOSSIERS ─────────────────────────────────────────────────────────────
echo ""
echo "[4/6] Création des dossiers..."
mkdir -p data/csv reports

# ─── 5. VÉRIFICATION DB ──────────────────────────────────────────────────────
echo ""
echo "[5/6] Vérification de la base de données..."
if [ ! -f "data/tennis.db" ]; then
    echo ""
    echo "  ⚠️  data/tennis.db introuvable."
    echo "  Deux options :"
    echo ""
    echo "  Option A — Copier depuis ton PC local (recommandé, plus rapide) :"
    echo "    scp data/tennis.db liouville_julien@VM_IP:~/tennis-predictor/data/"
    echo "    scp data/csv/tennis_global_atp_wta.csv liouville_julien@VM_IP:~/tennis-predictor/data/csv/"
    echo ""
    echo "  Option B — Reconstruire depuis zéro (lent, ~30 min) :"
    echo "    python3 main.py setup"
    echo ""
    echo "  Lance ensuite la suite manuellement :"
    echo "    python3 fix_csv_and_db.py"
    echo "    python3 precompute_features.py"
    echo "    python3 precompute_features_2026.py"
    echo "    python3 main.py retrain"
    echo "    python3 quick.py"
    echo "    python3 main.py run"
    exit 0
fi

# ─── 6. PIPELINE ─────────────────────────────────────────────────────────────
echo ""
echo "[6/6] Pipeline..."

echo "  → fix_csv_and_db.py"
python3 fix_csv_and_db.py

echo "  → precompute_features.py"
python3 precompute_features.py

echo "  → precompute_features_2026.py"
python3 precompute_features_2026.py

echo "  → retrain"
python3 main.py retrain

echo "  → validation"
python3 quick.py

# ─── DONE ─────────────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo " SETUP TERMINÉ"
echo " Lance le scheduler dans tmux :"
echo "   tmux new -s tennis"
echo "   python3 main.py run"
echo "============================================================"