import requests
from bs4 import BeautifulSoup
from database import get_connection
import urllib3
import re
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Tous les snapshots disponibles sur tennisexplorer pour 2025
# (extraits du dropdown de la page ranking)
DATES_2025 = [
    "2025-01-06", "2025-01-13", "2025-01-27",
    "2025-02-03", "2025-02-10", "2025-02-17", "2025-02-24",
    "2025-03-03", "2025-03-17", "2025-03-31",
    "2025-04-07", "2025-04-14", "2025-04-21",
    "2025-05-05", "2025-05-19", "2025-05-26",
    "2025-06-09", "2025-06-16", "2025-06-23", "2025-06-30",
    "2025-07-14", "2025-07-21", "2025-07-28",
    "2025-08-04", "2025-08-18", "2025-08-25",
    "2025-09-08", "2025-09-15", "2025-09-22", "2025-09-29",
    "2025-10-13", "2025-10-20", "2025-10-27",
    "2025-11-03", "2025-11-10", "2025-11-17", "2025-11-24",
    "2025-12-01", "2025-12-08", "2025-12-15", "2025-12-22", "2025-12-29",
]

# Snapshots 2026 disponibles (à compléter au fur et à mesure)
DATES_2026 = [
    "2026-01-06", "2026-01-13", "2026-01-20", "2026-01-27",
    "2026-02-03", "2026-02-10", "2026-02-17", "2026-02-24",
    "2026-03-03", "2026-03-17", "2026-03-31",
    "2026-04-07", "2026-04-14",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def clean_name(name):
    return re.sub(r'\(.*?\)', '', name).strip()


def already_in_db(date_recorded, gender):
    """Vérifie si ce snapshot est déjà en base pour éviter de re-scraper."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT COUNT(*) FROM players_rankings WHERE date_recorded = ? AND gender = ?",
        (date_recorded, gender)
    )
    count = c.fetchone()[0]
    conn.close()
    return count > 0


def scrape_rankings_for_date(gender_url, date_str, limit=1000):
    """Scrape le classement tennisexplorer pour une date donnée."""
    gender = 'M' if gender_url == 'atp-men' else 'F'
    year = date_str[:4]
    pages = limit // 50
    all_players = []

    for page in range(1, pages + 1):
        url = (
            f"https://www.tennisexplorer.com/ranking/{gender_url}/{year}/"
            f"?date={date_str}&page={page}"
        )
        try:
            res = requests.get(url, headers=HEADERS, verify=False, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.select('table.result tbody.flags tr')

            if not rows:
                break

            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 5:
                    rank_txt = cells[0].get_text(strip=True).replace('.', '')
                    name = clean_name(cells[2].get_text(strip=True))
                    country = cells[3].get_text(strip=True)
                    points_txt = cells[4].get_text(strip=True)

                    try:
                        all_players.append({
                            'rank': int(rank_txt),
                            'name': name,
                            'country': country,
                            'points': int(points_txt),
                            'gender': gender,
                        })
                    except ValueError:
                        continue

            time.sleep(1.2)

        except Exception as e:
            print(f"    ❌ Erreur page {page} ({url}): {e}")
            break

    return all_players


def save_to_db(players, date_recorded):
    if not players:
        return

    conn = get_connection()
    c = conn.cursor()
    for p in players:
        c.execute(
            '''INSERT OR REPLACE INTO players_rankings
               (name, rank, points, country, gender, date_recorded)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (p['name'], p['rank'], p['points'], p['country'], p['gender'], date_recorded)
        )
    conn.commit()
    conn.close()


def backfill(dates, dry_run=False):
    total = len(dates) * 2  # ATP + WTA
    done = 0

    for date_str in dates:
        for gender_url, label in [('atp-men', 'ATP'), ('wta-women', 'WTA')]:
            gender = 'M' if gender_url == 'atp-men' else 'F'
            done += 1

            if already_in_db(date_str, gender):
                print(f"[{done}/{total}] ⏭️  {date_str} {label} — déjà en base, skip")
                continue

            print(f"[{done}/{total}] 🔄 {date_str} {label}...", end=' ', flush=True)

            if dry_run:
                print("(dry run)")
                continue

            players = scrape_rankings_for_date(gender_url, date_str)
            if players:
                save_to_db(players, date_str)
                print(f"✅ {len(players)} joueurs sauvegardés")
            else:
                print("⚠️  Aucun joueur récupéré")

            # Pause entre chaque snapshot pour ne pas surcharger le site
            time.sleep(2)


if __name__ == "__main__":
    import sys

    dry_run = "--dry-run" in sys.argv
    year_filter = None
    for arg in sys.argv[1:]:
        if arg in ("2025", "2026"):
            year_filter = arg

    if year_filter == "2026":
        dates = DATES_2026
    elif year_filter == "2025":
        dates = DATES_2025
    else:
        dates = DATES_2025 + DATES_2026

    print(f"🎾 Backfill rankings — {len(dates)} snapshots × 2 tours")
    print(f"   Mode : {'DRY RUN' if dry_run else 'RÉEL'}\n")

    backfill(dates, dry_run=dry_run)
    print("\n✅ Backfill terminé.")