"""Prix des carburants autour de la ville configurée + historique quotidien.

Source : data.economie.gouv.fr (prix des carburants en France, flux instantané v2).
Sorties :
    docs/data/fuel.json          -> stations du jour + résumé par carburant
    docs/data/fuel_history.json  -> une ligne par jour (min / moyenne / nb stations)
"""
import datetime as dt
import math

import requests

from common import DATA, UA, load_config, read_json, write_json

URL = (
    "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
    "prix-des-carburants-en-france-flux-instantane-v2/records"
)
FUELS = {
    "gazole": "gazole_prix",
    "sp95": "sp95_prix",
    "e10": "e10_prix",
    "sp98": "sp98_prix",
    "e85": "e85_prix",
    "gplc": "gplc_prix",
}
HISTORY_DAYS = 800


def haversine(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def fetch_records(lat: float, lon: float, radius_km: int) -> list:
    where = f"within_distance(geom, geom'POINT({lon} {lat})', {radius_km}km)"
    out, offset = [], 0
    while True:
        r = requests.get(
            URL,
            params={"where": where, "limit": 100, "offset": offset},
            headers=UA,
            timeout=40,
        )
        r.raise_for_status()
        batch = r.json().get("results", [])
        out += batch
        if len(batch) < 100:
            return out
        offset += 100


def main() -> None:
    cfg = load_config()
    lat, lon, rad = cfg["latitude"], cfg["longitude"], cfg["fuel_radius_km"]
    records = fetch_records(lat, lon, rad)

    stations = []
    for rec in records:
        g = rec.get("geom") or {}
        s_lat, s_lon = g.get("lat"), g.get("lon")
        prices = {k: rec.get(f) for k, f in FUELS.items() if rec.get(f) is not None}
        if not prices:
            continue
        stations.append(
            {
                "id": rec.get("id"),
                "address": rec.get("adresse"),
                "city": rec.get("ville"),
                "distance_km": round(haversine(lat, lon, s_lat, s_lon), 1)
                if s_lat is not None and s_lon is not None
                else None,
                "prices": prices,
                "updated": {k: rec.get(FUELS[k].replace("_prix", "_maj")) for k in prices},
            }
        )
    stations.sort(key=lambda s: (s["distance_km"] is None, s["distance_km"] or 0))

    summary = {}
    for fuel in FUELS:
        vals = [(s["prices"][fuel], s) for s in stations if fuel in s["prices"]]
        if not vals:
            continue
        best_price, best = min(vals, key=lambda v: v[0])
        summary[fuel] = {
            "min": round(best_price, 3),
            "avg": round(sum(v[0] for v in vals) / len(vals), 3),
            "n": len(vals),
            "cheapest": f"{best['address']}, {best['city']}",
            "cheapest_km": best["distance_km"],
        }

    now = dt.datetime.now(dt.timezone.utc)
    write_json(
        DATA / "fuel.json",
        {
            "generated": now.isoformat(timespec="seconds"),
            "city": cfg["city"],
            "radius_km": rad,
            "summary": summary,
            "stations": stations,
        },
    )

    # Historique : une entrée par jour (la dernière exécution du jour l'emporte).
    # Si la ville change, on repart d'un historique propre.
    path = DATA / "fuel_history.json"
    hist = read_json(path, {"city": cfg["city"], "days": []})
    if hist.get("city") != cfg["city"]:
        hist = {"city": cfg["city"], "days": []}
    today = now.date().isoformat()
    hist["days"] = [d for d in hist["days"] if d["date"] != today]
    hist["days"].append(
        {
            "date": today,
            "fuels": {k: {"min": v["min"], "avg": v["avg"], "n": v["n"]} for k, v in summary.items()},
        }
    )
    hist["days"] = sorted(hist["days"], key=lambda d: d["date"])[-HISTORY_DAYS:]
    write_json(path, hist)

    print(f"{len(stations)} stations autour de {cfg['city']} ({rad} km)")
    for k, v in summary.items():
        print(f"  {k:7s} min {v['min']:.3f} €  moy {v['avg']:.3f} €  ({v['n']} stations)")


if __name__ == "__main__":
    main()
