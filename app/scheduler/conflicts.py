"""Conflict detection: used after generation and after every manual edit."""
from collections import defaultdict


def find_conflicts(allocations, unavailability=()):
    """Return a list of {type, detail, allocation_ids} for every hard-constraint violation.

    allocations: iterable of Allocation (needs .section, .room, .slot, .id)
    unavailability: iterable of (faculty_id, slot_id) pairs
    """
    allocations = list(allocations)
    conflicts = []
    blocked = set(unavailability)

    by_room, by_faculty, by_group = defaultdict(list), defaultdict(list), defaultdict(list)
    for a in allocations:
        by_room[(a.room_id, a.slot_id)].append(a)
        by_faculty[(a.section.faculty_id, a.slot_id)].append(a)
        by_group[(a.section.group_name, a.slot_id)].append(a)

        if a.room.capacity < a.section.strength:
            conflicts.append(_c("capacity", f"{a.room.name} seats {a.room.capacity}, "
                                f"section has {a.section.strength}", [a.id]))
        if a.room.room_type != a.section.course.room_type:
            conflicts.append(_c("room_type", f"{a.section.course.code} needs a "
                                f"{a.section.course.room_type} room, got {a.room.name}", [a.id]))
        if (a.section.faculty_id, a.slot_id) in blocked:
            conflicts.append(_c("faculty_unavailable", f"{a.section.faculty.name} unavailable "
                                f"at {a.slot.label}", [a.id]))

    for name, groups in (("room_double_booked", by_room), ("faculty_double_booked", by_faculty),
                         ("group_double_booked", by_group)):
        for key, items in groups.items():
            if len(items) > 1:
                conflicts.append(_c(name, f"{len(items)} allocations share {key}",
                                    [i.id for i in items]))

    per_section = defaultdict(int)
    for a in allocations:
        per_section[a.section_id] += 1
    seen = {a.section_id: a.section for a in allocations}
    for sid, sec in seen.items():
        if per_section[sid] != sec.course.weekly_sessions:
            conflicts.append(_c("session_count", f"{sec.course.code}/{sec.group_name} has "
                                f"{per_section[sid]} of {sec.course.weekly_sessions} sessions", []))
    return conflicts


def _c(kind, detail, ids):
    return {"type": kind, "detail": detail, "allocation_ids": ids}
