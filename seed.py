"""Populate the database with demo data:  python seed.py"""
from app import create_app
from app.extensions import db
from app.models import Course, Faculty, Room, Section, TimeSlot, User

PERIOD_TIMES = [("09:00", "09:55"), ("10:00", "10:55"), ("11:15", "12:10"),
                ("12:15", "13:10"), ("14:00", "14:55"), ("15:00", "15:55")]


def seed():
    for d in range(5):
        for p, (s, e) in enumerate(PERIOD_TIMES, start=1):
            db.session.add(TimeSlot(day=d, period=p, start=s, end=e))
    for name, cap, rt in [("R101", 70, "lecture"), ("R102", 60, "lecture"),
                          ("R201", 40, "lecture"), ("LAB1", 35, "lab"), ("LAB2", 35, "lab")]:
        db.session.add(Room(name=name, capacity=cap, room_type=rt))
    courses = [Course(code="CS101", name="Programming", weekly_sessions=3),
               Course(code="MA101", name="Calculus", weekly_sessions=3),
               Course(code="PH101", name="Physics", weekly_sessions=3),
               Course(code="CS101L", name="Programming Lab", weekly_sessions=1, room_type="lab")]
    facs = [Faculty(name="Dr. Rao"), Faculty(name="Dr. Mehta"), Faculty(name="Dr. Singh")]
    db.session.add_all(courses + facs)
    db.session.flush()
    c = {x.code: x for x in courses}
    for grp, size in [("CSE-1A", 55), ("CSE-1B", 50)]:
        db.session.add_all([
            Section(course_id=c["CS101"].id, faculty_id=facs[0].id, group_name=grp, strength=size),
            Section(course_id=c["MA101"].id, faculty_id=facs[1].id, group_name=grp, strength=size),
            Section(course_id=c["PH101"].id, faculty_id=facs[2].id, group_name=grp, strength=size),
            Section(course_id=c["CS101L"].id, faculty_id=facs[0].id, group_name=grp, strength=30)])
    for name, role in [("admin", "admin"), ("faculty", "faculty"), ("student", "student")]:
        u = User(username=name, role=role)
        u.set_password(name + "123")
        db.session.add(u)
    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
        seed()
        print("Seeded. Logins: admin/admin123, faculty/faculty123, student/student123")
