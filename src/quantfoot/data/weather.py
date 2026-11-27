"""Free, zero-key Open-Meteo match-time severe weather checker (heavy rain, high wind, snow).

Severe precipitation or high wind systematically depresses passing accuracy and scoring totals
(especially dangerous for Over / BTTS legs). This module fetches hourly forecasts from
``https://api.open-meteo.com/v1/forecast`` cached per ``(lat, lon, date)`` and emits concise
Turkish weather warnings only when kick-off conditions exceed severe thresholds.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import requests

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

RAIN_SEVERE_MM = 4.0      # >= 4.0 mm/h heavy rain
WIND_SEVERE_KMH = 38.0    # >= 38 km/h strong wind
SNOW_SEVERE_CM = 1.0      # >= 1.0 cm/h snowfall

#: Approximate coordinates (lat, lon) for major football countries / cities (used when venue coords unavailable).
COUNTRY_COORDS: dict[str, tuple[float, float]] = {
    "türkiye": (41.01, 28.97),
    "ingiltere": (52.48, -1.89),
    "iskoçya": (55.86, -4.25),
    "galler": (51.48, -3.18),
    "kuzey irlanda": (54.60, -5.93),
    "almanya": (51.16, 10.45),
    "ispanya": (40.42, -3.70),
    "italya": (43.77, 11.25),
    "fransa": (48.86, 2.35),
    "hollanda": (52.37, 4.90),
    "belçika": (50.85, 4.35),
    "portekiz": (38.72, -9.14),
    "avusturya": (48.21, 16.37),
    "isviçre": (47.37, 8.54),
    "norveç": (59.91, 10.75),
    "isveç": (59.33, 18.07),
    "danimarka": (55.68, 12.57),
    "polonya": (52.23, 21.01),
    "rusya": (55.75, 37.62),
    "ukrayna": (50.45, 30.52),
    "romanya": (44.43, 26.10),
    "yunanistan": (37.98, 23.73),
    "japonya": (35.68, 139.69),
    "avustralya": (-33.87, 151.21),
    "brezilya": (-23.55, -46.63),
    "arjantin": (-34.60, -58.38),
    "abd": (40.71, -74.01),
    "meksika": (19.43, -99.13),
}

CITY_COORDS: dict[str, tuple[float, float]] = {
    "istanbul": (41.01, 28.97),
    "ankara": (39.93, 32.85),
    "izmir": (38.42, 27.14),
    "trabzon": (41.00, 39.72),
    "london": (51.51, -0.13),
    "manchester": (53.48, -2.24),
    "liverpool": (53.41, -2.99),
    "birmingham": (52.48, -1.89),
    "madrid": (40.42, -3.70),
    "barcelona": (41.39, 2.17),
    "seville": (37.39, -5.98),
    "munich": (48.14, 11.58),
    "dortmund": (51.51, 7.47),
    "berlin": (52.52, 13.40),
    "hamburg": (53.55, 9.99),
    "frankfurt": (50.11, 8.68),
    "milan": (45.46, 9.19),
    "rome": (41.90, 12.50),
    "naples": (40.85, 14.27),
    "turin": (45.07, 7.69),
    "paris": (48.86, 2.35),
    "lyon": (45.76, 4.84),
    "marseille": (43.30, 5.37),
    "amsterdam": (52.37, 4.90),
    "rotterdam": (51.92, 4.48),
    "lisbon": (38.72, -9.14),
    "porto": (41.15, -8.61),
    "glasgow": (55.86, -4.25),
    "edinburgh": (55.95, -3.19),
    "newcastle": (54.97, -1.61),
    "leeds": (53.80, -1.55),
    "brighton": (50.82, -0.14),
    "leicester": (52.63, -1.13),
    "nottingham": (52.95, -1.15),
    "sheffield": (53.38, -1.47),
    "bristol": (51.45, -2.59),
    "southampton": (50.90, -1.40),
    "cardiff": (51.48, -3.18),
    "valencia": (39.47, -0.38),
    "bilbao": (43.26, -2.93),
    "san sebastian": (43.32, -1.98),
    "villarreal": (39.94, -0.10),
    "vigo": (42.24, -8.72),
    "stuttgart": (48.78, 9.18),
    "leipzig": (51.34, 12.37),
    "cologne": (50.94, 6.96),
    "koln": (50.94, 6.96),
    "leverkusen": (51.04, 6.98),
    "bremen": (53.08, 8.80),
    "freiburg": (48.00, 7.85),
    "florence": (43.77, 11.25),
    "bologna": (44.49, 11.34),
    "genoa": (44.41, 8.93),
    "verona": (45.44, 10.99),
    "bergamo": (45.70, 9.67),
    "lille": (50.63, 3.06),
    "monaco": (43.73, 7.42),
    "nice": (43.71, 7.26),
    "lens": (50.43, 2.83),
    "rennes": (48.11, -1.68),
    "nantes": (47.22, -1.55),
    "strasbourg": (48.57, 7.75),
    "eindhoven": (51.44, 5.47),
    "utrecht": (52.09, 5.12),
    "alkmaar": (52.63, 4.75),
    "brussels": (50.85, 4.35),
    "bruges": (51.21, 3.22),
    "ghent": (51.05, 3.72),
    "antwerp": (51.22, 4.40),
    "athens": (37.98, 23.73),
    "thessaloniki": (40.64, 22.94),
    "vienna": (48.21, 16.37),
    "salzburg": (47.81, 13.06),
    "zurich": (47.37, 8.54),
    "basel": (47.56, 7.59),
    "bern": (46.95, 7.45),
    "oslo": (59.91, 10.75),
    "stockholm": (59.33, 18.07),
    "copenhagen": (55.68, 12.57),
    "warsaw": (52.23, 21.01),
    "prague": (50.08, 14.44),
    "antalya": (36.90, 30.71),
    "konya": (37.87, 32.48),
    "gaziantep": (37.07, 37.38),
    "kayseri": (38.73, 35.48),
    "samsun": (41.29, 36.33),
    "adana": (37.00, 35.32),
    "sivas": (39.75, 37.02),
    "rize": (41.02, 40.52),
    "alanya": (36.54, 32.00),
    "bursa": (40.19, 29.06),
    "buenos aires": (-34.60, -58.38),
    "sao paulo": (-23.55, -46.63),
    "rio de janeiro": (-22.91, -43.17),
}


def resolve_coords(league: str = "", city: str | None = None) -> tuple[float, float] | None:
    """Resolve approximate stadium/league coordinates for Open-Meteo lookup."""
    if city:
        low_c = str(city).strip().lower()
        for k, coords in CITY_COORDS.items():
            if k in low_c:
                return coords
    low_l = str(league).replace("İ", "i").replace("I", "i").lower()
    for country, coords in COUNTRY_COORDS.items():
        if country in low_l:
            return coords
    return None


def evaluate_hourly_weather(payload: dict[str, Any], kickoff_utc: dt.datetime) -> dict[str, Any] | None:
    """Evaluate Open-Meteo hourly JSON at the kick-off hour and return weather metrics + severe flag."""
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    rains = hourly.get("precipitation") or []
    winds = hourly.get("wind_speed_10m") or []
    snows = hourly.get("snowfall") or []
    temps = hourly.get("temperature_2m") or []
    if not times:
        return None

    ko = kickoff_utc.astimezone(dt.timezone.utc) if kickoff_utc.tzinfo else kickoff_utc.replace(tzinfo=dt.timezone.utc)
    target_hour = ko.strftime("%Y-%m-%dT%H:00")
    try:
        idx = times.index(target_hour)
    except ValueError:
        return None

    rain = float(rains[idx]) if idx < len(rains) and rains[idx] is not None else 0.0
    wind = float(winds[idx]) if idx < len(winds) and winds[idx] is not None else 0.0
    snow = float(snows[idx]) if idx < len(snows) and snows[idx] is not None else 0.0
    temp = float(temps[idx]) if idx < len(temps) and temps[idx] is not None else None

    reasons: list[str] = []
    if rain >= RAIN_SEVERE_MM:
        reasons.append(f"şiddetli yağmur ({rain:.1f} mm/s)")
    if snow >= SNOW_SEVERE_CM:
        reasons.append(f"kar yağışı ({snow:.1f} cm/s)")
    if wind >= WIND_SEVERE_KMH:
        reasons.append(f"sert rüzgar ({wind:.0f} km/s)")

    flag = f"Hava uyarısı: {', '.join(reasons)} (Üst/tempo riski)" if reasons else None
    return {
        "hour_utc": target_hour,
        "temp_c": round(temp, 1) if temp is not None else None,
        "rain_mm": round(rain, 1),
        "wind_kmh": round(wind, 1),
        "snow_cm": round(snow, 1),
        "severe": bool(reasons),
        "flag": flag,
    }


def fetch_matchday_weather(
    matches: list[dict[str, Any]],
    *,
    timeout: int = 8,
) -> dict[Any, dict[str, Any]]:
    """Fetch kick-off weather flags for matches with resolvable coordinates (batched & cached per coord/date)."""
    cache: dict[tuple[float, float, str], dict[str, Any] | None] = {}
    out: dict[Any, dict[str, Any]] = {}
    sess = requests.Session()
    try:
        for m in matches:
            ko_iso = m.get("kickoff_iso")
            if not ko_iso:
                continue
            try:
                ko = dt.datetime.fromisoformat(ko_iso).astimezone(dt.timezone.utc)
            except ValueError:
                continue
            venue_city = ((m.get("research") or {}).get("venue_city"))
            coords = resolve_coords(m.get("league", ""), city=venue_city)
            if not coords:
                continue
            day_str = ko.strftime("%Y-%m-%d")
            key = (coords[0], coords[1], day_str)
            if key not in cache:
                try:
                    r = sess.get(
                        OPEN_METEO_URL,
                        params={
                            "latitude": coords[0],
                            "longitude": coords[1],
                            "hourly": "temperature_2m,precipitation,snowfall,wind_speed_10m",
                            "start_date": day_str,
                            "end_date": day_str,
                            "timezone": "UTC",
                        },
                        timeout=timeout,
                    )
                    cache[key] = r.json() if r.status_code == 200 else None
                except (requests.RequestException, ValueError):
                    cache[key] = None
            payload = cache[key]
            if not payload:
                continue
            ev = evaluate_hourly_weather(payload, ko)
            if ev is not None:
                out[m["code"]] = ev
    finally:
        sess.close()
    return out
