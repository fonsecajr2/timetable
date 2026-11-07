"""Conflict detection (whole schedule) and move validation (one class).

find_conflicts: used after generation and after manual edits.
check_move:     used when a teacher/admin wants to move ONE allocation to another room/slot.
"""
from collections import defaultdict

from ..models import DAYS


def _name(a):
    return f"{a.section.course.code}/{a.section.group_name}"


def find_conflicts(allocations, unavailability=(), sections=None):
    """Return a list of {type, detail, allocation_ids} for every hard-constraint violation.

    allocations: iterable of Allocation (needs .section, .room, .slot, .id)
    unavailability: iterable of (faculty_id, slot_id) pairs
    sections: optional iterable of ALL sections; when given, sections that have no
              allocation at all are reported too (otherwise they are invisible).
    """
    allocations = list(allocations)
    conflicts = []
    blocked = set(unavailability)

    by_room, by_faculty, by_group = defaultdict(list), defaultdict(list), defaultdict(list)
    by_section_day = defaultdict(list)
    for a in allocations:
        by_room[(a.room_id, a.slot_id)].append(a)
        by_faculty[(a.section.faculty_id, a.slot_id)].append(a)
        by_group[(a.section.group_name, a.slot_id)].append(a)
        by_section_day[(a.section_id, a.slot.day)].append(a)

        if a.room.capacity < a.section.strength:
            conflicts.append(_c("capacity", f"{a.room.name} seats {a.room.capacity}, "
                                f"{_name(a)} has {a.section.strength} students", [a.id]))
        if a.room.room_type != a.section.course.room_type:
            conflicts.append(_c("room_type", f"{a.section.course.code} needs a "
                                f"{a.section.course.room_type} room, got {a.room.name}", [a.id]))
        if (a.section.faculty_id, a.slot_id) in blocked:
            conflicts.append(_c("faculty_unavailable", f"{a.section.faculty.name} unavailable "
                                f"at {a.slot.label}", [a.id]))

    for kind, groups, who in (
            ("room_double_booked", by_room, lambda a: a.room.name),
            ("faculty_double_booked", by_faculty, lambda a: a.section.faculty.name),
            ("group_double_booked", by_group, lambda a: a.section.group_name)):
        for items in groups.values():
            if len(items) > 1:
                first = items[0]
                conflicts.append(_c(
                    kind,
                    f"{who(first)} has {len(items)} classes at {first.slot.label}: "
                    + ", ".join(_name(i) for i in items),
                    [i.id for i in items]))

    for items in by_section_day.values():  # H8: one session per section per day
        if len(items) > 1:
            conflicts.append(_c(
                "section_same_day",
                f"{_name(items[0])} has {len(items)} sessions on {DAYS[items[0].slot.day]}",
                [i.id for i in items]))

    per_section = defaultdict(int)
    for a in allocations:
        per_section[a.section_id] += 1
    to_check = {a.section_id: a.section for a in allocations}
    if sections is not None:
        to_check = {s.id: s for s in sections}
    for sid, sec in to_check.items():
        have = per_section.get(sid, 0)
        if have != sec.course.weekly_sessions:
            conflicts.append(_c("session_count", f"{sec.course.code}/{sec.group_name} has "
                                f"{have} of {sec.course.weekly_sessions} sessions", []))
    return conflicts


def check_move(alloc, room, slot, allocations, unavailability=()):
    """Why can't `alloc` be moved to (room, slot)? Returns a list of readable reasons.

    An empty list means the move breaks no hard constraint. The allocation being
    moved is ignored when checking clashes, so keeping its own room or slot is fine.
    """
    sec = alloc.section
    name = f"{sec.course.code}/{sec.group_name}"
    blocked = set(unavailability)
    reasons = []

    if room.capacity < sec.strength:
        reasons.append(f"{room.name} seats {room.capacity}, {name} has {sec.strength} students")
    if room.room_type != sec.course.room_type:
        reasons.append(f"{name} needs a {sec.course.room_type} room, "
                       f"{room.name} is a {room.room_type} room")
    if (sec.faculty_id, slot.id) in blocked:
        reasons.append(f"{sec.faculty.name} is unavailable at {slot.label}")

    for other in allocations:
        if other.id == alloc.id:
            continue
        if other.slot_id == slot.id:
            if other.room_id == room.id:
                reasons.append(f"{room.name} is already used by {_name(other)} at {slot.label}")
            if other.section.faculty_id == sec.faculty_id:
                reasons.append(f"{sec.faculty.name} already teaches {_name(other)} "
                               f"at {slot.label}")
            if other.section.group_name == sec.group_name:
                reasons.append(f"{sec.group_name} already has {_name(other)} at {slot.label}")
        elif other.section_id == sec.id and other.slot.day == slot.day:
            reasons.append(f"{name} already has a class on {DAYS[slot.day]}")
    return reasons


def _c(kind, detail, ids):
    return {"type": kind, "detail": detail, "allocation_ids": ids}