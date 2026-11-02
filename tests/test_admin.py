from app.models import Allocation, Course, Section, TimeSlot


def login(client, user="admin"):
    client.post("/login", data={"username": user, "password": user + "123"})


def test_full_flow_from_empty_via_ui(app):
    from app.extensions import db
    db.drop_all(); db.create_all()
    from app.models import User
    u = User(username="admin", role="admin"); u.set_password("admin123")
    db.session.add(u); db.session.commit()

    c = app.test_client(); login(c)
    c.post("/admin/slots/default")
    assert TimeSlot.query.count() == 30
    c.post("/admin/courses", data=dict(code="CS1", name="Intro", weekly_sessions=3, room_type="lecture"))
    c.post("/admin/faculty", data=dict(name="Dr A", email=""))
    c.post("/admin/rooms", data=dict(name="R1", capacity=60, room_type="lecture"))
    from app.models import Faculty
    cid, fid = Course.query.first().id, Faculty.query.first().id
    c.post("/admin/sections", data=dict(course_id=cid, faculty_id=fid, group_name="G1", strength=40))
    assert Section.query.count() == 1
    c.post("/generate")
    assert Allocation.query.count() == 3
    assert b"No conflicts found" in c.get("/conflicts").data


def test_validation_and_delete_guard(app):
    c = app.test_client(); login(c)
    c.post("/admin/courses", data=dict(code="X", name="Bad", weekly_sessions=9, room_type="lecture"))
    assert Course.query.filter_by(code="X").count() == 0       # max 5 sessions
    cid = Course.query.first().id
    c.post(f"/admin/courses/{cid}/delete")
    assert db_has_course(cid)                                   # still used by sections


def db_has_course(cid):
    from app.extensions import db
    return db.session.get(Course, cid) is not None


def test_non_admin_blocked(app):
    c = app.test_client(); login(c, "student")
    assert c.get("/admin/courses").status_code == 403
