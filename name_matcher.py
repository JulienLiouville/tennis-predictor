"""
Module de matching des noms pour réconcilier TennisExplorer et Odds API.

TennisExplorer utilise format abrégé: "Sinner J."
Odds API utilise format complet: "Jannik Sinner"

Ce module extrait les noms de famille pour faire le matching.
"""

import unicodedata


def normalize_name(name: str) -> str:
    """Normalise un nom : enlève accents, minuscules."""
    name = unicodedata.normalize('NFD', name)
    return ''.join(c for c in name if unicodedata.category(c) != 'Mn').lower().strip()


def extract_last_name(name: str) -> str:
    """
    Extrait le nom de famille d'un nom complet ou abrégé.

    Exemples:
    - "Jannik Sinner" → "sinner"
    - "Sinner J." → "sinner"
    - "Sinner Jannik" → "sinner"
    - "Van de Zandschulp B." → "van de zandschulp"
    - "Victoria Mboko" → "mboko"
    - "Madison Keys" → "keys"
    """
    name = normalize_name(name)
    parts = name.split()

    if not parts:
        return name

    # Si dernier mot est une initiale (1-2 chars + possibles points), c'est le prénom
    # Format: "Sinner J." ou "Van de Zandschulp B."
    last_part = parts[-1].replace('.', '')
    if len(parts) > 1 and len(last_part) <= 2 and last_part.isalpha():
        # Première partie = famille
        return ' '.join(parts[:-1])

    # Sinon, assume format "Jannik Sinner" ou "Matteo Berrettini"
    # Dernier mot = famille
    return parts[-1]


def make_match_key(p1: str, p2: str) -> str:
    """
    Crée une clé de matching pour deux joueurs basée sur leurs noms de famille.

    Permet de matcher:
    - "Sinner J." avec "Jannik Sinner"
    - "Mboko V." avec "Victoria Mboko"
    - etc.
    """
    last1 = extract_last_name(p1)
    last2 = extract_last_name(p2)
    return '_vs_'.join(sorted([last1, last2]))


# Tests
if __name__ == "__main__":
    test_cases = [
        (("Sinner J.", "Jannik Sinner"), True),
        (("Victoria Mboko", "Mboko V."), True),
        (("Van de Zandschulp B.", "Botic Van de Zandschulp"), True),
        (("Matteo Berrettini", "Berrettini M."), True),
        (("Carlos Alcaraz", "Alcaraz C."), True),
    ]

    print("🔤 TEST MATCHING NOMS\n")
    for (name1, name2), should_match in test_cases:
        key1 = make_match_key(name1, "dummy")
        key2 = make_match_key(name2, "dummy")
        matches = key1 == key2
        icon = "✅" if matches == should_match else "❌"
        print(f"{icon} '{name1}' ↔ '{name2}'")
        if not matches == should_match:
            print(f"   Key1: {key1}")
            print(f"   Key2: {key2}")