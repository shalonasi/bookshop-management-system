from app import app
from extensions import db
from models.user import User
from werkzeug.security import generate_password_hash

with app.app_context():
    # Make sure the tables exist
    db.create_all()

    # Check whether admin already exists
    existing_admin = User.query.filter_by(username="admin").first()

    if existing_admin:
        print("Admin user already exists.")
    else:
        admin = User(
            username="admin",
            password=generate_password_hash("admin"),
            role="admin"
        )

        db.session.add(admin)
        db.session.commit()

        print("Admin account created successfully.")
        print("Username: admin")
        print("Password: admin")