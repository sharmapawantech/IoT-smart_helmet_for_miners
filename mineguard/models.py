from extensions import db, login_manager
from flask_login import UserMixin
from datetime import datetime


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80),  unique=True, nullable=False)
    password   = db.Column(db.String(200), nullable=False)
    role       = db.Column(db.String(20),  default='viewer')
    created_at = db.Column(db.DateTime,    default=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.username}>'


class SensorReading(db.Model):
    __tablename__ = 'sensor_readings'
    id            = db.Column(db.Integer, primary_key=True)
    timestamp     = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    temperature   = db.Column(db.Float, nullable=True)   # DHT22  — field2
    humidity      = db.Column(db.Float, nullable=True)   # DHT22  — field3
    methane       = db.Column(db.Float, nullable=True)   # MQ4    — field1
    fall_detected = db.Column(db.Boolean, default=False) # MPU6050 — field4
    danger_level  = db.Column(db.String(20), default='safe')  # safe/warning/danger

    def to_dict(self):
        return {
            'id':            self.id,
            'timestamp':     self.timestamp.isoformat(),
            'temperature':   self.temperature,
            'humidity':      self.humidity,
            'methane':       self.methane,
            'fall_detected': self.fall_detected,
            'danger_level':  self.danger_level,
        }


class Alert(db.Model):
    __tablename__ = 'alerts'
    id           = db.Column(db.Integer, primary_key=True)
    timestamp    = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    alert_type   = db.Column(db.String(50))   # fall / methane / temperature / humidity / safe_recovery
    message      = db.Column(db.String(300))
    level        = db.Column(db.String(20))   # warning / danger / safe
    acknowledged = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id':           self.id,
            'timestamp':    self.timestamp.isoformat(),
            'alert_type':   self.alert_type,
            'message':      self.message,
            'level':        self.level,
            'acknowledged': self.acknowledged,
        }


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
