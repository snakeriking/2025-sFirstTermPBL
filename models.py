# models.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Food(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.String(50))
    expiry_date = db.Column(db.Date, nullable=False)
    image_path = db.Column(db.String(200))

class Memo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)

class NotificationSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    days_before = db.Column(db.Integer, default=3)
