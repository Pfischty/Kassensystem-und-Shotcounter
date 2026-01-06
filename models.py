from datetime import datetime

from extensions import db


class teamliste(db.Model):
    __tablename__ = "teamliste"

    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, unique=False, nullable=False)
    team = db.Column(db.String(150), unique=True, nullable=False)


class Order(db.Model):
    __tablename__ = "order"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    total = db.Column(db.Integer, nullable=False)


class OrderItem(db.Model):
    __tablename__ = "order_item"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)

    order = db.relationship("Order", backref=db.backref("items", lazy=True))


class DrinkSale(db.Model):
    """Aggregierte Stückzahlen pro Getränk und Bestellung"""

    __tablename__ = "drink_sale"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, default=0, nullable=False)

    order = db.relationship("Order", backref=db.backref("drink_sales", lazy=True))
