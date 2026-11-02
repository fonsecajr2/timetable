from app.extensions import db
from app.models import Allocation, FacultyUnavailability, Section, TimeSlot
from app.scheduler import find_conflicts, generate_timetable


def test_generation_has_no_conflicts(app):
    res = generate_timetable(time_limit=10)
    assert res["status"] in ("OPTIMAL", "FEASIBLE")
    total = sum(s.course.weekly_sessions for s in Section.query.all())
    assert Allocation.query.count() == total
    assert find_conflicts(Allocation.query.all()) == []


def test_faculty_unavailability_respected(app):
    sec = Section.query.first()
    slot = TimeSlot.query.filter_by(day=0, period=1).first()
    db.session.add(FacultyUnavailability(faculty_id=sec.faculty_id, slot_id=slot.id))
    db.session.commit()
    generate_timetable(time_limit=10)
    unavail = [(sec.faculty_id, slot.id)]
    assert find_conflicts(Allocation.query.all(), unavail) == []
    assert not Allocation.query.filter_by(slot_id=slot.id).join(Section).filter(
        Section.faculty_id == sec.faculty_id).count()


def test_detects_manual_double_booking(app):
    generate_timetable(time_limit=10)
    a = Allocation.query.first()
    other = Allocation.query.filter(Allocation.id != a.id).first()
    other.room_id, other.slot_id = a.room_id, a.slot_id
    db.session.commit()
    kinds = {c["type"] for c in find_conflicts(Allocation.query.all())}
    assert "room_double_booked" in kinds


def test_locked_allocation_is_kept(app):
    generate_timetable(time_limit=10)
    a = Allocation.query.first()
    a.locked = True
    keep = (a.id, a.room_id, a.slot_id)
    db.session.commit()
    generate_timetable(time_limit=10)
    kept = db.session.get(Allocation, keep[0])
    assert kept is not None and (kept.room_id, kept.slot_id) == keep[1:]
    assert find_conflicts(Allocation.query.all()) == []
