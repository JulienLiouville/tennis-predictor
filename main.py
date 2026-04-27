import sys
from agents.orchestrator import OrchestratorAgent


def main():
    print("""
    ╔══════════════════════════════════╗
    ║     🎾 TENNIS PREDICTOR BOT      ║
    ║     Multi-Agent AI System        ║
    ╚══════════════════════════════════╝
    """)

    orchestrator = OrchestratorAgent()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "setup":
            success = orchestrator.setup()
            if success:
                print("\n✅ Setup terminé ! Lance 'py main.py run' pour démarrer")
            else:
                print("\n❌ Setup échoué - Vérifie les erreurs ci-dessus")

        elif command == "run":
            orchestrator.run_scheduler()

        elif command == "test":
            orchestrator.daily_job()

        elif command == "retrain":
            orchestrator.retrain_weekly()

        else:
            print(f"❌ Commande inconnue : {command}")
            print_help()
    else:
        print_help()


def print_help():
    print("""
    Usage : py main.py <commande>

    Commandes disponibles :
    ┌─────────────────────────────────────────────────────────────┐
    │ setup    → Premier lancement : charge CSV + entraîne        │
    │ run      → Lance le scheduler (mail à 8h30/jour)            │
    │ test     → Teste le job quotidien une seule fois            │
    │ retrain  → Force le réentraînement du modèle                │
    └─────────────────────────────────────────────────────────────┘

    Prérequis setup :
      data/csv/tennis_global_atp_wta.csv  ← CSV historique 2025+
      data/model.pkl sera généré automatiquement
    """)


if __name__ == "__main__":
    main()