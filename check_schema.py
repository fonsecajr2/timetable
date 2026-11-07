"""Shows which database file the app uses and whether it still needs migrate_v2.py.

Run from the project root:  python check_schema.py
"""
from sqlalchemy import inspect

from app import create_app
from app.extensions import db

app = create_app()
with app.app_context():
    insp = inspect(db.engine)
    print("Database file:", db.engine.url.database)

    missing = []
    if "group_id" not in {c["name"] for c in insp.get_columns("section")}:
        missing.append("section.group_id")
    if "user_id" not in {c["name"] for c in insp.get_columns("faculty")}:
        missing.append("faculty.user_id")

    if missing:
        print("NEEDS MIGRATION - missing columns:", ", ".join(missing))
        print("Stop the server, then run: python migrate_v2.py")
    else:
        print("Schema is up to date.")