"""Create an empty database with only login users (no demo data):  python create_admin.py"""
from app import create_app
from app.extensions import db
from app.models import User

app = create_app()
with app.app_context():
    db.drop_all()
    db.create_all()
    for name, role in [("admin", "admin"), ("faculty", "faculty"), ("student", "student")]:
        u = User(username=name, role=role)
        u.set_password(name + "123")
        db.session.add(u)
    db.session.commit()
    print("Empty database created. Logins: admin/admin123, faculty/faculty123, student/student123")
