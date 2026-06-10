"""
ThingSpeak client + sensor logic for MineGuard.

YOUR CHANNEL FIELD MAPPING (from screenshot):
    field1  →  gas         (MQ4  — methane, raw ppm value)
    field2  →  temp        (DHT22 — temperature in °C)
    field3  →  hum         (DHT22 — humidity in %)
    field4  →  Accelerometer (MPU6050 — 1 = fall detected, 0 = normal)
"""

import requests
from config import Config

THINGSPEAK_BASE = "https://api.thingspeak.com"

# ── Thresholds (single source — mirrors config.py) ───────────────────────────
THRESHOLDS = {
    'temperature': {'warning': Config.TEMP_WARNING, 'danger': Config.TEMP_DANGER},
    'humidity':    {'warning': Config.HUM_WARNING,  'danger': Config.HUM_DANGER},
    'methane':     {'warning': Config.GAS_WARNING,  'danger': Config.GAS_DANGER},
}


# ── ThingSpeak API calls ──────────────────────────────────────────────────────

def fetch_latest(channel_id: str, api_key: str) -> dict | None:
    """Fetch the single most-recent feed entry from ThingSpeak."""
    url = f"{THINGSPEAK_BASE}/channels/{channel_id}/feeds/last.json"
    try:
        resp = requests.get(url, params={'api_key': api_key}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[ThingSpeak] fetch_latest error: {e}")
        return None


def fetch_history(channel_id: str, api_key: str, results: int = 100) -> list:
    """Fetch recent N feed entries from ThingSpeak."""
    url = f"{THINGSPEAK_BASE}/channels/{channel_id}/feeds.json"
    try:
        resp = requests.get(url, params={'api_key': api_key, 'results': results}, timeout=10)
        resp.raise_for_status()
        return resp.json().get('feeds', [])
    except Exception as e:
        print(f"[ThingSpeak] fetch_history error: {e}")
        return []


# ── Feed parser ──────────────────────────────────────────────────────────────

def _safe_float(feed: dict, key: str) -> float | None:
    """Safely parse a float from a feed dict key."""
    try:
        v = feed.get(key)
        return float(v) if v not in (None, '', 'nan', 'NaN') else None
    except (ValueError, TypeError):
        return None


def parse_feed(feed: dict) -> dict:
    """
    Parse raw ThingSpeak feed → typed sensor values.

    Channel field mapping:
        field1 = methane     (MQ4,    ppm)
        field2 = temperature (DHT22,  °C)
        field3 = humidity    (DHT22,  %)
        field4 = accelerometer (MPU6050, 1=fall / 0=ok)
    """
    methane     = _safe_float(feed, Config.FIELD_METHANE)      # field1
    temperature = _safe_float(feed, Config.FIELD_TEMPERATURE)  # field2
    humidity    = _safe_float(feed, Config.FIELD_HUMIDITY)     # field3
    accel_raw   = _safe_float(feed, Config.FIELD_ACCEL)        # field4

    # MPU6050 sends 1 when fall detected, 0 when normal
    fall_detected = (accel_raw == 1.0) if accel_raw is not None else False

    danger_level = compute_danger(temperature, humidity, methane, fall_detected)

    return {
        'temperature':   temperature,
        'humidity':      humidity,
        'methane':       methane,
        'fall_detected': fall_detected,
        'danger_level':  danger_level,
        'created_at':    feed.get('created_at', ''),
    }


# ── Danger computation ───────────────────────────────────────────────────────

def compute_danger(temp, hum, methane, fall) -> str:
    """
    Return overall danger level.
    Priority: fall > methane danger > temp danger > methane warning > temp warning > hum warning > safe
    """
    if fall:
        return 'danger'
    if methane  is not None and methane  >= THRESHOLDS['methane']['danger']:
        return 'danger'
    if temp     is not None and temp     >= THRESHOLDS['temperature']['danger']:
        return 'danger'
    if methane  is not None and methane  >= THRESHOLDS['methane']['warning']:
        return 'warning'
    if temp     is not None and temp     >= THRESHOLDS['temperature']['warning']:
        return 'warning'
    if hum      is not None and hum      >= THRESHOLDS['humidity']['warning']:
        return 'warning'
    return 'safe'


# ── Alert generation ─────────────────────────────────────────────────────────

def generate_alerts(parsed: dict) -> list[dict]:
    """
    Return list of alert dicts for every threshold crossed.
    Each dict: { alert_type, message, level }
    """
    alerts = []
    t    = parsed.get('temperature')
    h    = parsed.get('humidity')
    m    = parsed.get('methane')
    fall = parsed.get('fall_detected', False)

    if fall:
        alerts.append({
            'alert_type': 'fall',
            'message': '⚠️ FALL / IMPACT detected on mining helmet!',
            'level': 'danger'
        })

    if m is not None:
        if m >= THRESHOLDS['methane']['danger']:
            alerts.append({
                'alert_type': 'methane',
                'message': f'🔥 CRITICAL methane level: {m:.0f} ppm (limit: {Config.GAS_DANGER} ppm)',
                'level': 'danger'
            })
        elif m >= THRESHOLDS['methane']['warning']:
            alerts.append({
                'alert_type': 'methane',
                'message': f'⚡ Elevated methane gas: {m:.0f} ppm (warning at: {Config.GAS_WARNING} ppm)',
                'level': 'warning'
            })

    if t is not None:
        if t >= THRESHOLDS['temperature']['danger']:
            alerts.append({
                'alert_type': 'temperature',
                'message': f'🌡️ DANGEROUS temperature: {t:.1f}°C (limit: {Config.TEMP_DANGER}°C)',
                'level': 'danger'
            })
        elif t >= THRESHOLDS['temperature']['warning']:
            alerts.append({
                'alert_type': 'temperature',
                'message': f'🌡️ High temperature: {t:.1f}°C (warning at: {Config.TEMP_WARNING}°C)',
                'level': 'warning'
            })

    if h is not None:
        if h >= THRESHOLDS['humidity']['danger']:
            alerts.append({
                'alert_type': 'humidity',
                'message': f'💧 DANGEROUS humidity: {h:.1f}% (limit: {Config.HUM_DANGER}%)',
                'level': 'danger'
            })
        elif h >= THRESHOLDS['humidity']['warning']:
            alerts.append({
                'alert_type': 'humidity',
                'message': f'💧 High humidity: {h:.1f}% (warning at: {Config.HUM_WARNING}%)',
                'level': 'warning'
            })

    return alerts
