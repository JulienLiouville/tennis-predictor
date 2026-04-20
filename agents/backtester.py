import pandas as pd
from datetime import datetime
from database import get_connection
from agents.predictor import PredictorAgent

class BacktesterAgent:
    """
    Agent backtesteur : teste l'algo sur des matchs
    historiques pour mesurer la vraie performance
    """

    def __init__(self):
        self.predictor = PredictorAgent()
        print("✅ BacktesterAgent initialisé")

    def run(self, test_size: int = 1000) -> dict:
        """
        Lance le backtest sur les derniers matchs historiques
        test_size : nombre de matchs à tester
        """
        print(f"🔄 Backtest sur {test_size} matchs...")

        # Charge les données de test
        conn = get_connection()
        df = pd.read_sql_query(f"""
            SELECT player1, player2, winner, surface
            FROM matches
            WHERE surface IN ('Hard', 'Clay', 'Grass')
            ORDER BY date DESC
            LIMIT {test_size}
        """, conn)
        conn.close()

        if df.empty:
            print("❌ Pas de données pour le backtest")
            return {}

        # Charge le modèle
        self.predictor.load_model()

        correct = 0
        total = 0
        high_confidence_correct = 0
        high_confidence_total = 0
        results = []

        for _, row in df.iterrows():
            try:
                prediction = self.predictor.predict(
                    row['player1'],
                    row['player2'],
                    row['surface']
                )

                if not prediction:
                    continue

                is_correct = prediction['predicted_winner'] == row['winner']
                total += 1

                if is_correct:
                    correct += 1

                # Stats sur les prédictions > 80% confiance
                if prediction['confidence'] >= 0.80:
                    high_confidence_total += 1
                    if is_correct:
                        high_confidence_correct += 1

                results.append({
                    'player1': row['player1'],
                    'player2': row['player2'],
                    'predicted': prediction['predicted_winner'],
                    'actual': row['winner'],
                    'confidence': prediction['confidence'],
                    'correct': is_correct
                })

            except Exception:
                continue

        # Calcul des stats finales
        overall_rate = correct / total if total > 0 else 0
        high_conf_rate = (
            high_confidence_correct / high_confidence_total
            if high_confidence_total > 0 else 0
        )

        results_summary = {
            'total_tested': total,
            'overall_success_rate': round(overall_rate, 4),
            'high_confidence_total': high_confidence_total,
            'high_confidence_success_rate': round(high_conf_rate, 4),
            'date': datetime.now().strftime('%Y-%m-%d')
        }

        self._save_results(results_summary)
        self._print_report(results_summary)

        return results_summary

    def _save_results(self, results: dict):
        """Sauvegarde les résultats du backtest"""
        conn = get_connection()
        c = conn.cursor()
        c.execute('''INSERT INTO algo_performance
            (version, success_rate, total_predictions,
             correct_predictions, date)
            VALUES (?, ?, ?, ?, ?)''', (
            'v1',
            results['overall_success_rate'],
            results['total_tested'],
            int(results['overall_success_rate'] * results['total_tested']),
            results['date']
        ))
        conn.commit()
        conn.close()

    def _print_report(self, results: dict):
        """Affiche le rapport de backtest"""
        print("\n" + "="*50)
        print("📊 RAPPORT DE BACKTEST")
        print("="*50)
        print(f"Matchs testés      : {results['total_tested']}")
        print(f"Taux global        : {results['overall_success_rate']:.2%}")
        print(f"Prédictions >80%   : {results['high_confidence_total']}")
        print(f"Taux sur >80%      : {results['high_confidence_success_rate']:.2%}")
        print("="*50 + "\n")

if __name__ == "__main__":
    agent = BacktesterAgent()
    agent.run(test_size=1000)
