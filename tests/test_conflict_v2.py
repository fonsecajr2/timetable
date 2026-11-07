"""Pure unit tests (no database): model objects are built in memory."""
from types import SimpleNamespace

from app.models import Allocation, Course, Faculty, Room, Section, StudentGroup, TimeSlot
from app.scheduler.conflicts import check_move, find_conflicts


def room(id, name, capacity=60, room_type="lecture"):
    return Room(id=id, name=name, capacity=capacity, room_type=room_type)


def slot(id, day, period):
    return TimeSlot(id=id, day=day, period=period, start="09:00", end="09:55")


def section(id, code, faculty, group, weekly=1, room_type="lecture"):
    course = Course(id=id, code=code, name=code, weekly_sessions=weekly, room_type=room_type)
    return Section(id=id, course=course, course_id=id, faculty=faculty, faculty_id=faculty.id,
                   group=group, group_id=group.id)


def alloc(id, sec, rm, sl):
    return Allocation(id=id, section=sec, section_id=sec.id, room=rm, room_id=rm.id,
                      slot=sl, slot_id=sl.id)


def world():
    return SimpleNamespace(
        f1=Faculty(id=1, name="Dr. Rao"), f2=Faculty(id=2, name="Dr. Iyer"),
        g1=StudentGroup(id=1, name="CSE-1A", strength=40),
        g2=StudentGroup(id=2, name="CSE-1B", strength=40),
        a101=room(1, "A101"), a102=room(2, "A102"), small=room(3, "A103", capacity=20),
        lab=room(4, "L1", room_type="lab"),
        mon1=slot(1, 0, 1), mon2=slot(2, 0, 2), tue1=slot(3, 1, 1), tue2=slot(4, 1, 2))


def types(conflicts):
    return {c["type"] for c in conflicts}


# ---------------------------------------------------------------- find_conflicts
def test_clean_schedule_has_no_conflicts():
    w = world()
    s1, s2 = section(1, "CS101", w.f1, w.g1), section(2, "MA101", w.f2, w.g2)
    assert find_conflicts([alloc(1, s1, w.a101, w.mon1), alloc(2, s2, w.a101, w.mon2)]) == []


def test_unscheduled_section_is_reported_only_when_sections_given():
    w = world()
    s1 = section(1, "CS101", w.f1, w.g1, weekly=3)
    assert find_conflicts([]) == []
    found = find_conflicts([], sections=[s1])
    assert [c["type"] for c in found] == ["session_count"]
    assert "CS101/CSE-1A has 0 of 3 sessions" in found[0]["detail"]


def test_two_sessions_same_day_violate_h8():
    w = world()
    s1 = section(1, "CS101", w.f1, w.g1, weekly=2)
    found = find_conflicts([alloc(1, s1, w.a101, w.mon1), alloc(2, s1, w.a101, w.mon2)])
    assert "section_same_day" in types(found)


def test_room_double_booking_message_is_readable():
    w = world()
    s1, s2 = section(1, "CS101", w.f1, w.g1), section(2, "MA101", w.f2, w.g2)
    found = [c for c in find_conflicts([alloc(1, s1, w.a101, w.mon1), alloc(2, s2, w.a101, w.mon1)])
             if c["type"] == "room_double_booked"]
    assert len(found) == 1
    detail = found[0]["detail"]
    assert "A101" in detail and "CS101/CSE-1A" in detail and "MA101/CSE-1B" in detail
    assert sorted(found[0]["allocation_ids"]) == [1, 2]


def test_faculty_and_group_double_booking():
    w = world()
    s1 = section(1, "CS101", w.f1, w.g1)
    s2 = section(2, "MA101", w.f1, w.g1)  # same teacher AND same group
    found = find_conflicts([alloc(1, s1, w.a101, w.mon1), alloc(2, s2, w.a102, w.mon1)])
    assert {"faculty_double_booked", "group_double_booked"} <= types(found)


def test_capacity_type_and_unavailability():
    w = world()
    s1 = section(1, "CS101", w.f1, w.g1)
    assert "capacity" in types(find_conflicts([alloc(1, s1, w.small, w.mon1)]))
    assert "room_type" in types(find_conflicts([alloc(1, s1, w.lab, w.mon1)]))
    assert "faculty_unavailable" in types(
        find_conflicts([alloc(1, s1, w.a101, w.mon1)], unavailability=[(1, w.mon1.id)]))


# -------------------------------------------------------------------- check_move
def test_move_to_a_free_room_and_slot_is_allowed():
    w = world()
    s1 = section(1, "CS101", w.f1, w.g1)
    a = alloc(1, s1, w.a101, w.mon1)
    assert check_move(a, w.a102, w.tue1, [a]) == []


def test_move_ignores_the_allocation_itself():
    w = world()
    s1 = section(1, "CS101", w.f1, w.g1)
    a = alloc(1, s1, w.a101, w.mon1)
    assert check_move(a, w.a101, w.mon1, [a]) == []   # stay where it is
    assert check_move(a, w.a102, w.mon1, [a]) == []   # same slot, other room
    assert check_move(a, w.a101, w.mon2, [a]) == []   # same day, other slot (its own day)


def test_move_rejected_when_room_taken():
    w = world()
    s1, s2 = section(1, "CS101", w.f1, w.g1), section(2, "MA101", w.f2, w.g2)
    a, b = alloc(1, s1, w.a101, w.mon1), alloc(2, s2, w.a102, w.mon2)
    reasons = check_move(a, w.a102, w.mon2, [a, b])
    assert any("A102 is already used by MA101/CSE-1B" in r for r in reasons)


def test_move_rejected_when_teacher_or_group_busy():
    w = world()
    s1 = section(1, "CS101", w.f1, w.g1)
    same_teacher = section(2, "PH101", w.f1, w.g2)
    same_group = section(3, "MA101", w.f2, w.g1)
    a = alloc(1, s1, w.a101, w.mon1)
    t = alloc(2, same_teacher, w.a102, w.mon2)
    g = alloc(3, same_group, w.a102, w.tue1)
    assert any("Dr. Rao already teaches PH101" in r for r in check_move(a, w.a101, w.mon2, [a, t]))
    assert any("CSE-1A already has MA101" in r for r in check_move(a, w.a101, w.tue1, [a, g]))


def test_move_rejected_when_section_already_has_a_class_that_day():
    w = world()
    s1 = section(1, "CS101", w.f1, w.g1, weekly=2)
    a, b = alloc(1, s1, w.a101, w.mon1), alloc(2, s1, w.a101, w.tue1)
    reasons = check_move(a, w.a102, w.tue2, [a, b])
    assert any("already has a class on Tue" in r for r in reasons)


def test_move_rejected_for_unavailability_capacity_and_room_type():
    w = world()
    s1 = section(1, "CS101", w.f1, w.g1)
    a = alloc(1, s1, w.a101, w.mon1)
    assert any("unavailable" in r for r in
               check_move(a, w.a102, w.tue1, [a], unavailability=[(1, w.tue1.id)]))
    assert any("seats 20" in r for r in check_move(a, w.small, w.tue1, [a]))
    assert any("needs a lecture room" in r for r in check_move(a, w.lab, w.tue1, [a]))