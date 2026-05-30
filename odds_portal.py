import asyncio
import random
from bs4 import BeautifulSoup
import pandas as pd
from playwright.async_api import async_playwright


class OddsPortalTennisScraper:
    """Classe unique gérant l'extraction complète des cotes de tennis sur OddsPortal

    pour aujourd'hui et demain.
    """

    def __init__(self):
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        self.endpoints = {
            "Aujourd'hui": "https://www.oddsportal.com/matches/tennis/today/",
            "Demain": "https://www.oddsportal.com/matches/tennis/tomorrow/",
        }

    def _parse_html_frame(self, html_content: str) -> list[dict]:
        """Méthode interne : Extrait les données de match visibles dans le HTML fourni."""
        soup = BeautifulSoup(html_content, "html.parser")
        extracted = []

        # Ciblage via l'attribut de test stable d'OddsPortal
        match_rows = soup.find_all(
            "div", class_="group flex", attrs={"data-testid": "game-row"}
        )

        for row in match_rows:
            try:
                # Récupération de l'heure / statut du live
                time_container = row.find("div", {"data-testid": "time-item"})
                match_time = (
                    time_container.get_text(strip=True)
                    if time_container
                    else "N/A"
                )

                # Récupération des joueurs
                player_elements = row.find_all("p", class_="participant-name")
                if len(player_elements) < 2:
                    continue
                p1, p2 = (
                    player_elements[0].get_text(strip=True),
                    player_elements[1].get_text(strip=True),
                )

                # Récupération des deux cotes principales
                odds_elements = row.find_all(
                    "p", {"data-testid": "odd-container-default"}
                )
                c1 = (
                    odds_elements[0].get_text(strip=True)
                    if len(odds_elements) > 0
                    else "-"
                )
                c2 = (
                    odds_elements[1].get_text(strip=True)
                    if len(odds_elements) > 1
                    else "-"
                )

                extracted.append(
                    {
                        "Statut/Heure": match_time,
                        "Joueur 1": p1,
                        "Joueur 2": p2,
                        "Cote 1": c1,
                        "Cote 2": c2,
                    }
                )
            except Exception:
                continue

        return extracted

    async def _scrape_single_url(self, page_instance, url: str) -> list[dict]:
        """Méthode interne : Gère le scroll humain pas-à-pas et accumule les matchs au vol."""
        matches_dict = {}

        print(f"🌍 Connexion à : {url}")
        await page_instance.goto(url, wait_until="networkidle", timeout=60000)
        await page_instance.wait_for_selector(
            "div[data-testid='game-row']", timeout=15000
        )

        current_scroll = 0
        total_height = await page_instance.evaluate("document.body.scrollHeight")
        loop_count = 0

        while current_scroll < total_height:
            # 1. Descente par pas irréguliers
            step = random.randint(300, 500)
            current_scroll += step
            await page_instance.evaluate(f"window.scrollTo(0, {current_scroll});")

            # Simulation de mouvement de souris
            await page_instance.mouse.move(
                random.randint(400, 800), random.randint(300, 600)
            )

            # 2. Gestion de la "respiration" anti-blocage (Briser le palier des 75)
            loop_count += 1
            if loop_count % 5 == 0:
                current_scroll -= 150  # Légère remontée de relecture
                await page_instance.evaluate(
                    f"window.scrollTo(0, {current_scroll});"
                )
                await asyncio.sleep(2.0)  # Pause pour laisser le flux se recharger
                current_scroll += 150
            else:
                await asyncio.sleep(random.uniform(0.5, 0.8))

            # 3. Capture et parsing de la vue actuelle
            html_content = await page_instance.content()
            visible_matches = self._parse_html_frame(html_content)

            for m in visible_matches:
                match_key = f"{m['Joueur 1']} vs {m['Joueur 2']}"
                if match_key not in matches_dict:
                    matches_dict[match_key] = m

            # Recalcul de la hauteur du DOM qui grandit dynamiquement
            total_height = await page_instance.evaluate(
                "document.body.scrollHeight"
            )

        return list(matches_dict.values())

    async def run(self) -> pd.DataFrame:
        """Méthode principale : Lance le pipeline complet pour aujourd'hui et demain

        et retourne un DataFrame global unifié.
        """
        global_dataset = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=self.user_agent,
            )
            page = await context.new_page()

            # Boucle sur nos deux endpoints cibles
            for label, url in self.endpoints.items():
                print(f"\n🚀 Extraction de la catégorie : {label}")
                page_matches = await self._scrape_single_url(page, url)

                # Marquage de la période temporelle pour vos prédictions
                for match in page_matches:
                    match["Période"] = label
                    global_dataset.append(match)

                # Pause de courtoisie entre les deux requêtes lourdes
                print(
                    "🕒 Transition vers l'endpoint suivant, temporisation..."
                )
                await asyncio.sleep(random.uniform(4.0, 6.0))

            await browser.close()

        # Transformation finale en DataFrame Pandas
        if global_dataset:
            df = pd.DataFrame(global_dataset)
            # Réorganisation esthétique des colonnes
            columns_order = [
                "Période",
                "Statut/Heure",
                "Joueur 1",
                "Cote 1",
                "Joueur 2",
                "Cote 2",
            ]
            return df[columns_order]
        return pd.DataFrame()


# --- POINT D'ENTRÉE DU SCRIPT ---
async def main():
    scraper = OddsPortalTennisScraper()
    df_resultats = await scraper.run()

    if not df_resultats.empty:
        print(f"\n🏆 TERMINÉ ! {len(df_resultats)} matchs consolidés.")
        print(df_resultats.to_string(index=False))

        # Sauvegarde unique du package complet
        df_resultats.to_csv(
            "predictions_tennis_input.csv", index=False, encoding="utf-8-sig"
        )
        print("\n📁 Fichier 'predictions_tennis_input.csv' créé.")
    else:
        print("❌ Aucune donnée n'a pu être extraite.")


if __name__ == "__main__":
    asyncio.run(main())