import requests
from bs4 import BeautifulSoup
from database import get_connection
import urllib3
import re
import time
import os
import pandas as pd
from datetime import datetime, timedelta
from calendar import monthrange

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

# Exclusions par substring (case-insensitive)
EXCLUDED_SUBSTRINGS = [
    'utr pro tennis',
    'utr pro match',
    'utr pro',
    'ultimate tennis showdown',
    'billie jean king cup',
    'davis cup',
    'laver cup',
    'hopman cup',
    'exhibition',
    'bundesliga',
    'nationalliga',
    'world tennis league',
    'world university games',
    'six kings slam',
    'garden cup',
    'racquet at the rock',
    'charlotte invitational',
    'miami invitational',
    'france - championship',
    'czech league',
    'boodles',
    ' itf',   # ex: "Madrid 20 ITF", "Monastir 33 ITF"
]

# Exclusions par pattern regex (case-insensitive)
EXCLUDED_PATTERNS = [
    re.compile(r'^futures', re.IGNORECASE),        # Futures 2026, Futures XYZ
    re.compile(r'\bitf\b', re.IGNORECASE),          # contient ITF n'importe où
]

SURFACE_OVERRIDES = {
    'sao leopoldo': 'Clay', 'savannah': 'Clay', 'houston': 'Clay',
    'menorca': 'Clay', 'campinas': 'Clay', 'san luis potosi': 'Clay',
    'mexico city': 'Clay', 'oeiras': 'Clay', 'santa cruz': 'Clay',
    'barletta': 'Clay', 'monza': 'Clay', 'abidjan': 'Clay',
    'tallahassee': 'Clay', 'gwangju': 'Hard', 'miyazaki': 'Hard',
    'busan': 'Hard', 'wuning': 'Hard', 'shymkent': 'Hard', 'sarasota': 'Hard',
}

GRAND_SLAMS = [
    'australian open', 'roland garros', 'wimbledon', 'us open', 'french open'
]

INVALID_SCORES = {'0-0', '5-5', '1-0', '0-1', ''}

TOUR_CONFIG = {
    'atp': {'url_type': 'atp-single', 'gender': 'M'},
    'wta': {'url_type': 'wta-single', 'gender': 'F'},
}


# ─── MATCH COLLECTOR ──────────────────────────────────────────────────────────

class MatchCollector:
    """
    Collecteur de matchs tennis ATP/WTA.
    Même philosophie que RankingCollector :
    - Scrape tennisexplorer
    - Enrichit avec classements depuis la DB (players_rankings)
    - Sauvegarde en DB SQLite + CSV
    """

    def __init__(self, output_dir="data/csv"):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self._unknown_tournaments = set()
        self._name_cache = {}  # cache {nom_abrégé_gender -> nom_complet}
        self._init_db()
        print("✅ MatchCollector initialisé")

    def _init_db(self):
        """Crée la table matches enrichie si elle n'existe pas"""
        conn = get_connection()
        try:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS matches_2026 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                time TEXT,
                tour TEXT,
                tournament TEXT,
                surface TEXT,
                best_of INTEGER,
                player1 TEXT,
                player2 TEXT,
                winner TEXT,
                score TEXT,
                sets_won_p1 INTEGER,
                sets_won_p2 INTEGER,
                num_sets INTEGER,
                odds_p1 REAL,
                odds_p2 REAL,
                p1_rank INTEGER,
                p1_points INTEGER,
                p1_country TEXT,
                p2_rank INTEGER,
                p2_points INTEGER,
                p2_country TEXT,
                ranking_date_used TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, player1, player2, tour)
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS tournament_surfaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_key TEXT UNIQUE,
                tournament_name TEXT,
                surface TEXT,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            conn.commit()
        finally:
            conn.close()

    # ─── RANKING LOOKUP ───────────────────────────────────

    def _get_ranking_date(self, date_str: str) -> str:
        conn = get_connection()
        try:
            c = conn.cursor()
            # D'abord : date la plus récente avant le match
            c.execute('''
                SELECT DISTINCT date_recorded FROM players_rankings
                WHERE date_recorded <= ?
                ORDER BY date_recorded DESC
                LIMIT 1
            ''', (date_str,))
            row = c.fetchone()
            if row:
                return row[0]

            # Fallback : date la plus proche toutes dates confondues
            c.execute('''
                SELECT DISTINCT date_recorded FROM players_rankings
                ORDER BY ABS(JULIANDAY(date_recorded) - JULIANDAY(?))
                LIMIT 1
            ''', (date_str,))
            row = c.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def _get_player_ranking(self, player_name: str, gender: str,
                            ranking_date: str) -> dict:
        """
        Cherche le classement d'un joueur dans players_rankings.
        Format DB : "Sinner Jannik" (Prénom Nom)
        Format scraper : "Sinner J." (Nom Initiale)
        → Matching par nom de famille
        """
        default = {'rank': None, 'points': None, 'country': None}
        if not player_name or not ranking_date:
            return default

        conn = get_connection()
        try:
            c = conn.cursor()

            # Extrait les candidats nom de famille depuis "Auger Aliassime F."
            parts = player_name.strip().split()
            candidates = [
                p.lower().rstrip('.')
                for p in parts
                if len(p.rstrip('.')) > 2  # Ignore les initiales
            ]

            for candidate in reversed(candidates):
                # Recherche : nom DB contient le candidat
                c.execute('''
                    SELECT rank, points, country FROM players_rankings
                    WHERE LOWER(name) LIKE ?
                    AND gender = ?
                    AND date_recorded = ?
                    ORDER BY rank ASC
                    LIMIT 1
                ''', (f'%{candidate}%', gender, ranking_date))
                row = c.fetchone()
                if row:
                    return {
                        'rank': row[0],
                        'points': row[1],
                        'country': row[2]
                    }

            return default
        finally:
            conn.close()

    # ─── SURFACE ──────────────────────────────────────────

    def _get_surface(self, tournament: str) -> str:
        # 1. Overrides hardcodes
        t_low = tournament.lower()
        for key, surface in SURFACE_OVERRIDES.items():
            if key in t_low:
                return surface

        # 2. Cherche en DB
        conn = get_connection()
        try:
            c = conn.cursor()
            c.execute('SELECT surface FROM tournament_surfaces WHERE tournament_key = ?',
                      (tournament,))
            row = c.fetchone()
            if row:
                return row[0]

            # 3. Nouveau tournoi -> insere Unknown en DB
            c.execute('INSERT OR IGNORE INTO tournament_surfaces (tournament_key, tournament_name, surface) VALUES (?, ?, ?)',
                      (tournament, tournament, 'Unknown'))
            conn.commit()
            return 'Unknown'
        finally:
            conn.close()

    # ─── PARSING ──────────────────────────────────────────

    def _clean_name(self, name: str) -> str:
        cleaned = re.sub(r'\s*\([^)]*\)', '', name)
        cleaned = re.sub(r'\s*\[\d+\]', '', cleaned)
        return cleaned.strip()

    def _resolve_name(self, name_abbr: str, gender: str) -> str:
        """
        Résout un nom abrégé ("Sinner J.") vers le nom complet players_rankings
        ("Sinner Jannik"). Retourne le nom original si non trouvé.
        """
        cache_key = f"{name_abbr}_{gender}"
        if cache_key in self._name_cache:
            return self._name_cache[cache_key]

        parts = name_abbr.strip().split()
        if not parts:
            return name_abbr

        # Noms composés : "Van De Zandschulp B." → "Van De Zandschulp"
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
            if not row:
                c.execute('''
                    SELECT name FROM players_rankings
                    WHERE name LIKE ? AND gender = ?
                    ORDER BY date_recorded DESC LIMIT 1
                ''', (f'{parts[0]}%', gender))
                row = c.fetchone()
            resolved = row[0] if row else name_abbr
        finally:
            conn.close()

        self._name_cache[cache_key] = resolved
        return resolved

    def _parse_score(self, row_a, row_b) -> dict:
        """Parse le score avec tiebreaks propres : 7-6(3)"""
        score_parts = []
        score_cells_a = row_a.find_all('td', class_='score')
        score_cells_b = row_b.find_all('td', class_='score')

        for i, (ca, cb) in enumerate(zip(score_cells_a, score_cells_b)):
            if i == 0:
                continue

            # Extrait le superscript AVANT get_text
            sup_a = ca.find('sup')
            sup_b = cb.find('sup')
            tb_num = None
            if sup_a:
                tb_num = sup_a.get_text(strip=True)
                sup_a.decompose()
            elif sup_b:
                tb_num = sup_b.get_text(strip=True)
                sup_b.decompose()

            ta_raw = ca.get_text(strip=True)
            tb_raw = cb.get_text(strip=True)

            if not ta_raw or ta_raw == '\xa0':
                continue

            ta_clean = re.sub(r'[^\d]', '', ta_raw)
            tb_clean = re.sub(r'[^\d]', '', tb_raw) if tb_raw else ''

            if ta_clean and tb_clean:
                if tb_num:
                    score_parts.append(f"{ta_clean}-{tb_clean}({tb_num})")
                else:
                    score_parts.append(f"{ta_clean}-{tb_clean}")

        score_str = ' '.join(score_parts)

        try:
            res_a = int(row_a.find('td', class_='result').get_text(strip=True))
            res_b = int(row_b.find('td', class_='result').get_text(strip=True))
        except Exception:
            res_a, res_b = 0, 0

        return {
            'score': score_str,
            'sets_won_p1': res_a,
            'sets_won_p2': res_b,
            'num_sets': len(score_parts),
            'is_valid': (
                score_str not in INVALID_SCORES
                and score_str != ''
                and res_a + res_b > 0
            )
        }

    def _get_odds(self, row_a) -> dict:
        try:
            odds_w = row_a.find('td', class_='coursew')
            odds_l = row_a.find('td', class_='course')
            return {
                'odds_p1': float(odds_w.get_text(strip=True)) if odds_w else None,
                'odds_p2': float(odds_l.get_text(strip=True)) if odds_l else None,
            }
        except Exception:
            return {'odds_p1': None, 'odds_p2': None}

    def _is_excluded(self, tournament: str) -> bool:
        t_low = tournament.lower()
        if any(excl in t_low for excl in EXCLUDED_SUBSTRINGS):
            return True
        if any(p.match(t_low) for p in EXCLUDED_PATTERNS):
            return True
        return False

    # ─── SCRAPING PRINCIPAL ───────────────────────────────

    def scrape_date(self, date_str: str, tour: str = 'atp') -> list:
        """Scrape tous les matchs d'un tour pour une date donnée"""
        config = TOUR_CONFIG[tour]
        parts = date_str.split('-')
        url = (f"https://www.tennisexplorer.com/results/"
               f"?type={config['url_type']}"
               f"&year={parts[0]}&month={parts[1]}&day={parts[2]}")

        print(f"🌐 [{tour.upper()}] Scraping {date_str}...")

        # Trouve le classement le plus proche
        ranking_date = self._get_ranking_date(date_str)
        if not ranking_date:
            print(f"⚠️  Aucun classement en DB — lance get_ranking.py d'abord")

        try:
            response = requests.get(
                url, headers=self.headers, verify=False, timeout=15
            )
            if response.status_code != 200:
                print(f"❌ HTTP {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', class_='result')
            if not table:
                print(f"ℹ️  Aucun match {tour.upper()} pour {date_str}")
                return []

            rows = table.find_all('tr')
            current_tournament = "Unknown"
            current_surface = "Hard"
            matches = []
            skipped = 0

            for i, row in enumerate(rows):
                classes = row.get('class', [])

                # Détection tournoi
                if any(c in classes for c in
                       ['head', 'head_no_st', 'head_multi', 'flags']):
                    t_cell = row.find('td', class_='t-name')
                    if t_cell:
                        current_tournament = t_cell.get_text(strip=True)
                        current_surface = self._get_surface(current_tournament)
                    continue

                # Filtre
                if self._is_excluded(current_tournament):
                    skipped += 1
                    continue

                # Ligne match
                row_id = row.get('id', '')
                if not row_id or row_id.endswith('b'):
                    continue
                if i + 1 >= len(rows):
                    continue

                row_b = rows[i + 1]

                try:
                    p1_cell = row.find('td', class_='t-name')
                    p2_cell = row_b.find('td', class_='t-name')
                    if not p1_cell or not p2_cell:
                        continue

                    p1_name = self._clean_name(p1_cell.get_text())
                    p2_name = self._clean_name(p2_cell.get_text())
                    if not p1_name or not p2_name:
                        continue

                    # Résolution vers nom complet (format players_rankings)
                    gender = config['gender']
                    p1_name = self._resolve_name(p1_name, gender)
                    p2_name = self._resolve_name(p2_name, gender)
                    winner = p1_name if 'bott' in classes else p2_name
                    score_data = self._parse_score(row, row_b)
                    if not score_data['is_valid']:
                        continue

                    odds = self._get_odds(row)

                    # Classements depuis la DB
                    p1_rank = self._get_player_ranking(
                        p1_name, config['gender'], ranking_date
                    )
                    p2_rank = self._get_player_ranking(
                        p2_name, config['gender'], ranking_date
                    )

                    time_cell = row.find('td', class_='time')
                    match_time = ""
                    if time_cell:
                        match_time = time_cell.get_text(
                            strip=True
                        ).split('\n')[0].strip()

                    best_of = 5 if any(
                        gs in current_tournament.lower()
                        for gs in GRAND_SLAMS
                    ) else 3

                    matches.append({
                        'date': date_str,
                        'time': match_time,
                        'tour': tour.upper(),
                        'tournament': current_tournament,
                        'surface': current_surface,
                        'best_of': best_of,
                        'player1': p1_name,
                        'player2': p2_name,
                        'winner': winner,
                        'score': score_data['score'],
                        'sets_won_p1': score_data['sets_won_p1'],
                        'sets_won_p2': score_data['sets_won_p2'],
                        'num_sets': score_data['num_sets'],
                        'odds_p1': odds['odds_p1'],
                        'odds_p2': odds['odds_p2'],
                        'p1_rank': p1_rank['rank'],
                        'p1_points': p1_rank['points'],
                        'p1_country': p1_rank['country'],
                        'p2_rank': p2_rank['rank'],
                        'p2_points': p2_rank['points'],
                        'p2_country': p2_rank['country'],
                        'ranking_date_used': ranking_date,
                    })

                except Exception:
                    continue

            print(f"✅ [{tour.upper()}] {len(matches)} matchs | {skipped} exclus")
            return matches

        except Exception as e:
            print(f"💥 Erreur {date_str} [{tour.upper()}] : {e}")
            return []

    # ─── SAUVEGARDE ───────────────────────────────────────

    def save_to_db(self, matches: list):
        """Sauvegarde les matchs en DB SQLite"""
        if not matches:
            return
        conn = get_connection()
        try:
            c = conn.cursor()
            saved = 0
            for m in matches:
                try:
                    c.execute('''INSERT OR IGNORE INTO matches_2026 (
                        date, time, tour, tournament, surface, best_of,
                        player1, player2, winner, score,
                        sets_won_p1, sets_won_p2, num_sets,
                        odds_p1, odds_p2,
                        p1_rank, p1_points, p1_country,
                        p2_rank, p2_points, p2_country,
                        ranking_date_used
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                        m['date'], m['time'], m['tour'], m['tournament'],
                        m['surface'], m['best_of'],
                        m['player1'], m['player2'], m['winner'], m['score'],
                        m['sets_won_p1'], m['sets_won_p2'], m['num_sets'],
                        m['odds_p1'], m['odds_p2'],
                        m['p1_rank'], m['p1_points'], m['p1_country'],
                        m['p2_rank'], m['p2_points'], m['p2_country'],
                        m['ranking_date_used']
                    ))
                    saved += c.rowcount
                except Exception:
                    continue
            conn.commit()
            print(f"💾 {saved} matchs sauvegardés en DB")
        finally:
            conn.close()

    def save_to_csv(self, matches: list, filename: str):
        """Sauvegarde les matchs en CSV"""
        if not matches:
            return
        df = pd.DataFrame(matches)
        filepath = f"{self.output_dir}/{filename}"
        df.to_csv(filepath, index=False, encoding='utf-8')
        print(f"💾 CSV sauvegardé : {filepath} ({len(df)} matchs)")
        return df

    # ─── TOURNOIS INCONNUS ────────────────────────────────

    def _print_unknown_tournaments(self):
        conn = get_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT tournament_key FROM tournament_surfaces WHERE surface = 'Unknown' ORDER BY tournament_key")
            unknowns = [row[0] for row in c.fetchall()]
        finally:
            conn.close()

        if unknowns:
            print(f"\n{'='*55}")
            print(f"⚠️  {len(unknowns)} tournois avec surface inconnue en DB :")
            print(f"{'='*55}")
            for t in unknowns:
                print(f"   ❓ {t}")
            print(f"\n💡 Pour corriger, lance :")
            print(f"   py set_surface.py 'Nom tournoi' Clay")
            print(f"{'='*55}\n")
        else:
            print("\n✅ Tous les tournois ont une surface connue !\n")

    # ─── COLLECTE ─────────────────────────────────────────

    def collect_date(self, date_str: str,
                     tours: list = None,
                     save_db: bool = True,
                     save_csv: bool = True) -> list:
        """Collecte une date pour ATP et/ou WTA"""
        if tours is None:
            tours = ['atp', 'wta']

        all_matches = []
        for tour in tours:
            matches = self.scrape_date(date_str, tour)
            all_matches.extend(matches)
            time.sleep(1)

        if save_db:
            self.save_to_db(all_matches)
        if save_csv and all_matches:
            self.save_to_csv(
                all_matches,
                f"tennis_{date_str}_{'_'.join(tours)}.csv"
            )

        return all_matches

    def collect_month(self, year: int, month: int,
                      tours: list = None,
                      save_db: bool = True,
                      save_csv: bool = True) -> list:
        """Collecte un mois entier"""
        if tours is None:
            tours = ['atp', 'wta']

        print(f"\n📅 Collecte {year}-{month:02d} "
              f"[{'/'.join(t.upper() for t in tours)}]...")

        _, num_days = monthrange(year, month)
        all_matches = []

        for day in range(1, num_days + 1):
            date_str = f"{year}-{month:02d}-{day:02d}"
            if datetime.strptime(date_str, "%Y-%m-%d") > datetime.now():
                break
            for tour in tours:
                matches = self.scrape_date(date_str, tour)
                all_matches.extend(matches)
                time.sleep(1)

        self._print_unknown_tournaments()

        if save_db:
            self.save_to_db(all_matches)
        if save_csv and all_matches:
            tours_str = '_'.join(tours)
            self.save_to_csv(
                all_matches,
                f"tennis_{year}_{month:02d}_{tours_str}.csv"
            )

        print(f"\n📊 Total : {len(all_matches)} matchs collectés")
        return all_matches

    def collect_range(self, start_date: str, end_date: str,
                      tours: list = None,
                      save_db: bool = True,
                      save_csv: bool = True) -> list:
        """Collecte sur une plage de dates"""
        if tours is None:
            tours = ['atp', 'wta']

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        current = start
        all_matches = []

        while current <= end and current <= datetime.now():
            date_str = current.strftime("%Y-%m-%d")
            for tour in tours:
                matches = self.scrape_date(date_str, tour)
                all_matches.extend(matches)
                time.sleep(1)
            current += timedelta(days=1)

        self._print_unknown_tournaments()

        if save_db:
            self.save_to_db(all_matches)
        if save_csv and all_matches:
            tours_str = '_'.join(tours)
            self.save_to_csv(
                all_matches,
                f"tennis_{start_date}_{end_date}_{tours_str}.csv"
            )

        print(f"\n📊 Total : {len(all_matches)} matchs collectés")
        return all_matches

    def collect_last_n_days(self, n: int = 30,
                             tours: list = None,
                             save_db: bool = True,
                             save_csv: bool = True) -> list:
        """Collecte les N derniers jours"""
        if tours is None:
            tours = ['atp', 'wta']
        end = datetime.now()
        start = end - timedelta(days=n)
        return self.collect_range(
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
            tours=tours,
            save_db=save_db,
            save_csv=save_csv
        )

    def migrate_names(self):
        """
        Migration one-shot : normalise les noms abrégés existants dans
        matches_2026 et le CSV global vers le format players_rankings.
        Idempotent : ne touche pas les noms déjà résolus.
        """
        print("🔄 Migration des noms dans matches_2026...")
        conn = get_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT id, player1, player2, winner, tour FROM matches_2026")
            rows = c.fetchall()
            updated = 0
            for row_id, p1, p2, winner, tour in rows:
                gender = 'F' if tour == 'WTA' else 'M'
                p1_new = self._resolve_name(p1, gender)
                p2_new = self._resolve_name(p2, gender)
                winner_new = self._resolve_name(winner, gender)
                if p1_new != p1 or p2_new != p2 or winner_new != winner:
                    try:
                        c.execute('''
                            UPDATE matches_2026
                            SET player1=?, player2=?, winner=?
                            WHERE id=?
                        ''', (p1_new, p2_new, winner_new, row_id))
                        updated += 1
                    except Exception:
                        # Doublon après résolution → supprime la ligne en double
                        c.execute('DELETE FROM matches_2026 WHERE id=?', (row_id,))
                        updated += 1
            conn.commit()
            print(f"   ✅ {updated}/{len(rows)} lignes mises à jour en DB")
        finally:
            conn.close()

        # Mise à jour du CSV global
        global_csv = f"{self.output_dir}/tennis_global_atp_wta.csv"
        if not os.path.exists(global_csv):
            print("⚠️  CSV global introuvable — migration DB uniquement")
            return

        print("🔄 Migration des noms dans le CSV global...")
        df = pd.read_csv(global_csv)
        csv_updated = 0
        for i, row in df.iterrows():
            gender = 'F' if row['tour'] == 'WTA' else 'M'
            p1_new = self._resolve_name(str(row['player1']), gender)
            p2_new = self._resolve_name(str(row['player2']), gender)
            w_new  = self._resolve_name(str(row['winner']), gender)
            if p1_new != row['player1'] or p2_new != row['player2'] or w_new != row['winner']:
                df.at[i, 'player1'] = p1_new
                df.at[i, 'player2'] = p2_new
                df.at[i, 'winner']  = w_new
                csv_updated += 1
        df.to_csv(global_csv, index=False, encoding='utf-8')
        print(f"   ✅ {csv_updated}/{len(df)} lignes mises à jour dans le CSV")

    def collect_yesterday(self, tours: list = None) -> list:
        """Job quotidien : collecte la veille et met a jour le CSV global"""
        if tours is None:
            tours = ['atp', 'wta']
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"\n📅 Collecte quotidienne : {yesterday}")
        matches = self.collect_date(yesterday, tours=tours, save_db=True, save_csv=False)
        if matches:
            self._append_to_global_csv(matches)
        return matches

    def _append_to_global_csv(self, matches: list):
        """Ajoute les nouveaux matchs au CSV global (sans doublons)"""
        global_path = f"{self.output_dir}/tennis_global_atp_wta.csv"
        df_new = pd.DataFrame(matches)
        if os.path.exists(global_path):
            df_existing = pd.read_csv(global_path)
            df_combined = pd.concat([df_existing, df_new]).drop_duplicates(
                subset=['date', 'player1', 'player2', 'tour']
            ).sort_values('date')
        else:
            df_combined = df_new
        df_combined.to_csv(global_path, index=False, encoding='utf-8')
        print(f"💾 CSV global mis a jour : {global_path} ({len(df_combined)} matchs total)")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    collector = MatchCollector()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "yesterday":
            collector.collect_yesterday()

        elif cmd == "range" and len(sys.argv) == 4:
            collector.collect_range(sys.argv[2], sys.argv[3])

        elif cmd == "month" and len(sys.argv) == 4:
            collector.collect_month(int(sys.argv[2]), int(sys.argv[3]))

        elif cmd == "migrate":
            # Migration one-shot : normalise les noms abrégés dans matches_2026 et le CSV
            collector.migrate_names()

        else:
            print("Usage:")
            print("  py match_collector.py                        # delta auto depuis CSV")
            print("  py match_collector.py yesterday")
            print("  py match_collector.py range 2025-01-01 2025-12-31")
            print("  py match_collector.py month 2025 4")
            print("  py match_collector.py migrate                # normalise noms existants")

    else:
        # Par défaut : détecte la date max du CSV global et scrape le delta
        global_csv = f"{collector.output_dir}/tennis_global_atp_wta.csv"
        today = datetime.now().strftime("%Y-%m-%d")

        if os.path.exists(global_csv):
            df_existing = pd.read_csv(global_csv)
            if not df_existing.empty and 'date' in df_existing.columns:
                max_date = df_existing['date'].max()
                # Démarre au lendemain de la dernière date connue
                start = (datetime.strptime(max_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                if start > today:
                    print(f"✅ CSV déjà à jour (dernière date : {max_date})")
                else:
                    print(f"📅 Delta détecté : {start} → {today}")
                    collector.collect_range(start, today)
            else:
                print("⚠️  CSV vide — collecte complète depuis 2025-01-01")
                collector.collect_range("2025-01-01", today)
        else:
            print("⚠️  CSV introuvable — collecte complète depuis 2025-01-01")
            collector.collect_range("2025-01-01", today)