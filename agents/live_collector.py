import re
import asyncio
import random
import requests
import urllib3
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from database import get_connection
from config import ODDS_API_KEY, ODDS_SPORT, ODDS_REGION, ODDS_MARKET
from name_matcher import make_match_key, extract_last_name

urllib3.disable_warnings()

EXCLUDED_TOURS = {'itf', 'utr', 'futures'}


class OddsPortalTennisScraper:
    """Scraper OddsPortal pour cotes tennis (aujourd'hui + demain)."""

    def __init__(self):
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
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

    async def _scrape_single_url(self, page_instance, url: str) -> list:
        """Scrape une URL OddsPortal avec scroll humain."""
        matches_dict = {}

        print(f"  🌍 Scraping {url}")
        try:
            await page_instance.goto(url, wait_until="networkidle", timeout=60000)
            await page_instance.wait_for_selector(
                "div[data-testid='game-row']", timeout=15000
            )
        except Exception as e:
            print(f"  ⚠️  Erreur navigation OddsPortal: {e}")
            return []

        current_scroll = 0
        total_height = await page_instance.evaluate("document.body.scrollHeight")
        loop_count = 0

        while current_scroll < total_height:
            step = random.randint(300, 500)
            current_scroll += step
            await page_instance.evaluate(f"window.scrollTo(0, {current_scroll});")
            await page_instance.mouse.move(
                random.randint(400, 800), random.randint(300, 600)
            )

            loop_count += 1
            if loop_count % 5 == 0:
                current_scroll -= 150
                await page_instance.evaluate(
                    f"window.scrollTo(0, {current_scroll});"
                )
                await asyncio.sleep(2.0)
                current_scroll += 150
            else:
                await asyncio.sleep(random.uniform(0.5, 0.8))

            html_content = await page_instance.content()
            visible_matches = self._parse_html_frame(html_content)

            for m in visible_matches:
                match_key = f"{m['player1']} vs {m['player2']}"
                if match_key not in matches_dict:
                    matches_dict[match_key] = m

            total_height = await page_instance.evaluate(
                "document.body.scrollHeight"
            )

        return list(matches_dict.values())

    async def run(self) -> dict:
        """Scrape OddsPortal pour aujourd'hui et demain, retourne {match_key: cotes}."""
        global_matches = {}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=self.user_agent,
            )
            page = await context.new_page()

            for label, url in self.endpoints.items():
                print(f"📥 OddsPortal - {label}...")
                page_matches = await self._scrape_single_url(page, url)

                for m in page_matches:
                    key = make_match_key(m['player1'], m['player2'])
                    if key not in global_matches:
                        global_matches[key] = {
                            'player1': m['player1'],
                            'player2': m['player2'],
                            'odds_p1': m['odds_p1'],
                            'odds_p2': m['odds_p2'],
                        }

                await asyncio.sleep(random.uniform(2.0, 4.0))

            await browser.close()

        print(f"   ✅ {len(global_matches)} matchs OddsPortal")
        return global_matches


class LiveCollectorAgent:
    def __init__(self):
        self.base_url = "https://api.the-odds-api.com/v4"
        self.te_base = "https://www.tennisexplorer.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }
        self._name_cache = {}
        self.oddsportal_scraper = OddsPortalTennisScraper()
        print("✅ LiveCollectorAgent initialisé")

    # ─── RÉSOLUTION DES NOMS ──────────────────────────────────────────────────

    def _resolve_player_name(self, name_abbr: str, gender: str) -> str:
        cache_key = f"{name_abbr}_{gender}"
        if cache_key in self._name_cache:
            return self._name_cache[cache_key]

        parts = name_abbr.strip().split()
        if not parts:
            return name_abbr

        if len(parts) > 1 and re.match(r'^[A-Z]{1,2}\.?$', parts[-1]):
            last_name = ' '.join(parts[:-1])
        else:
            last_name = ' '.join(parts)

        conn = get_connection()
        try:
            c = conn.cursor()
            c.execute('''
                SELECT name FROM players_rankings
                WHERE name LIKE ? AND gender = ?
                ORDER BY date_recorded DESC LIMIT 1
            ''', (f'%{last_name}%', gender))
            row = c.fetchone()

            if row:
                resolved = row[0]
            else:
                first_word = parts[0]
                c.execute('''
                    SELECT name FROM players_rankings
                    WHERE name LIKE ? AND gender = ?
                    ORDER BY date_recorded DESC LIMIT 1
                ''', (f'{first_word}%', gender))
                row = c.fetchone()
                resolved = row[0] if row else name_abbr

        finally:
            conn.close()

        self._name_cache[cache_key] = resolved
        return resolved

    def _resolve_match_names(self, matches: list) -> list:
        print("🔍 Résolution des noms de joueurs...")
        resolved = 0
        for m in matches:
            gender = 'F' if m['tour'] == 'WTA' else 'M'

            p1_resolved = self._resolve_player_name(m['player1'], gender)
            p2_resolved = self._resolve_player_name(m['player2'], gender)

            if p1_resolved != m['player1']:
                m['player1_abbr'] = m['player1']
                m['player1'] = p1_resolved
                resolved += 1
            if p2_resolved != m['player2']:
                m['player2_abbr'] = m['player2']
                m['player2'] = p2_resolved
                resolved += 1

        print(f"   {resolved} noms résolus sur {len(matches) * 2} joueurs")
        return matches

    # ─── DÉDUPLICATION ────────────────────────────────────────────────────────

    def _deduplicate_matches(self, matches: list) -> list:
        seen = set()
        result = []
        for m in matches:
            key = frozenset([m['player1'], m['player2']])
            if key not in seen:
                seen.add(key)
                result.append(m)
        removed = len(matches) - len(result)
        if removed:
            print(f"   {removed} doublon(s) sens inversé supprimé(s)")
        return result

    # ─── TENNISEXPLORER ───────────────────────────────────────────────────────

    def get_todays_matches_te(self) -> list:
        from bs4 import BeautifulSoup

        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        url = (f"{self.te_base}/matches/"
               f"?type=all&year={now.year}&month={now.month:02d}&day={now.day:02d}")
        print(f"📥 Scraping tennisexplorer ({today})...")

        try:
            resp = requests.get(url, headers=self.headers, verify=False, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"❌ Erreur tennisexplorer : {e}")
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')

        matches = []
        current_tournament = "Unknown"
        current_tour = "ATP"
        current_surface = "Hard"

        rows = soup.select('tbody tr')

        i = 0
        while i < len(rows):
            row = rows[i]
            row_id = row.get('id', '')
            row_class = row.get('class', [])

            if 'head' in row_class and 'flags' in row_class:
                td = row.select_one('td.t-name')
                if td:
                    current_tournament = td.get_text(strip=True)
                    tl = current_tournament.lower()

                    if any(ex in tl for ex in EXCLUDED_TOURS):
                        current_tour = 'SKIP'
                    elif 'wta' in tl:
                        current_tour = 'WTA'
                    else:
                        current_tour = 'ATP'

                    course_tds = row.select('td.course')
                    current_surface = 'Hard'
                    for ctd in course_tds:
                        c = ctd.get_text(strip=True).upper()
                        if c == 'C':
                            current_surface = 'Clay'
                            break
                        elif c == 'G':
                            current_surface = 'Grass'
                            break
                        elif c == 'H':
                            current_surface = 'Hard'
                            break
                i += 1
                continue

            if current_tour == 'SKIP':
                i += 1
                continue

            is_p1 = (
                    len(row_id) >= 2 and
                    row_id[0] in ('r', 's') and
                    not row_id.endswith('b') and
                    row_id[1:].isdigit()
            )
            if not is_p1:
                i += 1
                continue

            p2_row = None
            if i + 1 < len(rows):
                nxt = rows[i + 1]
                nxt_id = nxt.get('id', '')
                if nxt_id.endswith('b') and nxt_id[:-1] == row_id:
                    p2_row = nxt

            if p2_row is None:
                i += 1
                continue

            p1_link = row.select_one('td.t-name a[href*="/player/"]')
            p2_link = p2_row.select_one('td.t-name a[href*="/player/"]')

            if not p1_link or not p2_link:
                i += 2
                continue

            p1 = re.sub(r'\s*\(\d+\)\s*$', '', p1_link.get_text(strip=True)).strip()
            p2 = re.sub(r'\s*\(\d+\)\s*$', '', p2_link.get_text(strip=True)).strip()

            if not p1 or not p2:
                i += 2
                continue

            time_td = row.select_one('td.first.time')
            time_text = time_td.get_text(separator=' ', strip=True).split()[0] if time_td else ''

            matches.append({
                'player1': p1,
                'player2': p2,
                'tournament': current_tournament,
                'tour': current_tour,
                'surface': current_surface,
                'commence_time': f"{today}T{time_text}" if time_text else today,
            })

            i += 2

        print(f"   {len(matches)} matchs trouvés sur tennisexplorer")
        return matches

    # ─── ODDS API ─────────────────────────────────────────────────────────────

    def get_odds_api(self) -> dict:
        """Récupère cotes Odds API, retourne {match_key: {odds_api_p1, odds_api_p2}}."""
        print("📥 Récupération des cotes (Odds API)...")
        try:
            resp = requests.get(
                f"{self.base_url}/sports/{ODDS_SPORT}/odds",
                params={"apiKey": ODDS_API_KEY, "regions": ODDS_REGION,
                        "markets": ODDS_MARKET, "oddsFormat": "decimal"},
                timeout=10
            )
            data = resp.json()
            if resp.status_code != 200:
                print(f"⚠️  Odds API : {data.get('message', 'erreur')}")
                return {}

            odds_map = {}
            for event in data:
                if not event.get("bookmakers"):
                    continue
                p1, p2 = event.get("home_team", "?"), event.get("away_team", "?")
                odds_p1 = odds_p2 = None
                for market in event["bookmakers"][0].get("markets", []):
                    if market["key"] == "h2h":
                        for o in market.get("outcomes", []):
                            if o["name"] == p1:
                                odds_p1 = o["price"]
                            elif o["name"] == p2:
                                odds_p2 = o["price"]

                key = make_match_key(p1, p2)
                odds_map[key] = {
                    'odds_api_p1': odds_p1, 'odds_api_p2': odds_p2,
                    'p1_odds_name': p1, 'p2_odds_name': p2,
                }
            print(f"   ✅ {len(odds_map)} matchs Odds API")
            return odds_map
        except Exception as e:
            print(f"⚠️  Odds API indisponible : {e}")
            return {}

    # ─── COTES (PAS DE NORMALISATION) ─────────────────────────────────────────

    def _validate_odds(self, match: dict) -> dict:
        """Valide les cotes : on garde l'ordre TennisExplorer sans swapper."""
        odds_p1 = match.get('odds_p1')
        odds_p2 = match.get('odds_p2')

        if odds_p1 is None or odds_p2 is None:
            return match

        if odds_p1 > 0 and odds_p2 > 0:
            match['odds_valid'] = True
        else:
            match['odds_valid'] = False

        return match

    # ─── FUSION COTES ────────────────────────────────────────────────────────

    def _merge_odds(self, matches: list, oddsportal_map: dict, odds_api_map: dict) -> list:
        """Fusionne OddsPortal (odds_p1/p2) + Odds API (odds_api_p1/p2) via name_matcher."""
        merged_op = 0
        merged_oa = 0

        for m in matches:
            key = make_match_key(m['player1'], m['player2'])

            # OddsPortal (source principale)
            if key in oddsportal_map:
                op_data = oddsportal_map[key]
                m['odds_p1'] = op_data['odds_p1']
                m['odds_p2'] = op_data['odds_p2']
                m = self._validate_odds(m)
                merged_op += 1

            # Odds API (source secondaire)
            if key in odds_api_map:
                odds_api = odds_api_map[key]
                # Détecte le bon sens : compare les noms de famille
                last1 = extract_last_name(m['player1'])
                p1_oa_last = extract_last_name(odds_api['p1_odds_name'])

                if last1 == p1_oa_last:
                    m['odds_api_p1'] = odds_api['odds_api_p1']
                    m['odds_api_p2'] = odds_api['odds_api_p2']
                else:
                    m['odds_api_p1'] = odds_api['odds_api_p2']
                    m['odds_api_p2'] = odds_api['odds_api_p1']
                merged_oa += 1

        print(f"   ✅ {merged_op} matchs OddsPortal enrichis, {merged_oa} Odds API")
        return matches

    # ─── SAUVEGARDE ───────────────────────────────────────────────────────────

    def save_todays_matches(self, matches: list):
        if not matches:
            print("⚠️  Aucun match à sauvegarder")
            return

        conn = get_connection()
        c = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        saved = 0

        for m in matches:
            try:
                surface = m.get('surface', 'Hard')
                try:
                    c.execute("""
                        SELECT surface FROM tournament_surfaces
                        WHERE ? LIKE '%' || tournament_key || '%' LIMIT 1
                    """, (m['tournament'].lower(),))
                    row = c.fetchone()
                    if row:
                        surface = row[0]
                except Exception:
                    pass

                c.execute("""
                    INSERT OR IGNORE INTO predictions
                    (date, player1, player2, tournament, surface,
                     predicted_winner, confidence)
                    VALUES (?, ?, ?, ?, ?, '', 0.0)
                """, (today, m['player1'], m['player2'],
                      m['tournament'], surface))

                # Update cotes OddsPortal
                if m.get('odds_p1') or m.get('odds_p2'):
                    try:
                        c.execute("""
                            UPDATE predictions SET odds_p1=?, odds_p2=?
                            WHERE date=? AND player1=? AND player2=?
                        """, (m.get('odds_p1'), m.get('odds_p2'),
                              today, m['player1'], m['player2']))
                    except Exception:
                        pass

                # Update cotes Odds API
                if m.get('odds_api_p1') or m.get('odds_api_p2'):
                    try:
                        c.execute("""
                            UPDATE predictions SET odds_api_p1=?, odds_api_p2=?
                            WHERE date=? AND player1=? AND player2=?
                        """, (m.get('odds_api_p1'), m.get('odds_api_p2'),
                              today, m['player1'], m['player2']))
                    except Exception:
                        pass

                saved += 1
            except Exception as e:
                print(f"  ⚠️  Erreur save {m['player1']}: {e}")
                continue

        conn.commit()
        conn.close()
        with_odds = sum(1 for m in matches if m.get('odds_p1'))
        with_api = sum(1 for m in matches if m.get('odds_api_p1'))
        print(f"✅ {saved} matchs sauvegardés ({with_odds} OddsPortal, {with_api} Odds API)")

    # ─── MAIN ─────────────────────────────────────────────────────────────────

    def run(self) -> list:
        # 1. Scraping tennisexplorer
        matches = self.get_todays_matches_te()

        # 2. Résolution des noms
        if matches:
            matches = self._resolve_match_names(matches)

        # 3. Déduplication
        if matches:
            matches = self._deduplicate_matches(matches)

        # 4. Scraper OddsPortal (async)
        oddsportal_map = asyncio.run(self.oddsportal_scraper.run())

        # 5. Cotes Odds API
        odds_api_map = self.get_odds_api()

        # 6. Fusion cotes
        if matches:
            matches = self._merge_odds(matches, oddsportal_map, odds_api_map)

        # 7. Sauvegarde
        self.save_todays_matches(matches)
        return matches


if __name__ == "__main__":
    agent = LiveCollectorAgent()
    matches = agent.run()

    print(f"\n{'=' * 120}")
    print(f"{'Joueur 1':<25} {'Joueur 2':<25} {'OddsPortal':^25} {'Odds API':^25}")
    print(f"{'=' * 120}")
    for m in matches:
        op = f"{m.get('odds_p1', '-'):.2f}/{m.get('odds_p2', '-'):.2f}" if m.get('odds_p1') else "—"
        oa = f"{m.get('odds_api_p1', '-'):.2f}/{m.get('odds_api_p2', '-'):.2f}" if m.get('odds_api_p1') else "—"
        print(f"{m['player1']:<25} {m['player2']:<25} {op:^25} {oa:^25}")
    print(f"\nTotal : {len(matches)} matchs")