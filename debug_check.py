"""Read-only integrity check for the timetable DB. Changes nothing.

Run from the project root:  python debug_check.py
Assumes app/__init__.py exposes create_app() (adjust the import if yours differs).
"""
from collections import Counter, defaultdict

from app import create_app
from app.extensions import db
from app.models import Allocation, Faculty, FacultyUnavailability, Section, TimeSlot
from app.scheduler.conflicts import find_conflicts

app = create_app()


def report(title, rows):
    print(f"\n[{'OK' if not rows else 'FAIL'}] {title}")
    for r in rows[:15]:
        print("   -", r)
    if len(rows) > 15:
        print(f"   ... and {len(rows) - 15} more")


with app.app_context():
    if db.engine.dialect.name == "sqlite":
        fk = db.session.execute(db.text("PRAGMA foreign_keys")).scalar()
        print(f"SQLite foreign_keys pragma = {fk} (0 means deletes can leave orphans)")

    allocs = Allocation.query.all()
    sections = Section.query.all()
    num_days = len({t.day for t in TimeSlot.query.all()})

    report("Allocations pointing at a missing section/room/slot",
           [f"allocation {a.id}" for a in allocs if not (a.section and a.room and a.slot)])
    report("Sections pointing at a missing course/faculty",
           [f"section {s.id}" for s in sections if not (s.course and s.faculty)])

    good = [a for a in allocs
            if a.section and a.room and a.slot and a.section.course and a.section.faculty]
    unavail = [(u.faculty_id, u.slot_id) for u in FacultyUnavailability.query.all()]
    report("Hard-constraint conflicts (find_conflicts)",
           [f"{c['type']}: {c['detail']}" for c in find_conflicts(good, unavail)])

    count = Counter(a.section_id for a in good)
    report("Sections with NO allocations (find_conflicts cannot see these)",
           [f"{s.course.code}/{s.group_name}" for s in sections
            if s.course and count[s.id] == 0])

    per_day = Counter((a.section_id, a.slot.day) for a in good)
    report("H8: section has more than one session on a day (find_conflicts does not check this)",
           [f"section {sid}, day {d}: {n} sessions"
            for (sid, d), n in per_day.items() if n > 1])

    report("Sections needing more sessions than there are days (impossible under H8)",
           [f"{s.course.code}/{s.group_name}: {s.course.weekly_sessions} sessions, {num_days} days"
            for s in sections if s.course and s.course.weekly_sessions > num_days])

    dup = Counter((s.course_id, s.group_name) for s in sections)
    report("Duplicate sections (same course + group)",
           [f"course {c}, group {g} x{n}" for (c, g), n in dup.items() if n > 1])

    similar = defaultdict(set)
    strengths = defaultdict(set)
    for s in sections:
        key = "".join(ch for ch in s.group_name.lower() if ch.isalnum())
        similar[key].add(s.group_name)
        strengths[s.group_name].add(s.strength)
    report("Group names that look like the same group (a typo silently breaks H4)",
           [sorted(v) for v in similar.values() if len(v) > 1])
    report("Same group with different strengths across sections",
           [f"{g}: {sorted(v)}" for g, v in strengths.items() if len(v) > 1])

    emails = Counter((f.email or "").strip().lower() for f in Faculty.query.all())
    report("Faculty with blank or duplicate email (needed later to link logins)",
           [f"{e or '(blank)'} x{n}" for e, n in emails.items() if e == "" or n > 1])