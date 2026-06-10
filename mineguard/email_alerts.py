"""
MineGuard — Email Alert System

Rules:
  1. When threshold is crossed → send email immediately
  2. If still in danger after 10 minutes → send again (repeat every 10 min)
  3. When values return to SAFE after being in danger → send ONE "Situation Under Control" email
  4. Uses Gmail free SMTP — no paid API needed

SETUP: Fill in SECTION A below only.
"""

import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from config import Config


# ════════════════════════════════════════════════════════════════
#  SECTION A — ✏️ YOUR EMAIL SETTINGS (edit only this section)
# ════════════════════════════════════════════════════════════════

SENDER_EMAIL    = "SENDER@gmail.com"         # Gmail that SENDS alerts
SENDER_PASSWORD = "uygp vipl evpu zzxw"          # Gmail App Password (NOT normal password)
RECEIVER_EMAILS = [
    "RECEIVER@gmail.com",                # Add all recipients here
    "receiver2@gmail.com",
]

# ════════════════════════════════════════════════════════════════
#  Internal state tracking — DO NOT EDIT
# ══════════════════════════════════════════

_state = {
    # Tracks last email sent time per alert_type
    # { 'methane': 1712345678.0, 'temperature': ... }
    'last_sent': {},

    # Tracks whether we were previously in danger (for safe-recovery detection)
    # { 'methane': True, 'temperature': False, ... }
    'was_danger': {},
}

EMAIL_COOLDOWN = Config.EMAIL_COOLDOWN_SECONDS   # 600 seconds = 10 minutes


# ════════════════════════════════════════════════════════════════
#  HTML Email builder
# ════════════════════════════════════════════════════════════════

def _build_html(alert_type: str, level: str, message: str, sensor_data: dict) -> str:
    color_map = {
        'danger':   '#e74c3c',
        'warning':  '#f39c12',
        'safe':     '#27ae60',
    }
    header_color = color_map.get(level, '#7f8c8d')
    now = datetime.now().strftime("%d %b %Y, %I:%M:%S %p")

    icon_map = {
        'fall':          '🤸',
        'methane':       '💨',
        'temperature':   '🌡️',
        'humidity':      '💧',
        'safe_recovery': '✅',
    }
    icon = icon_map.get(alert_type, '⚠️')

    t    = sensor_data.get('temperature')
    h    = sensor_data.get('humidity')
    m    = sensor_data.get('methane')
    fall = sensor_data.get('fall_detected', False)

    def fmt(v, unit=''):
        return f"{v:.2f}{unit}" if v is not None else 'N/A'

    level_label = level.upper()
    fall_color  = '#e74c3c' if fall else '#27ae60'
    fall_text   = '⚠️ YES — FALL DETECTED' if fall else '✓ NO FALL'

    gas_color   = '#e74c3c' if (m is not None and m >= Config.GAS_DANGER) else \
                  '#f39c12' if (m is not None and m >= Config.GAS_WARNING) else '#27ae60'
    temp_color  = '#e74c3c' if (t is not None and t >= Config.TEMP_DANGER) else \
                  '#f39c12' if (t is not None and t >= Config.TEMP_WARNING) else '#27ae60'
    hum_color   = '#e74c3c' if (h is not None and h >= Config.HUM_DANGER) else \
                  '#f39c12' if (h is not None and h >= Config.HUM_WARNING) else '#27ae60'

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"/>
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#f0ede6;margin:0;padding:24px}}
  .wrap{{max-width:580px;margin:0 auto;background:#fff;border-radius:14px;
         overflow:hidden;box-shadow:0 6px 28px rgba(0,0,0,.12)}}
  .top{{background:#1a1a2e;color:#fff;padding:20px 28px;display:flex;align-items:center;gap:12px}}
  .top h1{{margin:0;font-size:1.15rem;font-weight:700}}
  .top p{{margin:3px 0 0;font-size:.78rem;opacity:.5}}
  .band{{background:{header_color};color:#fff;padding:20px 28px}}
  .band .ico{{font-size:2.2rem;margin-bottom:6px}}
  .band h2{{margin:0 0 4px;font-size:1.2rem;font-weight:800}}
  .band p{{margin:0;font-size:.9rem;opacity:.9;line-height:1.5}}
  .body{{padding:24px 28px}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}}
  .cell{{background:#f7f5f0;border-radius:10px;padding:14px 16px;border-left:4px solid #ddd}}
  .cell.red{{border-left-color:#e74c3c}} .cell.amber{{border-left-color:#f39c12}} .cell.green{{border-left-color:#27ae60}}
  .lbl{{font-size:.68rem;font-weight:800;text-transform:uppercase;letter-spacing:.07em;color:#999;margin-bottom:5px}}
  .val{{font-size:1.1rem;font-weight:700;font-family:'Courier New',monospace;color:#1c1c1c}}
  .thresholds{{margin-top:16px;background:#f7f5f0;border-radius:10px;padding:14px 16px}}
  .thresholds p{{margin:0 0 6px;font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#999}}
  .thresholds table{{width:100%;font-size:.8rem;border-collapse:collapse}}
  .thresholds td{{padding:3px 8px 3px 0;color:#555}}
  .thresholds td:last-child{{font-weight:700;color:#1c1c1c;text-align:right}}
  .note{{margin-top:16px;background:#fff8e1;border-left:4px solid #f39c12;
         border-radius:0 8px 8px 0;padding:12px 16px;font-size:.82rem;color:#7d5700;line-height:1.5}}
  .footer{{background:#f0ede6;padding:14px 28px;text-align:center;
           font-size:.72rem;color:#bbb;border-top:1px solid #e8e4dc}}
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div>
      <h1>⛏️ S.A.F.E. MINER Safety System</h1>
      <p>Mining Helmet IoT Monitor — {now}</p>
    </div>
  </div>
  <div class="band">
    <div class="ico">{icon}</div>
    <h2>{level_label}: {alert_type.replace('_',' ').title()}</h2>
    <p>{message}</p>
  </div>
  <div class="body">
    <p style="margin:0 0 4px;font-size:.78rem;font-weight:800;text-transform:uppercase;letter-spacing:.07em;color:#aaa">
      LIVE SENSOR READINGS AT TIME OF ALERT
    </p>
    <div class="grid">
      <div class="cell {'red' if temp_color=='#e74c3c' else 'amber' if temp_color=='#f39c12' else 'green'}">
        <div class="lbl">🌡️ Temperature</div>
        <div class="val" style="color:{temp_color}">{fmt(t,' °C')}</div>
      </div>
      <div class="cell {'red' if hum_color=='#e74c3c' else 'amber' if hum_color=='#f39c12' else 'green'}">
        <div class="lbl">💧 Humidity</div>
        <div class="val" style="color:{hum_color}">{fmt(h,' %')}</div>
      </div>
      <div class="cell {'red' if gas_color=='#e74c3c' else 'amber' if gas_color=='#f39c12' else 'green'}">
        <div class="lbl">💨 Methane (MQ4)</div>
        <div class="val" style="color:{gas_color}">{fmt(m,' ppm')}</div>
      </div>
      <div class="cell {'red' if fall else 'green'}">
        <div class="lbl">🤸 Fall Detection</div>
        <div class="val" style="color:{fall_color};font-size:.85rem">{fall_text}</div>
      </div>
    </div>
    <div class="thresholds">
      <p>Configured Thresholds</p>
      <table>
        <tr><td>Temperature Warning</td><td>≥ {Config.TEMP_WARNING}°C</td></tr>
        <tr><td>Temperature Danger</td><td>≥ {Config.TEMP_DANGER}°C</td></tr>
        <tr><td>Humidity Warning</td><td>≥ {Config.HUM_WARNING}%</td></tr>
        <tr><td>Methane Warning</td><td>≥ {Config.GAS_WARNING} ppm</td></tr>
        <tr><td>Methane Danger</td><td>≥ {Config.GAS_DANGER} ppm</td></tr>
      </table>
    </div>
    <div class="note">
      ⚡ <strong>Action Required:</strong> Please check on the miner immediately.
      If this alert continues, another notification will be sent in 10 minutes.
    </div>
  </div>
  <div class="footer">Sent automatically by S.A.F.E. MINER IoT Safety System · Do not reply</div>
</div>
</body></html>"""


# ════════════════════════════════════════════════════════════════
#  Core send function
# ════════════════════════════════════════════════════════════════

def _send_email(subject: str, html_body: str) -> bool:
    """Low-level: send one HTML email. Returns True on success."""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f"S.A.F.E. MINER Alerts <{SENDER_EMAIL}>"
        msg['To']      = ', '.join(RECEIVER_EMAILS)
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())

        print(f"[EMAIL ✓] Sent: {subject}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("[EMAIL ✗] Authentication failed — check SENDER_EMAIL and SENDER_PASSWORD.")
        print("          Use a Gmail App Password, NOT your normal Gmail password.")
        return False
    except smtplib.SMTPException as e:
        print(f"[EMAIL ✗] SMTP error: {e}")
        return False
    except Exception as e:
        print(f"[EMAIL ✗] Unexpected error: {e}")
        return False


def send_alert_email(alert_type: str, level: str, message: str, sensor_data: dict) -> bool:
    """Build subject and send one alert email."""
    subject_map = {
        'fall':          'FALL DETECTED — Miner Down!',
        'methane':       'Methane Gas Alert',
        'temperature':   'High Temperature Alert',
        'humidity':      'High Humidity Alert',
        'safe_recovery': '✅ Situation Under Control',
    }
    base    = subject_map.get(alert_type, f"Alert: {alert_type.title()}")
    prefix  = '🔴 DANGER' if level == 'danger' else '🟡 WARNING' if level == 'warning' else '✅ SAFE'
    subject = f"{prefix} — {base} | S.A.F.E. MINER"
    html    = _build_html(alert_type, level, message, sensor_data)
    return _send_email(subject, html)


# ════════════════════════════════════════════════════════════════
#  Main controller — called from routes/api.py every 10 seconds
# ════════════════════════════════════════════════════════════════

def process_alerts(alert_list: list, sensor_data: dict) -> None:
    """
    Smart alert dispatcher with:
      - Immediate email on first threshold breach
      - Repeat email every 10 minutes while danger persists
      - One "Situation Under Control" email when values return to safe
    """
    now = time.time()

    # Build set of currently active alert types
    active_types = {a['alert_type'] for a in alert_list}

    # ── Send alerts for active threshold breaches ──
    for alert in alert_list:
        atype   = alert['alert_type']
        level   = alert['level']
        message = alert['message']

        last_sent = _state['last_sent'].get(atype, 0)
        elapsed   = now - last_sent

        if elapsed >= EMAIL_COOLDOWN:
            success = send_alert_email(atype, level, message, sensor_data)
            if success:
                _state['last_sent'][atype]  = now
                _state['was_danger'][atype] = True
        else:
            remaining = int(EMAIL_COOLDOWN - elapsed)
            mins = remaining // 60
            secs = remaining % 60
            print(f"[EMAIL] '{atype}' cooldown: {mins}m {secs}s remaining")

    # ── Detect safe recovery ──
    # If we were previously sending danger emails for a type,
    # and that type is no longer in the active alerts → send "safe" email once
    for atype, was_danger in list(_state['was_danger'].items()):
        if was_danger and atype not in active_types:
            recovery_msg = (
                f"✅ Sensor '{atype.replace('_',' ').title()}' has returned to safe levels. "
                f"No further danger detected."
            )
            print(f"[EMAIL] Safe recovery detected for '{atype}' — sending control email")
            success = send_alert_email('safe_recovery', 'safe', recovery_msg, sensor_data)
            if success:
                _state['was_danger'][atype] = False   # Reset — don't send again until next breach
                _state['last_sent'].pop(atype, None)  # Reset cooldown for next potential breach


# ════════════════════════════════════════════════════════════════
#  Test mode — run: python email_alerts.py
# ════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print('=' * 58)
    print('  S.A.F.E. MINER — Email System Test')
    print('=' * 58)
    print(f"  Sender   : {SENDER_EMAIL}")
    print(f"  Receivers: {RECEIVER_EMAILS}")
    print()
    print('  Sending test DANGER email...')

    test_data = {
        'temperature':   47.3,
        'humidity':      88.5,
        'methane':       650.0,
        'fall_detected': True,
    }
    ok = send_alert_email(
        alert_type  = 'fall',
        level       = 'danger',
        message     = '⚠️ TEST: This is a test alert from S.A.F.E. MINER email setup.',
        sensor_data = test_data,
    )
    print()
    print('  ✅ SUCCESS — Check your inbox!' if ok else '  ❌ FAILED — Fix error above.')
    print('=' * 58)
