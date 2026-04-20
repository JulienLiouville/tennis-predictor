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
            # Premier lancement : collecte + entraînement + backtest
            success = orchestrator.setup()
            if success:
                print("\n✅ Setup terminé ! Lance 'python main.py run' pour démarrer")
            else:
                print("\n❌ Setup échoué - Vérifie les erreurs ci-dessus")

        elif command == "run":
            # Lance le scheduler quotidien
            orchestrator.run_scheduler()

        elif command == "test":
            # Lance juste le job quotidien une fois (pour tester)
            orchestrator.daily_job()

        elif command == "retrain":
            # Force le réentraînement
            orchestrator.retrain_weekly()

        else:
            print(f"❌ Commande inconnue : {command}")
            print_help()
    else:
        print_help()

def print_help():
    print("""
    Usage : python main.py <commande>

    Commandes disponibles :
    ┌─────────────────────────────────────────────────────┐
    │ setup    → Premier lancement : collecte + entraîne  │
    │ run      → Lance le scheduler (mail à 8h30/jour)    │
    │ test     → Teste le job quotidien une seule fois    │
    │ retrain  → Force le réentraînement du modèle        │
    └─────────────────────────────────────────────────────┘
    """)

if __name__ == "__main__":
    main()
