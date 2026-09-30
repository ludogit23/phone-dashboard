"""Lance toutes les collectes (utile en local pour tester)."""
import fetch_electricity
import fetch_fuel
import fetch_weather_air

for mod in (fetch_weather_air, fetch_fuel, fetch_electricity):
    print(f"\n=== {mod.__name__} ===")
    try:
        mod.main()
    except Exception as e:  # une source en panne ne bloque pas les autres
        print(f"ERREUR {mod.__name__}: {e}")
