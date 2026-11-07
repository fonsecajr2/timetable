"""One-off: move an existing database to the v2 schema (student groups, student/faculty
login links, unique constraints). Your data is kept, ids included.

    python migrate_v2.py

A backup is written next to the database first (<db>.v1.bak). If anything fails,
the backup is restored automatically.
"""
import os
import shutil
import sys
from collections import defaultdict

from sqlalchemy import inspect, text

from app import create_app
from app.extensions import db
from app.models import (Allocation, Course, Faculty, FacultyUnavailability, Room, Section,
                        StudentGroup, TimeSlot, User)

OLD_TABLES = ["user", "course", "faculty", "room", "time_slot", "section",
              "faculty_unavailability", "allocation"]


def _read(table):
    return [dict(r) for r in db.session.execute(text(f'SELECT * FROM "{table}"')).mappings()]


def _clone(model, row):
    cols = {c.key for c in model.__table__.columns}
    return model(**{k: v for k, v in row.items() if k in cols})


def _load(old):
    for model, table in ((User, "user"), (Course, "course"), (Faculty, "faculty"),
                         (Room, "room"), (TimeSlot, "time_slot")):
        db.session.add_all([_clone(model, r) for r in old[table]])

    # One StudentGroup per distinct group_name. If sections disagree about its size,
    # keep the largest so room capacity is never under-estimated.
    strengths = defaultdict(set)
    for s in old["section"]:
        strengths[s["group_name"]].add(s["strength"])
    groups = {}
    for name in sorted(strengths):
        sizes = strengths[name]
        groups[name] = StudentGroup(name=name, strength=max(sizes))
        if len(sizes) > 1:
            print(f"  group {name}: sections disagreed {sorted(sizes)} -> using {max(sizes)}")
    db.session.add_all(groups.values())
    db.session.flush()

    for s in old["section"]:
        db.session.add(Section(id=s["id"], course_id=s["course_id"],
                               faculty_id=s["faculty_id"], group_id=groups[s["group_name"]].id))
    seen = set()
    for u in old["faculty_unavailability"]:
        key = (u["faculty_id"], u["slot_id"])
        if key not in seen:
            seen.add(key)
            db.session.add(_clone(FacultyUnavailability, u))
    db.session.flush()
    db.session.add_all([_clone(Allocation, r) for r in old["allocation"]])
    db.session.commit()
    return len(groups)


def main():
    app = create_app()
    with app.app_context():
        if db.engine.dialect.name != "sqlite":
            sys.exit("migrate_v2 only supports SQLite.")
        insp = inspect(db.engine)
        if not insp.has_table("section"):
            sys.exit("No 'section' table found. Is this the right database file?")
        section_cols = {c["name"] for c in insp.get_columns("section")}
        if "group_id" in section_cols:
            sys.exit("Database already has the v2 schema; nothing to do.")
        if "group_name" not in section_cols:
            sys.exit(f"Unrecognised 'section' table (columns: {sorted(section_cols)}).")
        # Note: new empty tables (student_group, student) may already exist because the
        # app calls create_all() on start-up; that is harmless, they are rebuilt below.
        path = db.engine.url.database
        if not path or not os.path.exists(path):
            sys.exit(f"Cannot find the database file ({path!r}).")

        backup = path + ".v1.bak"
        shutil.copy2(path, backup)
        print(f"Backup written to {backup}")

        old = {t: _read(t) for t in OLD_TABLES}
        db.session.close()
        try:
            db.drop_all()
            db.create_all()
            n_groups = _load(old)
        except Exception:
            db.session.rollback()
            db.engine.dispose()
            shutil.copy2(backup, path)
            print("Migration failed; the original database was restored.")
            raise

        print("Migrated:")
        for t in OLD_TABLES:
            print(f"  {t}: {len(old[t])} rows")
        print(f"  student_group: {n_groups} created from section group names")
        print("Next: check group names/sizes under Admin > Groups, and link logins.")


if __name__ == "__main__":
    main()