from extensions import db
from datetime import datetime


class StockMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("product.id"),
        nullable=False
    )

    quantity = db.Column(
        db.Integer,
        nullable=False
    )

    movement_type = db.Column(
        db.String(20),
        nullable=False
    )

    reference = db.Column(
        db.String(100),
        nullable=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    movement_date = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    product = db.relationship(
        "Product",
        backref="stock_movements"
    )

    user = db.relationship(
        "User",
        backref="stock_movements"
    )