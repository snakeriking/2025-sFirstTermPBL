# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

db = SQLAlchemy()

food_tags = db.Table('food_tags',
    db.Column('food_id', db.Integer, db.ForeignKey('food.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class Food(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.String(50))
    expiry_date = db.Column(db.Date, nullable=False)
    image_path = db.Column(db.String(200))
    tags = db.relationship('Tag', secondary=food_tags, backref=db.backref('foods', lazy='dynamic'))

class Memo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)

class NotificationSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    days_before = db.Column(db.Integer, default=3)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    
class RecipeLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    ingredients = db.Column(db.Text)       # JSON で保持
    recipes_json = db.Column(db.Text)
