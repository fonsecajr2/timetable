"""Admin setup screens: add / edit / delete courses, faculty, rooms, slots, sections, availability."""
import re

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import (DAYS, Allocation, Course, Faculty, FacultyUnavailability, Room,
                     Section, TimeSlot)
from .routes import role_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ROOM_TYPES = [("lecture", "Lecture"), ("lab", "Lab")]
DEFAULT_PERIODS = [("09:00", "09:55"), ("10:00", "10:55"), ("11:15", "12:10"),
                   ("12:15", "13:10"), ("14:00", "14:55"), ("15:00", "15:55")]


def _courses():
    return [(c.id, f"{c.code} - {c.name}") for c in Course.query.order_by(Course.code)]


def _faculty():
    return [(f.id, f.name) for f in Faculty.query.order_by(Faculty.name)]


def _slots():
    return [(t.id, t.label) for t in TimeSlot.query.order_by(TimeSlot.day, TimeSlot.period)]


def F(name, label, kind="text", choices=None, required=True, min=1, max=None):
    return dict(name=name, label=label, kind=kind, choices=choices,
                required=required, min=min, max=max)


ENTITIES = {
    "courses": dict(
        model=Course, title="Courses", order=Course.code,
        fields=[F("code", "Code (e.g. CS101)"), F("name", "Course name"),
                F("weekly_sessions", "Sessions per week", "int", max=5),
                F("room_type", "Room type", "select", ROOM_TYPES)],
        columns=[("Code", lambda o: o.code), ("Name", lambda o: o.name),
                 ("Sessions/week", lambda o: o.weekly_sessions),
                 ("Room type", lambda o: o.room_type)],
        deps=[(Section, "course_id")]),
    "faculty": dict(
        model=Faculty, title="Faculty", order=Faculty.name,
        fields=[F("name", "Name"), F("email", "Email", required=False)],
        columns=[("Name", lambda o: o.name), ("Email", lambda o: o.email or "")],
        deps=[(Section, "faculty_id"), (FacultyUnavailability, "faculty_id")]),
    "rooms": dict(
        model=Room, title="Rooms", order=Room.name,
        fields=[F("name", "Room name"), F("capacity", "Capacity", "int"),
                F("room_type", "Room type", "select", ROOM_TYPES)],
        columns=[("Room", lambda o: o.name), ("Capacity", lambda o: o.capacity),
                 ("Type", lambda o: o.room_type)],
        deps=[(Allocation, "room_id")]),
    "slots": dict(
        model=TimeSlot, title="Time slots", order=(TimeSlot.day, TimeSlot.period),
        fields=[F("day", "Day", "select_int", list(enumerate(DAYS))),
                F("period", "Period number", "int"),
                F("start", "Start (HH:MM)", "time"), F("end", "End (HH:MM)", "time")],
        columns=[("Day", lambda o: DAYS[o.day]), ("Period", lambda o: o.period),
                 ("Start", lambda o: o.start), ("End", lambda o: o.end)],
        deps=[(Allocation, "slot_id"), (FacultyUnavailability, "slot_id")]),
    "sections": dict(
        model=Section, title="Sections (class offerings)", order=Section.id,
        fields=[F("course_id", "Course", "select_int", _courses),
                F("faculty_id", "Faculty", "select_int", _faculty),
                F("group_name", "Student group (e.g. CSE-3A)"),
                F("strength", "Number of students", "int")],
        columns=[("Course", lambda o: f"{o.course.code} - {o.course.name}"),
                 ("Faculty", lambda o: o.faculty.name), ("Group", lambda o: o.group_name),
                 ("Students", lambda o: o.strength)],
        deps=[(Allocation, "section_id")]),
    "availability": dict(
        model=FacultyUnavailability, title="Faculty unavailability", order=FacultyUnavailability.id,
        fields=[F("faculty_id", "Faculty", "select_int", _faculty),
                F("slot_id", "Unavailable at", "select_int", _slots)],
        columns=[("Faculty", lambda o: db.session.get(Faculty, o.faculty_id).name),
                 ("Slot", lambda o: db.session.get(TimeSlot, o.slot_id).label)],
        deps=[]),
}


def _entity(name):
    ent = ENTITIES.get(name)
    if not ent:
        abort(404)
    return ent


def _choices(field):
    c = field["choices"]
    return c() if callable(c) else (c or [])


def _parse(ent, form):
    data = {}
    for f in ent["fields"]:
        raw = (form.get(f["name"]) or "").strip()
        if not raw:
            if f["required"]:
                raise ValueError(f"'{f['label']}' is required")
            data[f["name"]] = None
            continue
        kind = f["kind"]
        if kind in ("int", "select_int"):
            try:
                val = int(raw)
            except ValueError:
                raise ValueError(f"'{f['label']}' must be a number")
            if kind == "int":
                if val < f["min"]:
                    raise ValueError(f"'{f['label']}' must be at least {f['min']}")
                if f["max"] and val > f["max"]:
                    raise ValueError(f"'{f['label']}' must be at most {f['max']}")
            elif val not in [c[0] for c in _choices(f)]:
                raise ValueError(f"Choose a valid '{f['label']}'")
            data[f["name"]] = val
        elif kind == "select":
            if raw not in [c[0] for c in _choices(f)]:
                raise ValueError(f"Choose a valid '{f['label']}'")
            data[f["name"]] = raw
        elif kind == "time":
            if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", raw):
                raise ValueError(f"'{f['label']}' must look like 09:00")
            data[f["name"]] = raw
        else:
            data[f["name"]] = raw
    return data


def _render(name, ent, editing=None):
    order = ent["order"] if isinstance(ent["order"], tuple) else (ent["order"],)
    fields = [dict(f, options=_choices(f)) for f in ent["fields"]]
    return render_template("admin_list.html", name=name, ent=ent, fields=fields,
                           rows=ent["model"].query.order_by(*order).all(), editing=editing)


@admin_bp.route("/<name>", methods=["GET", "POST"])
@role_required("admin")
def manage(name):
    ent = _entity(name)
    if request.method == "POST":
        try:
            db.session.add(ent["model"](**_parse(ent, request.form)))
            db.session.commit()
            flash("Added.")
        except ValueError as e:
            flash(str(e))
        except IntegrityError:
            db.session.rollback()
            flash("That entry already exists (duplicate code, name, or slot).")
        return redirect(url_for("admin.manage", name=name))
    return _render(name, ent)


@admin_bp.route("/<name>/<int:oid>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit(name, oid):
    ent = _entity(name)
    obj = db.get_or_404(ent["model"], oid)
    if request.method == "POST":
        try:
            for k, v in _parse(ent, request.form).items():
                setattr(obj, k, v)
            db.session.commit()
            flash("Saved.")
            return redirect(url_for("admin.manage", name=name))
        except ValueError as e:
            flash(str(e))
        except IntegrityError:
            db.session.rollback()
            flash("That entry already exists (duplicate code, name, or slot).")
    return _render(name, ent, editing=obj)


@admin_bp.route("/<name>/<int:oid>/delete", methods=["POST"])
@role_required("admin")
def delete(name, oid):
    ent = _entity(name)
    obj = db.get_or_404(ent["model"], oid)
    for model, col in ent["deps"]:
        if model.query.filter(getattr(model, col) == oid).count():
            flash(f"Cannot delete: still used by {model.__name__} records. Remove those first.")
            return redirect(url_for("admin.manage", name=name))
    db.session.delete(obj)
    db.session.commit()
    flash("Deleted.")
    return redirect(url_for("admin.manage", name=name))


@admin_bp.route("/slots/default", methods=["POST"])
@role_required("admin")
def default_slots():
    """Create Mon-Fri x 6 periods, skipping any that already exist."""
    added = 0
    for d in range(5):
        for p, (s, e) in enumerate(DEFAULT_PERIODS, start=1):
            if not TimeSlot.query.filter_by(day=d, period=p).first():
                db.session.add(TimeSlot(day=d, period=p, start=s, end=e))
                added += 1
    db.session.commit()
    flash(f"Added {added} default time slots.")
    return redirect(url_for("admin.manage", name="slots"))
