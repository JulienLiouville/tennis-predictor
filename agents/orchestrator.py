import schedule
import time
from datetime import datetime
from database import init_db
from agents.collector import CollectorAgent
from agents.predictor import PredictorAgent
from agents.backtester import BacktesterAgent
from agents.qa_engineer import QAEngineerAgent
from agents.reporter import ReporterAgent

class OrchestratorAgent:
    """
    Agent orchestrateur : coordonne toute l'équipe
    et prend les décisions sur le flow quotidien
    """

    def __init__(self):
        print("🚀 Initialisation de l'équipe...")
        init_db()
        self.collector  = CollectorAgent()
        self.predictor  = PredictorAgent()
        self.backtester = BacktesterAgent()
        self.qa         = QAEngineerAgent()
        self.reporter   = ReporterAgent()
        print("✅ Équipe prête !")

    def setup(self):
        """
        Setup initial : collecte historique + entraînement
        À lancer une seule fois au démarrage
        """
        print("\n" + "="*50)
        print("⚙️  SETUP INITIAL")
        print("="*50)

        # 1. Collecte des données historiques
        print("\n📥 Étape 1 : Collecte des données historiques...")
        self.collector.collect_and_save([2022, 2023, 2024])

        # 2. Entraînement du modèle
        print("\n🧠 Étape 2 : Entraînement du modèle...")
        accuracy = self.predictor.train()

        # 3. Backtest
        print("\n📊 Étape 3 : Backtest...")
        backtest = self.backtester.run(test_size=1000)

        # 4. QA
        print("\n🧪 Étape 4 : Validation QA...")
        qa_report = self.qa.run()

        # Décision de l'orchestrateur
        if qa_report['validated']:
            print("\n✅ Setup terminé - Système prêt !")
            print(f"   Précision modèle  : {accuracy:.2%}")
            print(f"   Taux backtest     : {backtest.get('overall_success_rate', 0):.2%}")
        else:
            print("\n⚠️  QA non validé - Vérifier les erreurs")

        return qa_report['validated']

    def daily_job(self):
        """
        Job quotidien : prédit les matchs du jour
        et envoie le rapport
        """
        print("\n" + "="*50)
        print(f"📅 JOB QUOTIDIEN - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        print("="*50)

        # 1. Vérifie que le modèle est à jour
        print("\n🔄 Vérification du modèle...")
        self.predictor.load_model()

        if not self.predictor.is_trained:
            print("⚠️  Modèle non entraîné, entraînement...")
            self.predictor.train()

        # 2. QA rapide avant envoi
        print("\n🧪 QA rapide...")
        qa_report = self.qa.run()

        if not qa_report['validated']:
            print("❌ QA échoué - Mail annulé aujourd'hui")
            return False

        # 3. Envoi du rapport
        print("\n📧 Envoi du rapport...")
        success = self.reporter.run()

        if success:
            print("✅ Job quotidien terminé avec succès !")
        else:
            print("❌ Erreur lors de l'envoi du rapport")

        return success

    def retrain_weekly(self):
        """
        Réentraînement hebdomadaire avec les nouvelles données
        Pour améliorer l'algo progressivement
        """
        print("\n🔄 Réentraînement hebdomadaire...")

        # Collecte les données récentes
        current_year = datetime.now().year
        self.collector.collect_and_save([current_year])

        # Réentraîne
        accuracy = self.predictor.train()

        # Backtest sur les nouvelles données
        backtest = self.backtester.run(test_size=2000)

        # QA
        qa_report = self.qa.run()

        print(f"✅ Réentraînement terminé")
        print(f"   Nouvelle précision : {accuracy:.2%}")
        print(f"   Nouveau backtest   : {backtest.get('overall_success_rate', 0):.2%}")

    def run_scheduler(self):
        """Lance le scheduler pour automatiser les tâches"""
        print("\n⏰ Scheduler démarré...")
        print("   Mail quotidien    : 08h30")
        print("   Réentraînement    : dimanche 02h00")

        # Mail tous les jours à 8h30
        schedule.every().day.at("08:30").do(self.daily_job)

        # Réentraînement chaque dimanche à 2h du matin
        schedule.every().sunday.at("02:00").do(self.retrain_weekly)

        while True:
            schedule.run_pending()
            time.sleep(60)  # vérifie toutes les minutes


if __name__ == "__main__":
    orchestrator = OrchestratorAgent()

    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        orchestrator.setup()
    else:
        orchestrator.run_scheduler()
