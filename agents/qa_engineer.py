import unittest
from database import get_connection
from agents.predictor import PredictorAgent

class TennisTests(unittest.TestCase):
    def setUp(self):
        self.predictor = PredictorAgent()
        self.predictor.load_model()
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT DISTINCT player1 FROM matches LIMIT 2")
        rows = c.fetchall()
        c.execute("SELECT DISTINCT surface FROM matches WHERE surface NOT IN ('', 'None') LIMIT 1")
        row = c.fetchone()
        conn.close()
        self.player1 = rows[0][0] if len(rows) > 0 else ""
        self.player2 = rows[1][0] if len(rows) > 1 else ""
        self.surface = row[0] if row else "Hard"

    def test_model_loaded(self):
        self.assertTrue(self.predictor.is_trained)

    def test_prediction_format(self):
        if not self.player1 or not self.player2:
            self.skipTest("Pas de joueurs")
        r = self.predictor.predict(self.player1, self.player2, self.surface)
        self.assertIn("predicted_winner", r)
        self.assertIn("confidence", r)

    def test_confidence_range(self):
        if not self.player1 or not self.player2:
            self.skipTest("Pas de joueurs")
        r = self.predictor.predict(self.player1, self.player2, self.surface)
        if r:
            self.assertGreaterEqual(r["confidence"], 0)
            self.assertLessEqual(r["confidence"], 1)

    def test_winner_is_one_of_players(self):
        if not self.player1 or not self.player2:
            self.skipTest("Pas de joueurs")
        r = self.predictor.predict(self.player1, self.player2, self.surface)
        if r:
            self.assertIn(r["predicted_winner"], [self.player1, self.player2])

    def test_database_has_data(self):
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM matches")
        count = c.fetchone()[0]
        conn.close()
        self.assertGreater(count, 0)

    def test_unknown_player_handling(self):
        """Vérifie que l'agent gère proprement les joueurs inconnus"""
        r = self.predictor.predict("Inconnu XYZ", "Inconnu ABC", "Hard")

        # On vérifie que ce n'est pas vide
        self.assertIsNotNone(r)

        # Un joueur inconnu reçoit Elo=1500 (défaut) → prédiction valide
        self.assertIn(r.get('status'), ['success', 'unknown_player'])
        # La confiance doit être dans [0, 1]
        self.assertGreaterEqual(r.get('confidence', 0), 0)
        self.assertLessEqual(r.get('confidence', 1), 1)

class QAEngineerAgent:
    def __init__(self):
        print("✅ QAEngineerAgent initialisé")

    def run(self):
        print("🧪 Tests en cours...")
        suite = unittest.TestLoader().loadTestsFromTestCase(TennisTests)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        total = result.testsRun
        failed = len(result.failures) + len(result.errors)
        passed = total - failed
        report = {
            "total_tests": total, "passed": passed, "failed": failed,
            "success_rate": round(passed/total, 4) if total > 0 else 0,
            "failures": [str(f) for f in result.failures],
            "errors": [str(e) for e in result.errors],
            "validated": failed == 0
        }
        print(f"\n{'='*40}\n🧪 QA : {passed}/{total} ({'✅ VALIDÉ' if report['validated'] else '❌ ÉCHEC'})\n{'='*40}")
        return report