import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from database import get_connection
from config import EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER

class ReporterAgent:
    """
    Agent reporter : génère et envoie le mail
    quotidien avec les prédictions et résultats
    """

    def __init__(self):
        print("✅ ReporterAgent initialisé")

    def get_todays_predictions(self) -> list:
        """Récupère les prédictions du jour > 80% confiance"""
        conn = get_connection()
        c = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        c.execute("""
            SELECT player1, player2, predicted_winner,
                   confidence, surface
            FROM predictions
            WHERE date = ? AND confidence >= 0.80
            ORDER BY confidence DESC
            LIMIT 5
        """, (today,))
        rows = c.fetchall()
        conn.close()
        return rows

    def get_yesterday_results(self) -> list:
        """Récupère les résultats des prédictions de la veille"""
        conn = get_connection()
        c = conn.cursor()
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        c.execute("""
            SELECT player1, player2, predicted_winner,
                   actual_winner, confidence, correct
            FROM predictions
            WHERE date = ? AND actual_winner IS NOT NULL
        """, (yesterday,))
        rows = c.fetchall()
        conn.close()
        return rows

    def get_algo_performance(self) -> dict:
        """Récupère les stats de performance globale"""
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT success_rate, total_predictions
            FROM algo_performance
            ORDER BY created_at DESC
            LIMIT 1
        """)
        row = c.fetchone()
        conn.close()
        if row:
            return {
                'success_rate': row[0],
                'total_predictions': row[1]
            }
        return {'success_rate': 0, 'total_predictions': 0}

    def build_email(self, predictions: list,
                    yesterday: list, perf: dict) -> str:
        """Construit le contenu HTML du mail"""

        # Section prédictions du jour
        pred_html = ""
        if predictions:
            for p in predictions:
                player1, player2, winner, conf, surface = p
                emoji = "🎾"
                pred_html += f"""
                <tr>
                    <td>{emoji} {player1} vs {player2}</td>
                    <td><b>{winner}</b></td>
                    <td>{surface}</td>
                    <td><b>{conf:.0%}</b></td>
                </tr>"""
        else:
            pred_html = "<tr><td colspan='4'>Aucune prédiction > 80% aujourd'hui</td></tr>"

        # Section résultats hier
        results_html = ""
        if yesterday:
            correct = sum(1 for r in yesterday if r[5] == 1)
            total = len(yesterday)
            results_html = f"<p>✅ {correct}/{total} prédictions correctes hier</p>"
            for r in yesterday:
                player1, player2, predicted, actual, conf, correct_bet = r
                icon = "✅" if correct_bet else "❌"
                results_html += f"""
                <p>{icon} {player1} vs {player2} 
                → Prédit: <b>{predicted}</b> 
                | Réel: <b>{actual}</b></p>"""
        else:
            results_html = "<p>Pas de résultats à afficher pour hier</p>"

        html = f"""
        <html><body style="font-family: Arial; max-width: 600px; margin: auto;">
            <h1>🎾 Tennis Predictor - {datetime.now().strftime('%d/%m/%Y')}</h1>

            <h2>📊 Performance globale de l'algo</h2>
            <p>Taux de réussite : <b>{perf['success_rate']:.2%}</b>
            sur {perf['total_predictions']} prédictions</p>

            <h2>🎯 Prédictions du jour (confiance > 80%)</h2>
            <table border="1" cellpadding="8" cellspacing="0" width="100%">
                <tr style="background:#f0f0f0">
                    <th>Match</th>
                    <th>Vainqueur prédit</th>
                    <th>Surface</th>
                    <th>Confiance</th>
                </tr>
                {pred_html}
            </table>

            <h2>📈 Résultats d'hier</h2>
            {results_html}

            <hr>
            <p style="color:gray; font-size:12px">
            Tennis Predictor Bot | Généré automatiquement
            </p>
        </body></html>
        """
        return html

    def send_email(self, html_content: str) -> bool:
        """Envoie le mail via Gmail SMTP"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🎾 Tennis Predictions - {datetime.now().strftime('%d/%m/%Y')}"
            msg['From'] = EMAIL_SENDER
            msg['To'] = EMAIL_RECEIVER

            msg.attach(MIMEText(html_content, 'html'))

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER,
                                msg.as_string())

            print("✅ Mail envoyé avec succès !")
            return True

        except Exception as e:
            print(f"❌ Erreur envoi mail: {e}")
            return False

    def run(self) -> bool:
        """Lance la génération et l'envoi du rapport"""
        print("📧 Génération du rapport quotidien...")

        predictions = self.get_todays_predictions()
        yesterday = self.get_yesterday_results()
        perf = self.get_algo_performance()

        html = self.build_email(predictions, yesterday, perf)

        # Sauvegarde locale du rapport
        today = datetime.now().strftime('%Y-%m-%d')
        with open(f"reports/report_{today}.html", 'w') as f:
            f.write(html)
        print(f"💾 Rapport sauvegardé dans reports/report_{today}.html")

        return self.send_email(html)


if __name__ == "__main__":
    agent = ReporterAgent()
    agent.run()
