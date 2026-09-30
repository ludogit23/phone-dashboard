"""Prix spot de l'électricité (France, day-ahead) + historique quotidien.

Source : Energy-Charts (Fraunhofer ISE), sans clé.
Sorties :
    docs/data/electricity.json          -> prix horaires (J-3 à demain si publié)
    docs/data/electricity_history.json  -> moyenne / min / max par jour, en c€/kWh
Note : c'est le prix de GROS. Ton tarif réglementé ne bouge pas avec.
"""
import datetime as dt
from collections import defaultdict
from zoneinfo import ZoneInfo

import requests

from common import DATA, UA, read_json, write_json

URL = "https://api.energy-charts.info/price"
TZ = ZoneInfo("Europe/Paris")
HISTORY_DAYS = 800


def main() -> None:
    today = dt.datetime.now(TZ).date()
    start = (today - dt.timedelta(days=3)).isoformat()
    end = (today + dt.timedelta(days=1)).isoformat()

    r = requests.get(URL, params={"bzn": "FR", "start": start, "end": end}, headers=UA, timeout=40)
    r.raise_for_status()
    j = r.json()
    ts, prices = j["unix_seconds"], j["price"]

    hourly, per_day = [], defaultdict(list)
    for t, p in zip(ts, prices):
        if p is None:
            continue
        local = dt.datetime.fromtimestamp(t, TZ)
        ckwh = round(p / 10, 3)  # €/MWh -> c€/kWh
        hourly.append({"t": local.isoformat(timespec="minutes"), "c_kwh": ckwh})
        per_day[local.date().isoformat()].append(ckwh)

    write_json(
        DATA / "electricity.json",
        {
            "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "unit": "c€/kWh (prix spot, hors taxes et acheminement)",
            "hourly": hourly,
        },
    )

    path = DATA / "electricity_history.json"
    hist = read_json(path, {"days": []})
    by_date = {d["date"]: d for d in hist["days"]}
    for day, vals in per_day.items():
        by_date[day] = {
            "date": day,
            "avg": round(sum(vals) / len(vals), 3),
            "min": min(vals),
            "max": max(vals),
            "n": len(vals),
        }
    hist["days"] = sorted(by_date.values(), key=lambda d: d["date"])[-HISTORY_DAYS:]
    write_json(path, hist)

    print(f"{len(hourly)} points, {len(per_day)} jours ({start} -> {end})")


if __name__ == "__main__":
    main()
