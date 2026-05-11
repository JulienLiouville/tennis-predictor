import re
import requests
import urllib3
from datetime import datetime
from database import get_connection
from config import ODDS_API_KEY, ODDS_SPORT, ODDS_REGION, ODDS_MARKET

urllib3.disable_warnings()

EXCLUDED_TOURS = {'itf', 'utr', 'futures'}


class LiveCollectorAgent:
    def __init__(self):
        self.base_url = "https://api.the-odds-api.com/v4"
        self.te_base  = "https://www.tennisexplorer.com"
        self.headers  = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }
        self._name_cache = {}  # cache {nom_abrégé -> nom_complet}
        print("✅ LiveCollectorAgent initialisé")

    # ─── RÉSOLUTION DES NOMS ──────────────────────────────────────────────────

    def _resolve_player_name(self, name_abbr: str, gender: str) -> str:
        """
        Résout un nom abrégé tennisexplorer ("Hurkacz H.") vers le nom complet
        dans players_rankings ("Hurkacz Hubert").

        Stratégie :
          1. Extrait le nom de famille (tout avant le dernier espace)
          2. Cherche dans players_rankings avec LIKE '%nom_famille%' + gender
          3. Retourne le nom complet si trouvé, sinon le nom abrégé original

        Format players_rankings : "Sinner Jannik" (famille + prénom)
        Format tennisexplorer   : "Sinner J." (famille + initiale)
        """
        cache_key = f"{name_abbr}_{gender}"
        if cache_key in self._name_cache:
            return self._name_cache[cache_key]

        # Extrait le nom de famille : "Hurkacz H." → "Hurkacz"
        parts = name_abbr.strip().split()
        if not parts:
            return name_abbr

        # Gère les noms composés : "Van De Zandschulp B." → cherche "Van De Zandschulp"
        # On enlève la dernière partie si elle ressemble à une initiale (1-2 chars + point)
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
                # Fallback : essaie juste le premier mot (nom de famille simple)
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
        """
        Résout tous les noms abrégés vers les noms complets.
        Met à jour player1/player2 in-place.
        """
        print("🔍 Résolution des noms de joueurs...")
        resolved = 0
        for m in matches:
            gender = 'F' if m['tour'] == 'WTA' else 'M'

            p1_resolved = self._resolve_player_name(m['player1'], gender)
            p2_resolved = self._resolve_player_name(m['player2'], gender)

            if p1_resolved != m['player1']:
                m['player1_abbr'] = m['player1']  # garde l'original pour debug
                m['player1'] = p1_resolved
                resolved += 1
            if p2_resolved != m['player2']:
                m['player2_abbr'] = m['player2']
                m['player2'] = p2_resolved
                resolved += 1

        print(f"   {resolved} noms résolus sur {len(matches) * 2} joueurs")
        return matches

    # ─── TENNISEXPLORER ───────────────────────────────────────────────────────

    def get_todays_matches_te(self) -> list:
        from bs4 import BeautifulSoup

        now   = datetime.now()
        today = now.strftime('%Y-%m-%d')
        url   = (f"{self.te_base}/matches/"
                 f"?type=all&year={now.year}&month={now.month:02d}&day={now.day:02d}")
        print(f"📥 Scraping tennisexplorer ({today})...")

        try:
            resp = requests.get(url, headers=self.headers, verify=False, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"❌ Erreur tennisexplorer : {e}")
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')

        matches            = []
        current_tournament = "Unknown"
        current_tour       = "ATP"
        current_surface    = "Hard"

        rows = soup.select('tbody tr')

        i = 0
        while i < len(rows):
            row        = rows[i]
            row_id     = row.get('id', '')
            row_class  = row.get('class', [])

            # ── Ligne tournoi ─────────────────────────────────────────────────
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

            # ── Ligne player1 ─────────────────────────────────────────────────
            is_p1 = (
                len(row_id) >= 2 and
                row_id[0] in ('r', 's') and
                not row_id.endswith('b') and
                row_id[1:].isdigit()
            )
            if not is_p1:
                i += 1
                continue

            # ── Ligne player2 ─────────────────────────────────────────────────
            p2_row = None
            if i + 1 < len(rows):
                nxt    = rows[i + 1]
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

            time_td   = row.select_one('td.first.time')
            time_text = time_td.get_text(separator=' ', strip=True).split()[0] if time_td else ''

            te_odds1, te_odds2 = None, None
            coursew = row.select_one('td.coursew')
            course  = row.select_one('td.course')
            if coursew:
                try:    te_odds1 = float(coursew.get_text(strip=True))
                except: pass
            if course:
                try:    te_odds2 = float(course.get_text(strip=True))
                except: pass

            matches.append({
                'player1':       p1,
                'player2':       p2,
                'tournament':    current_tournament,
                'tour':          current_tour,
                'surface':       current_surface,
                'commence_time': f"{today}T{time_text}" if time_text else today,
                'odds1':         te_odds1,
                'odds2':         te_odds2,
            })

            i += 2

        print(f"   {len(matches)} matchs trouvés sur tennisexplorer")
        return matches

    # ─── ODDS API ─────────────────────────────────────────────────────────────

    def get_odds(self) -> dict:
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
                p1, p2 = event["home_team"], event["away_team"]
                odds1 = odds2 = None
                for market in event["bookmakers"][0]["markets"]:
                    if market["key"] == "h2h":
                        for o in market["outcomes"]:
                            if o["name"] == p1:   odds1 = o["price"]
                            elif o["name"] == p2: odds2 = o["price"]
                odds_map[self._match_key(p1, p2)] = {
                    'odds1': odds1, 'odds2': odds2,
                    'p1_odds_name': p1, 'p2_odds_name': p2,
                }
            print(f"   {len(odds_map)} matchs avec cotes (Odds API)")
            return odds_map
        except Exception as e:
            print(f"⚠️  Odds API indisponible : {e}")
            return {}

    # ─── MERGE ────────────────────────────────────────────────────────────────

    def _normalize_name(self, name: str) -> str:
        import unicodedata
        name = unicodedata.normalize('NFD', name)
        return ''.join(c for c in name if unicodedata.category(c) != 'Mn').lower().strip()

    def _match_key(self, p1: str, p2: str) -> str:
        return '_vs_'.join(sorted([self._normalize_name(p1), self._normalize_name(p2)]))

    def _merge_odds(self, matches: list, odds_map: dict) -> list:
        merged = 0
        for m in matches:
            key = self._match_key(m['player1'], m['player2'])
            if key in odds_map:
                odds    = odds_map[key]
                p1_norm = self._normalize_name(m['player1'])
                if p1_norm in self._normalize_name(odds['p1_odds_name']):
                    m['odds1'], m['odds2'] = odds['odds1'], odds['odds2']
                else:
                    m['odds1'], m['odds2'] = odds['odds2'], odds['odds1']
                merged += 1
        print(f"   {merged}/{len(matches)} matchs enrichis avec cotes Odds API")
        return matches

    # ─── SAUVEGARDE ───────────────────────────────────────────────────────────

    def save_todays_matches(self, matches: list):
        if not matches:
            print("⚠️  Aucun match à sauvegarder")
            return

        conn  = get_connection()
        c     = conn.cursor()
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

                if m.get('odds1') or m.get('odds2'):
                    try:
                        c.execute("""
                            UPDATE predictions SET odds_p1=?, odds_p2=?
                            WHERE date=? AND player1=? AND player2=?
                        """, (m.get('odds1'), m.get('odds2'),
                              today, m['player1'], m['player2']))
                    except Exception:
                        pass

                saved += 1
            except Exception as e:
                print(f"  ⚠️  Erreur save {m['player1']}: {e}")
                continue

        conn.commit()
        conn.close()
        with_odds = sum(1 for m in matches if m.get('odds1'))
        print(f"✅ {saved} matchs sauvegardés ({with_odds} avec cotes)")

    # ─── MAIN ─────────────────────────────────────────────────────────────────

    def run(self) -> list:
        # 1. Scraping tennisexplorer
        matches = self.get_todays_matches_te()

        # 2. Résolution des noms abrégés → noms complets via players_rankings
        if matches:
            matches = self._resolve_match_names(matches)

        # 3. Cotes Odds API
        odds_map = self.get_odds()
        if odds_map and matches:
            matches = self._merge_odds(matches, odds_map)

        # 4. Sauvegarde
        self.save_todays_matches(matches)
        return matches


if __name__ == "__main__":
    agent   = LiveCollectorAgent()
    matches = agent.run()

    print(f"\n{'='*80}")
    print(f"{'Joueur 1':<30} {'Joueur 2':<30} {'Cotes':^12} {'Surface':<8} Tour")
    print(f"{'='*80}")
    for m in matches:
        cotes = f"{m['odds1']}/{m['odds2']}" if m.get('odds1') else "—"
        p1 = m['player1']
        p2 = m['player2']
        # Affiche l'abrégé original si résolution a eu lieu
        if 'player1_abbr' in m:
            p1 = f"{p1} ({m['player1_abbr']})"
        if 'player2_abbr' in m:
            p2 = f"{p2} ({m['player2_abbr']})"
        print(f"{p1:<30} {p2:<30} {cotes:^12} "
              f"{m.get('surface','?'):<8} {m.get('tour','?')}")
    print(f"\nTotal : {len(matches)} matchs")