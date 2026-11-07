"""Explains why the timetable / room / "my timetable" views may look empty.

Run from the project root:  python check_data.py
"""
from app import create_app
from app.models import (Allocation, Faculty, Room, Section, Student, StudentGroup, TimeSlot,
                        User)

with create_app().app_context():
    total = Allocation.query.count()
    published = Allocation.query.filter_by(published=True).count()
    print(f"Rooms {Room.query.count()}, slots {TimeSlot.query.count()}, "
          f"groups {StudentGroup.query.count()}, sections {Section.query.count()}")
    print(f"Allocations: {total} total, {published} published, "
          f"{Allocation.query.filter_by(locked=True).count()} locked")
    if total == 0:
        print("-> Nothing is scheduled yet: press Generate as admin.")
    elif published == 0:
        print("-> Nothing is published: teachers and students see empty timetables "
              "until admin presses Publish.")

    fac_users = {f.user_id for f in Faculty.query.all() if f.user_id}
    stu_users = {s.user_id for s in Student.query.all() if s.user_id}
    print(f"\nFaculty records: {Faculty.query.count()} ({len(fac_users)} with a login)")
    print(f"Student records: {Student.query.count()} ({len(stu_users)} with a login)")
    for u in User.query.order_by(User.role, User.username):
        linked = {"faculty": u.id in fac_users, "student": u.id in stu_users, "admin": True}[u.role]
        print(f"  login '{u.username}' ({u.role}): "
              + ("OK" if linked else "NOT LINKED to any faculty/student record -> its views are empty"))