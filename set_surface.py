"""
Corrige la surface d'un ou plusieurs tournois dans tournament_surfaces.

Usage :
    py set_surface.py "Marrakech" Clay
    py set_surface.py "Madrid" Clay
    py set_surface.py --list          # Affiche tous les Unknown
    py set_surface.py --all           # Affiche toute la table
"""

import sys
from database import get_connection


def list_unknowns():
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM tournament_surfaces WHERE surface = 'Unknown' ORDER BY name")
        rows = c.fetchall()
        if rows:
            print(f"\n⚠️  {len(rows)} tournois avec surface inconnue :\n")
            for r in rows:
                print(f"   ❓ {r[0]}")
            print(f"\n💡 Corriger avec : py set_surface.py 'Nom tournoi' Clay|Hard|Grass\n")
        else:
            print("\n✅ Aucun tournoi inconnu !\n")
    finally:
        conn.close()


def list_all():
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT name, surface FROM tournament_surfaces ORDER BY surface, name")
        rows = c.fetchall()
        print(f"\n{'Tournoi':<45} {'Surface'}")
        print("-" * 55)
        for name, surface in rows:
            icon = "❓" if surface == "Unknown" else "✅"
            print(f"   {icon} {name:<43} {surface}")
        print(f"\n📋 Total : {len(rows)} tournois\n")
    finally:
        conn.close()


def set_surface(tournament: str, surface: str):
    surface = surface.capitalize()
    if surface not in ('Clay', 'Hard', 'Grass', 'Unknown'):
        print(f"❌ Surface invalide : {surface}. Valeurs : Clay, Hard, Grass")
        return

    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO tournament_surfaces (name, surface)
            VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET surface = excluded.surface
        """, (tournament, surface))
        conn.commit()
        print(f"✅ '{tournament}' → {surface}")
    finally:
        conn.close()


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
    elif args[0] == '--list':
        list_unknowns()
    elif args[0] == '--all':
        list_all()
    elif len(args) == 2:
        set_surface(args[0], args[1])
    else:
        print("❌ Usage : py set_surface.py 'Nom tournoi' Clay")
        print("           py set_surface.py --list")
        print("           py set_surface.py --all")