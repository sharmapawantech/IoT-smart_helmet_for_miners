import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ── ThingSpeak ───────────────────────────────────────────────────────────
    # Get these from: thingspeak.com → your channel → API Keys tab
    THINGSPEAK_API_KEY    = os.environ.get('THINGSPEAK_API_KEY',    'YOUR_READ_API_KEY')
    THINGSPEAK_CHANNEL_ID = os.environ.get('THINGSPEAK_CHANNEL_ID', 'YOUR_CHANNEL_ID')

    # ── ThingSpeak Field Mapping ─────────────────────────────────────────────
    # Based on your channel screenshot:
    #   Field 1 → gas      (MQ4  — methane ppm)
    #   Field 2 → temp     (DHT22 — temperature °C)
    #   Field 3 → hum      (DHT22 — humidity %)
    #   Field 4 → Accel    (MPU6050 — fall detection, 0 or 1)
    FIELD_METHANE     = 'field1'
    FIELD_TEMPERATURE = 'field2'
    FIELD_HUMIDITY    = 'field3'
    FIELD_ACCEL       = 'field4'   # 1 = fall detected, 0 = normal

    # ── Sensor Thresholds ───────────────────────────────────────────────────
    TEMP_WARNING  = 42      # °C
    TEMP_DANGER   = 50      # °C
    HUM_WARNING   = 80      # %
    HUM_DANGER    = 95      # %
    GAS_WARNING   = 650     # ppm
    GAS_DANGER    = 800     # ppm

    # ── Dashboard Refresh (seconds) ─────────────────────────────────────────
    REFRESH_INTERVAL = 10

    # ── Email Alert Cooldown ─────────────────────────────────────────────────
    EMAIL_COOLDOWN_SECONDS = 600   # 10 minutes between repeated danger emails

    # ── Flask ────────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mineguard-secret-2024')
    SQLALCHEMY_DATABASE_URI    = 'sqlite:///mineguard.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
