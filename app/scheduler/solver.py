"""Automatic generation with OR-Tools CP-SAT.

Hard constraints:
  H1 every session is placed exactly once
  H2 a room hosts at most one session per slot
  H3 a faculty member teaches at most one session per slot
  H4 a student group attends at most one session per slot
  H5 room capacity >= section strength
  H6 room type matches course type (lecture / lab)
  H7 faculty unavailable slots are respected
  H8 a section has at most one session per day
Objective: minimise wasted seats (capacity - strength).
Manual adjustments: allocations with locked=True are kept and treated as fixed.
"""
from ortools.sat.python import cp_model

from ..extensions import db
from ..models import Allocation, FacultyUnavailability, Room, Section, TimeSlot


def generate_timetable(time_limit=30, keep_locked=True):
    sections = Section.query.all()
    rooms = Room.query.all()
    slots = TimeSlot.query.all()
    blocked = {(u.faculty_id, u.slot_id) for u in FacultyUnavailability.query.all()}

    locked = Allocation.query.filter_by(locked=True).all() if keep_locked else []
    if keep_locked:
        Allocation.query.filter_by(locked=False).delete()
    else:
        Allocation.query.delete()

    taken_room = {(a.room_id, a.slot_id) for a in locked}
    taken_fac = {(a.section.faculty_id, a.slot_id) for a in locked}
    taken_grp = {(a.section.group_name, a.slot_id) for a in locked}
    locked_days = {(a.section_id, a.slot.day) for a in locked}
    locked_count = {}
    for a in locked:
        locked_count[a.section_id] = locked_count.get(a.section_id, 0) + 1

    model = cp_model.CpModel()
    x = {}  # (section_id, session_idx, room_id, slot_id) -> BoolVar
    sessions = []
    for sec in sections:
        need = sec.course.weekly_sessions - locked_count.get(sec.id, 0)
        for k in range(max(need, 0)):
            sessions.append((sec, k))

    for sec, k in sessions:
        options = []
        for r in rooms:
            if r.capacity < sec.strength or r.room_type != sec.course.room_type:
                continue  # H5, H6
            for t in slots:
                if ((sec.faculty_id, t.id) in blocked  # H7
                        or (r.id, t.id) in taken_room
                        or (sec.faculty_id, t.id) in taken_fac
                        or (sec.group_name, t.id) in taken_grp
                        or (sec.id, t.day) in locked_days):
                    continue
                v = model.NewBoolVar(f"x_{sec.id}_{k}_{r.id}_{t.id}")
                x[(sec.id, k, r.id, t.id)] = v
                options.append(v)
        if not options:
            db.session.rollback()
            return {"status": "INFEASIBLE", "allocations": 0,
                    "reason": f"No valid room/slot for {sec.course.code} {sec.group_name}"}
        model.AddExactlyOne(options)  # H1

    def group_by(keyfn):
        d = {}
        for (sid, k, rid, tid), v in x.items():
            d.setdefault(keyfn(sid, rid, tid), []).append(v)
        return d

    sec_by_id = {s.id: s for s in sections}
    slot_day = {t.id: t.day for t in slots}
    for vs in group_by(lambda s, r, t: (r, t)).values():
        model.AddAtMostOne(vs)  # H2
    for vs in group_by(lambda s, r, t: (sec_by_id[s].faculty_id, t)).values():
        model.AddAtMostOne(vs)  # H3
    for vs in group_by(lambda s, r, t: (sec_by_id[s].group_name, t)).values():
        model.AddAtMostOne(vs)  # H4
    for vs in group_by(lambda s, r, t: (s, slot_day[t])).values():
        model.AddAtMostOne(vs)  # H8

    room_cap = {r.id: r.capacity for r in rooms}
    model.Minimize(sum((room_cap[rid] - sec_by_id[sid].strength) * v
                       for (sid, k, rid, tid), v in x.items()))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = 8
    status = solver.Solve(model)
    name = solver.StatusName(status)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        db.session.rollback()
        return {"status": name, "allocations": 0}

    placed = 0
    for (sid, k, rid, tid), v in x.items():
        if solver.Value(v):
            db.session.add(Allocation(section_id=sid, room_id=rid, slot_id=tid))
            placed += 1
    db.session.commit()
    return {"status": name, "allocations": placed, "objective": solver.ObjectiveValue()}
