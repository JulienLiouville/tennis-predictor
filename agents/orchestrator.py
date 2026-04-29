import schedule
import time
import csv
import os
from datetime import datetime
from database import init_db, get_connection
from agents.collector import CollectorAgent
from agents.predictor import PredictorAgent
from agents.backtester import BacktesterAgent
from agents.qa_engineer import QAEngineerAgent
from agents.reporter import ReporterAgent

CSV_PATH = "data/csv/tennis_global_atp_wta.csv"


class OrchestratorAgent:
    """
    Agent orchestrateur : coordonne toute l'équipe
    et prend les décisions sur le flow quotidien
    """

    def __init__(self):
        print("🚀 Initialisation de l'équipe...")
        os.makedirs("data", exist_ok=True)
        os.makedirs("reports", exist_ok=True)
        init_db()
        self.collector  = CollectorAgent()
        self.predictor  = PredictorAgent()
        self.backtester = BacktesterAgent()
        self.qa         = QAEngineerAgent()
        self.reporter   = ReporterAgent()
        print("✅ Équipe prête !")

    # ─── CHARGEMENT CSV GLOBAL ────────────────────────────────────────────────

    def load_csv_to_db(self):
        """
        Charge le CSV global (2025→aujourd'hui) dans matches_2026.
        Idempotent : INSERT OR IGNORE sur la contrainte UNIQUE(date, player1, player2, tour).
        """
        if not os.path.exists(CSV_PATH):
            print(f"⚠️  CSV introuvable : {CSV_PATH}")
            print("   Lance : py match_collector.py range 2025-01-01 <today>")
            return 0

        print(f"📥 Chargement du CSV global → matches_2026...")
        conn = get_connection()
        c = conn.cursor()
        inserted = 0
        skipped = 0

        with open(CSV_PATH, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    c.execute('''
                        INSERT OR IGNORE INTO matches_2026
                        (date, time, tour, tournament, surface, best_of,
                         player1, player2, winner, score,
                         sets_won_p1, sets_won_p2, num_sets,
                         odds_p1, odds_p2,
                         p1_rank, p1_points, p1_country,
                         p2_rank, p2_points, p2_country,
                         ranking_date_used)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ''', (
                        row.get('date'), row.get('time'), row.get('tour'),
                        row.get('tournament'), row.get('surface'),
                        row.get('best_of') or 3,
                        row.get('player1'), row.get('player2'), row.get('winner'),
                        row.get('score'),
                        row.get('sets_won_p1'), row.get('sets_won_p2'), row.get('num_sets'),
                        row.get('odds_p1') or None, row.get('odds_p2') or None,
                        row.get('p1_rank') or None, row.get('p1_points') or None,
                        row.get('p1_country'),
                        row.get('p2_rank') or None, row.get('p2_points') or None,
                        row.get('p2_country'),
                        row.get('ranking_date_used'),
                    ))
                    if c.rowcount:
                        inserted += 1
                    else:
                        skipped += 1
                except Exception as e:
                    print(f"  ⚠️  Ligne ignorée ({row.get('date')} {row.get('player1')}): {e}")

        conn.commit()
        conn.close()
        print(f"✅ CSV chargé : {inserted} insérés, {skipped} déjà présents")
        return inserted

    # ─── SETUP ────────────────────────────────────────────────────────────────

    def setup(self):
        """
        Setup initial complet. À lancer une seule fois.
        1. Sackmann 2015-2024 → matches
        2. CSV global → matches_2026
        3. Entraînement
        4. Backtest
        5. QA
        """
        print("\n" + "="*50)
        print("⚙️  SETUP INITIAL")
        print("="*50)

        # 1. Collecte Sackmann 2015-2024
        print("\n📥 Étape 1 : Collecte historique Sackmann 2015-2024...")
        years = list(range(2015, 2025))
        self.collector.collect_and_save(years)

        # 2. CSV global 2025+
        print("\n📥 Étape 2 : Chargement CSV global 2025+...")
        self.load_csv_to_db()

        # 3. Entraînement
        print("\n🧠 Étape 3 : Entraînement du modèle...")
        accuracy = self.predictor.train()

        # 4. Backtest
        print("\n📊 Étape 4 : Backtest...")
        backtest = self.backtester.run(test_size=1000)

        # 5. QA
        print("\n🧪 Étape 5 : Validation QA...")
        qa_report = self.qa.run()

        if qa_report['validated']:
            print("\n✅ Setup terminé - Système prêt !")
            print(f"   Précision modèle : {accuracy:.2%}")
            print(f"   Taux backtest    : {backtest.get('overall_success_rate', 0):.2%}")
        else:
            print("\n⚠️  QA non validé - Vérifier les erreurs")

        return qa_report['validated']

    # ─── JOB QUOTIDIEN ────────────────────────────────────────────────────────

    def daily_job(self):
        print("\n" + "="*50)
        print(f"📅 JOB QUOTIDIEN - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        print("="*50)

        # 1. Collecte matchs du jour via The Odds API
        from agents.live_collector import LiveCollectorAgent
        live_collector = LiveCollectorAgent()
        live_collector.run()

        # 2. Collecte matchs hier via tennisexplorer → matches_2026 + CSV
        from match_collector import MatchCollector
        collector = MatchCollector()
        collector.collect_yesterday()

        # 3. Prédictions
        self.predictor.load_model()
        self.predictor.process_pending_predictions()

        # 4. QA rapide
        qa_report = self.qa.run()

        # 5. Rapport mail
        if qa_report['validated']:
            self.reporter.run()
            print("✅ Job quotidien terminé avec succès !")
            return True
        else:
            print("❌ QA échoué - rapport non envoyé")
            return False

    # ─── RETRAIN ──────────────────────────────────────────────────────────────

    def retrain_weekly(self):
        """
        Réentraînement hebdomadaire.
        Ne recollecte PAS Sackmann (déjà en DB).
        Recharge le CSV global pour intégrer les matchs récents accumulés.
        """
        print("\n🔄 Réentraînement hebdomadaire...")

        # Recharge le CSV global (matchs récents accumulés par collect_yesterday)
        print("📥 Mise à jour matches_2026 depuis CSV global...")
        self.load_csv_to_db()

        # Réentraîne depuis DB complète (Sackmann + récents)
        accuracy = self.predictor.train()

        # Backtest
        backtest = self.backtester.run(test_size=2000)

        # QA
        qa_report = self.qa.run()

        print(f"\n✅ Réentraînement terminé")
        print(f"   Nouvelle précision : {accuracy:.2%}")
        print(f"   Nouveau backtest   : {backtest.get('overall_success_rate', 0):.2%}")

    # ─── SCHEDULER ────────────────────────────────────────────────────────────

    def run_scheduler(self):
        """Lance le scheduler pour automatiser les tâches"""
        print("\n⏰ Scheduler démarré...")
        print("   Mail quotidien    : 08h30")
        print("   Réentraînement    : dimanche 02h00")

        schedule.every().day.at("08:30").do(self.daily_job)
        schedule.every().sunday.at("02:00").do(self.retrain_weekly)

        while True:
            schedule.run_pending()
            time.sleep(60)


if __name__ == "__main__":
    import sys
    orchestrator = OrchestratorAgent()

    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        orchestrator.setup()
    else:
        orchestrator.run_scheduler()