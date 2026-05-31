"""
Scraper OddsPortal avec Selenium + undetected-chromedriver.
Contourne la détection de bot que Playwright déclenche.
"""

import time
import random
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc


class OddsPortalSeleniumScraper:
    """Scraper OddsPortal avec Selenium pour éviter les timeouts Playwright."""

    def __init__(self):
        self.endpoints = {
            "today": "https://www.oddsportal.com/matches/tennis/today/",
            "tomorrow": "https://www.oddsportal.com/matches/tennis/tomorrow/",
        }

    def _parse_html_frame(self, html_content: str) -> list:
        """Extrait les matchs depuis le HTML OddsPortal."""
        soup = BeautifulSoup(html_content, "html.parser")
        extracted = []

        match_rows = soup.find_all(
            "div", class_="group flex", attrs={"data-testid": "game-row"}
        )

        for row in match_rows:
            try:
                player_elements = row.find_all("p", class_="participant-name")
                if len(player_elements) < 2:
                    continue
                p1 = player_elements[0].get_text(strip=True)
                p2 = player_elements[1].get_text(strip=True)

                odds_elements = row.find_all(
                    "p", {"data-testid": "odd-container-default"}
                )
                odds_p1 = None
                odds_p2 = None
                if len(odds_elements) > 0:
                    try:
                        odds_p1 = float(odds_elements[0].get_text(strip=True))
                    except:
                        pass
                if len(odds_elements) > 1:
                    try:
                        odds_p2 = float(odds_elements[1].get_text(strip=True))
                    except:
                        pass

                extracted.append({
                    "player1": p1,
                    "player2": p2,
                    "odds_p1": odds_p1,
                    "odds_p2": odds_p2,
                })
            except Exception:
                continue

        return extracted

    def _scrape_single_url(self, driver, url: str) -> list:
        """Scrape une URL OddsPortal avec Selenium."""
        matches_dict = {}

        print(f"  🌍 Scraping {url} (Selenium)")
        try:
            driver.get(url)

            # Attendre que les éléments se chargent
            wait = WebDriverWait(driver, 20)
            wait.until(EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "div[data-testid='game-row']")
            ))

            print(f"    ✅ Page chargée")

        except TimeoutException:
            print(f"    ⚠️  Timeout lors du chargement")
            return []
        except Exception as e:
            print(f"    ⚠️  Erreur: {e}")
            return []

        # Scroll et collecte des matchs
        current_scroll = 0
        max_scrolls = 15
        scroll_count = 0

        while scroll_count < max_scrolls:
            try:
                # Scroll
                step = random.randint(300, 500)
                driver.execute_script(f"window.scrollBy(0, {step});")
                time.sleep(random.uniform(0.5, 1.0))

                # Parse
                html = driver.page_source
                visible_matches = self._parse_html_frame(html)

                for m in visible_matches:
                    match_key = f"{m['player1']} vs {m['player2']}"
                    if match_key not in matches_dict:
                        matches_dict[match_key] = m

                scroll_count += 1

            except Exception as e:
                print(f"    ⚠️  Erreur scroll: {e}")
                break

        return list(matches_dict.values())

    def run(self) -> dict:
        """Scrape OddsPortal pour aujourd'hui et demain."""
        global_matches = {}

        # Créer un driver undetected
        try:
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')

            driver = uc.Chrome(options=options)
            print("✅ Selenium driver créé (undetected)")

        except Exception as e:
            print(f"❌ Erreur création driver: {e}")
            print("   Installer: pip install undetected-chromedriver selenium")
            return {}

        try:
            for label, url in self.endpoints.items():
                print(f"📥 OddsPortal - {label}...")
                page_matches = self._scrape_single_url(driver, url)

                if page_matches:
                    print(f"    ✅ {len(page_matches)} matchs trouvés")
                    for m in page_matches:
                        key = self._match_key(m['player1'], m['player2'])
                        if key not in global_matches:
                            global_matches[key] = {
                                'player1': m['player1'],
                                'player2': m['player2'],
                                'odds_p1': m['odds_p1'],
                                'odds_p2': m['odds_p2'],
                            }
                else:
                    print(f"    ⚠️  Aucun match trouvé")

                time.sleep(random.uniform(2.0, 4.0))

        finally:
            driver.quit()
            print("✅ Driver fermé")

        print(f"   ✅ Total: {len(global_matches)} matchs OddsPortal")
        return global_matches

    def _match_key(self, p1: str, p2: str) -> str:
        """Crée une clé de matching."""
        from name_matcher import make_match_key
        return make_match_key(p1, p2)


if __name__ == "__main__":
    scraper = OddsPortalSeleniumScraper()
    result = scraper.run()

    print(f"\nRésultat: {len(result)} matchs")
    for key, data in list(result.items())[:5]:
        print(f"  {key}: {data['odds_p1']} / {data['odds_p2']}")