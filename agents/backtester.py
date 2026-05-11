import pandas as pd
from datetime import datetime
from database import get_connection
from agents.predictor import PredictorAgent


class BacktesterAgent:
    """
    Teste le modèle sur des matchs historiques non vus.
    Utilise le predictor déjà entraîné en mémoire (pas de rechargement pkl).
    """

    def __init__(self):
        self.predictor = PredictorAgent()
        print("✅ BacktesterAgent initialisé")

    def run(self, test_size: int = 1000, predictor: PredictorAgent = None) -> dict:
        print(f"🔄 Backtest sur {test_size} matchs (données non vues)...")

        agent = predictor if (predictor and predictor.is_trained) else self.predictor
        if not agent.is_trained:
            agent.load_model()

        conn = get_connection()

        # player1 = winner uniquement → ground truth cohérent, pas besoin de dédup
        df = pd.read_sql_query('''
            SELECT player1, player2, winner, surface, date,
                   p1_rank, p2_rank
            FROM matches
            WHERE date >= '20230101'
            AND surface IN ('Hard', 'Clay', 'Grass')
            AND winner != '' AND player1 != '' AND player2 != ''
            AND player1 = winner
            ORDER BY date DESC
            LIMIT ?
        ''', conn, params=(test_size,))
        conn.close()

        if df.empty:
            print("❌ Pas de données pour le backtest")
            return {}

        print(f"   {len(df)} matchs sélectionnés")

        correct = 0
        total = 0
        high_conf_correct = 0
        high_conf_total = 0

        for _, row in df.iterrows():
            try:
                pred = agent.predict(
                    row['player1'], row['player2'], row['surface'],
                    p1_rank=int(row['p1_rank'] or 100),
                    p2_rank=int(row['p2_rank'] or 100),
                    date_limit=row['date']
                )
                if not pred or pred.get('status') == 'error':
                    continue

                is_correct = pred['predicted_winner'] == row['winner']
                total += 1
                if is_correct:
                    correct += 1
                if pred['confidence'] >= 0.80:
                    high_conf_total += 1
                    if is_correct:
                        high_conf_correct += 1

            except Exception:
                continue

        overall_rate = correct / total if total > 0 else 0
        high_conf_rate = high_conf_correct / high_conf_total if high_conf_total > 0 else 0

        results = {
            'total_tested': total,
            'overall_success_rate': round(overall_rate, 4),
            'high_confidence_total': high_conf_total,
            'high_confidence_success_rate': round(high_conf_rate, 4),
            'date': datetime.now().strftime('%Y-%m-%d')
        }

        self._save_results(results)
        self._print_report(results)
        return results

    def _save_results(self, results: dict):
        conn = get_connection()
        c = conn.cursor()
        c.execute('''INSERT INTO algo_performance
            (version, success_rate, total_predictions, correct_predictions, date)
            VALUES (?, ?, ?, ?, ?)''', (
            'v2',
            results['overall_success_rate'],
            results['total_tested'],
            int(results['overall_success_rate'] * results['total_tested']),
            results['date']
        ))
        conn.commit()
        conn.close()

    def _print_report(self, results: dict):
        print("\n" + "=" * 50)
        print("📊 RAPPORT DE BACKTEST")
        print("=" * 50)
        print(f"Matchs testés      : {results['total_tested']}")
        print(f"Taux global        : {results['overall_success_rate']:.2%}")
        print(f"Prédictions >80%   : {results['high_confidence_total']}")
        print(f"Taux sur >80%      : {results['high_confidence_success_rate']:.2%}")
        print("=" * 50 + "\n")


if __name__ == "__main__":
    agent = BacktesterAgent()
    agent.run(test_size=1000)