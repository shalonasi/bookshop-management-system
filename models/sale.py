from extensions import db
from datetime import datetime


class Sale(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    receipt_number = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    # Customer name or reference
    customer_reference = db.Column(
        db.String(150),
        nullable=False
    )

    total_amount = db.Column(
        db.Float,
        nullable=False
    )

    sale_date = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    user = db.relationship(
        "User",
        backref="sales"
    )

