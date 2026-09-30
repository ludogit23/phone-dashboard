"""Météo + qualité de l'air + pollens (Open-Meteo), en cache JSON.

Le téléphone appelle Open-Meteo en direct ; ce cache sert de secours hors ligne
et permet de vérifier rapidement les données depuis ton PC.
"""
import datetime as dt

import requests

from common import DATA, UA, load_config, write_json

WEATHER = "https://api.open-meteo.com/v1/forecast"
AIR = "https://air-quality-api.open-meteo.com/v1/air-quality"


def main() -> None:
    cfg = load_config()
    base = {"latitude": cfg["latitude"], "longitude": cfg["longitude"], "timezone": cfg["timezone"]}

    w = requests.get(
        WEATHER,
        params={
            **base,
            "models": "meteofrance_seamless",
            "forecast_days": 2,
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,wind_gusts_10m",
            "hourly": "temperature_2m,apparent_temperature,precipitation_probability,precipitation,weather_code,wind_speed_10m,wind_gusts_10m",
            "daily": "temperature_2m_max,temperature_2m_min,sunrise,sunset,uv_index_max,weather_code",
        },
        headers=UA,
        timeout=30,
    )
    w.raise_for_status()

    a = requests.get(
        AIR,
        params={
            **base,
            "forecast_days": 2,
            "current": "european_aqi,pm10,pm2_5",
            "hourly": "european_aqi,pm10,pm2_5,alder_pollen,birch_pollen,grass_pollen,mugwort_pollen,olive_pollen,ragweed_pollen",
        },
        headers=UA,
        timeout=30,
    )
    a.raise_for_status()

    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    wj, aj = w.json(), a.json()
    write_json(DATA / "weather.json", {"generated": stamp, "city": cfg["city"], **wj})
    write_json(DATA / "air.json", {"generated": stamp, "city": cfg["city"], **aj})
    print(f"{cfg['city']} : {wj.get('current', {}).get('temperature_2m')} °C, AQI européen : {aj.get('current', {}).get('european_aqi')}")


if __name__ == "__main__":
    main()
