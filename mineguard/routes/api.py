import csv
import io
from flask import Blueprint, jsonify, request, make_response
from flask_login import login_required
from extensions import db
from models import SensorReading, Alert
from thingspeak import fetch_latest, parse_feed, generate_alerts
from email_alerts import process_alerts
from config import Config
from datetime import datetime

api_bp = Blueprint('api', __name__)


# ── Poll ThingSpeak every 10 seconds ────────────────────────────────────────

@api_bp.route('/poll', methods=['POST'])
@login_required
def poll():
    """
    Called by the browser every 10 seconds.
    1. Fetch latest feed from ThingSpeak
    2. Parse sensor values (correct field mapping)
    3. Store new reading in DB (skip if duplicate timestamp)
    4. Generate alerts if thresholds crossed
    5. Dispatch emails (10 min cooldown + safe recovery)
    6. Return parsed data as JSON to the browser
    """
    feed = fetch_latest(Config.THINGSPEAK_CHANNEL_ID, Config.THINGSPEAK_API_KEY)
    if not feed:
        return jsonify({'error': 'Failed to reach ThingSpeak'}), 502

    parsed = parse_feed(feed)

    # Parse timestamp from ThingSpeak (avoid duplicate DB rows)
    ts_str = parsed.get('created_at', '')
    try:
        ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        ts = datetime.utcnow()

    existing = SensorReading.query.filter_by(timestamp=ts).first()
    if not existing:
        reading = SensorReading(
            timestamp     = ts,
            temperature   = parsed['temperature'],
            humidity      = parsed['humidity'],
            methane       = parsed['methane'],
            fall_detected = parsed['fall_detected'],
            danger_level  = parsed['danger_level'],
        )
        db.session.add(reading)

        alert_list = generate_alerts(parsed)
        for a in alert_list:
            db.session.add(Alert(
                alert_type = a['alert_type'],
                message    = a['message'],
                level      = a['level'],
            ))

        db.session.commit()

        # Smart email dispatch (10 min cooldown + safe recovery notification)
        process_alerts(alert_list, parsed)

    return jsonify(parsed)


# ── Latest reading from DB ──────────────────────────────────────────────────

@api_bp.route('/latest')
@login_required
def latest():
    reading = SensorReading.query.order_by(SensorReading.timestamp.desc()).first()
    if not reading:
        return jsonify({'error': 'No data yet'}), 404
    return jsonify(reading.to_dict())


# ── History for charts ──────────────────────────────────────────────────────

@api_bp.route('/history')
@login_required
def history():
    limit = min(int(request.args.get('limit', 50)), 500)
    readings = (SensorReading.query
                .order_by(SensorReading.timestamp.desc())
                .limit(limit).all())
    readings.reverse()
    return jsonify([r.to_dict() for r in readings])


# ── Alerts list ─────────────────────────────────────────────────────────────

@api_bp.route('/alerts')
@login_required
def get_alerts():
    limit = min(int(request.args.get('limit', 30)), 300)
    alerts = (Alert.query
              .order_by(Alert.timestamp.desc())
              .limit(limit).all())
    return jsonify([a.to_dict() for a in alerts])


@api_bp.route('/alerts/<int:alert_id>/acknowledge', methods=['POST'])
@login_required
def acknowledge_alert(alert_id):
    alert = Alert.query.get_or_404(alert_id)
    alert.acknowledged = True
    db.session.commit()
    return jsonify({'success': True})


# ── Stats for pie chart ─────────────────────────────────────────────────────

@api_bp.route('/stats')
@login_required
def stats():
    total   = SensorReading.query.count()
    safe    = SensorReading.query.filter_by(danger_level='safe').count()
    warning = SensorReading.query.filter_by(danger_level='warning').count()
    danger  = SensorReading.query.filter_by(danger_level='danger').count()
    falls   = SensorReading.query.filter_by(fall_detected=True).count()
    return jsonify({
        'total': total, 'safe': safe,
        'warning': warning, 'danger': danger, 'falls': falls
    })


# ── CSV Export ──────────────────────────────────────────────────────────────

@api_bp.route('/export/csv')
@login_required
def export_csv():
    readings = SensorReading.query.order_by(SensorReading.timestamp.asc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Timestamp', 'Temperature (°C)', 'Humidity (%)',
        'Methane (ppm)', 'Fall Detected', 'Danger Level'
    ])
    for r in readings:
        writer.writerow([
            r.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            r.temperature, r.humidity, r.methane,
            'Yes' if r.fall_detected else 'No',
            r.danger_level
        ])
    output.seek(0)
    resp = make_response(output.getvalue())
    resp.headers['Content-Disposition'] = 'attachment; filename=_data.csv'
    resp.headers['Content-Type'] = 'text/csv'
    return resp
