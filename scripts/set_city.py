"""Change la ville du dashboard.

Usage :
    python scripts/set_city.py "Lannion"
    python scripts/set_city.py "Saint-Brieuc" --pick 2     # 2e résultat de la liste
    python scripts/set_city.py "Brest" --radius 20
"""
import argparse
import json
import sys

import requests

from common import CONFIG_PATH, UA, load_config

GEO = "https://geocoding-api.open-meteo.com/v1/search"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ville")
    ap.add_argument("--pick", type=int, default=1, help="numéro du résultat (défaut 1)")
    ap.add_argument("--radius", type=int, help="rayon carburants en km")
    a = ap.parse_args()

    r = requests.get(
        GEO,
        params={"name": a.ville, "count": 8, "language": "fr", "countryCode": "FR"},
        headers=UA,
        timeout=20,
    )
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        sys.exit(f"Aucune ville trouvée pour « {a.ville} ».")

    for i, c in enumerate(results, 1):
        cp = (c.get("postcodes") or [""])[0]
        print(f"{i}. {c['name']} {cp} ({c.get('admin2') or c.get('admin1', '')})")

    if not 1 <= a.pick <= len(results):
        sys.exit("Numéro --pick invalide.")
    c = results[a.pick - 1]

    cfg = load_config()
    cfg.update(
        city=c["name"],
        postcode=(c.get("postcodes") or [""])[0],
        latitude=round(c["latitude"], 4),
        longitude=round(c["longitude"], 4),
        timezone=c.get("timezone", "Europe/Paris"),
    )
    if a.radius:
        cfg["fuel_radius_km"] = a.radius
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ Ville définie : {cfg['city']} ({cfg['latitude']}, {cfg['longitude']})")
    print("Relance run_all.py (ou pousse sur GitHub) pour régénérer les données.")


if __name__ == "__main__":
    main()
