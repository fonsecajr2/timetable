from functools import wraps

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from .extensions import db
from .models import (DAYS, Allocation, Faculty, FacultyUnavailability, Room, Section, Student,
                     TimeSlot, User)
from .scheduler import check_move, find_conflicts, generate_timetable

bp = Blueprint("main", __name__)


def role_required(*roles):
    def deco(fn):
        @wraps(fn)
        @login_required
        def wrapper(*a, **kw):
            if current_user.role not in roles:
                abort(403)
            return fn(*a, **kw)
        return wrapper
    return deco


# ----------------------------------------------------------------------------- helpers
def _allocations():
    """Allocation query with everything the views touch loaded up front (no N+1)."""
    sec = joinedload(Allocation.section)
    return Allocation.query.options(
        sec.joinedload(Section.course), sec.joinedload(Section.faculty),
        sec.joinedload(Section.group), joinedload(Allocation.room),
        joinedload(Allocation.slot))


def _unavailability():
    return [(u.faculty_id, u.slot_id) for u in FacultyUnavailability.query.all()]


def _slot_info():
    """(all slots in display order, {period: 'HH:MM-HH:MM'})."""
    slots = TimeSlot.query.order_by(TimeSlot.period, TimeSlot.day).all()
    times = {}
    for s in slots:
        times.setdefault(s.period, f"{s.start}-{s.end}")
    return slots, times


def _grid(allocs):
    grid = {}
    for a in allocs:
        grid.setdefault((a.slot.period, a.slot.day), []).append(a)
    return grid


def _current_faculty():
    return Faculty.query.filter_by(user_id=current_user.id).first()


# ------------------------------------------------------------------------------- auth
@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"]).first()
        if user and user.check_password(request.form["password"]):
            login_user(user)
            return redirect(url_for("main.index"))
        flash("Invalid credentials")
    return render_template("login.html")


@bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("main.login"))


# ------------------------------------------------------------------------- timetables
@bp.route("/")
@login_required
def index():
    """Admin: the whole timetable. Faculty and students: their own (see my_timetable)."""
    if current_user.role != "admin":
        return redirect(url_for("main.my_timetable"))
    slots, _ = _slot_info()
    periods = sorted({s.period for s in slots})
    return render_template("timetable.html", days=DAYS, periods=periods,
                           grid=_grid(_allocations().all()))


@bp.route("/my")
@role_required("faculty", "student")
def my_timetable():
    """A teacher sees the classes they teach; a student sees their group's classes."""
    is_faculty = current_user.role == "faculty"
    owner, allocs = None, []
    if is_faculty:
        owner = _current_faculty()
        if owner:
            allocs = (_allocations().join(Allocation.section)
                      .filter(Section.faculty_id == owner.id, Allocation.published.is_(True))
                      .all())
    else:
        owner = Student.query.filter_by(user_id=current_user.id).first()
        if owner:
            allocs = (_allocations().join(Allocation.section)
                      .filter(Section.group_id == owner.group_id, Allocation.published.is_(True))
                      .all())
    slots, times = _slot_info()
    title = (f"My timetable - {owner.name}" if is_faculty and owner
             else f"My timetable - {owner.name} ({owner.group.name})" if owner
             else "My timetable")
    return render_template("my_timetable.html", title=title, linked=owner is not None,
                           is_faculty=is_faculty, days=DAYS,
                           periods=sorted({s.period for s in slots}), times=times,
                           grid=_grid(allocs))


@bp.route("/rooms")
@login_required
def room_timetable():
    """Week grid of one room showing when it is booked and when it is free."""
    rooms = Room.query.order_by(Room.name).all()
    if not rooms:
        return render_template("rooms.html", rooms=[], room=None)
    room_id = request.args.get("room", type=int)
    room = next((r for r in rooms if r.id == room_id), rooms[0])
    slots, times = _slot_info()
    occupied = {(a.slot.period, a.slot.day): a
                for a in _allocations().filter(Allocation.room_id == room.id).all()}
    free = sum(1 for s in slots if (s.period, s.day) not in occupied)
    return render_template("rooms.html", rooms=rooms, room=room, days=DAYS,
                           periods=sorted({s.period for s in slots}), times=times,
                           occupied=occupied, free=free, total=len(slots))


# ------------------------------------------------------------------------------ moving
def _movable_allocation(alloc_id):
    """Admin may move any class; a teacher only their own."""
    alloc = db.get_or_404(Allocation, alloc_id)
    if current_user.role == "faculty":
        owner = _current_faculty()
        if not owner or alloc.section.faculty_id != owner.id:
            abort(403)
    return alloc


@bp.route("/move/<int:alloc_id>", methods=["GET", "POST"])
@role_required("admin", "faculty")
def move(alloc_id):
    """GET: every free (slot, room) this class could move to. POST: apply the chosen one."""
    alloc = _movable_allocation(alloc_id)
    everything = _allocations().all()
    unavail = _unavailability()

    if request.method == "POST":
        try:
            room_id, slot_id = (int(x) for x in request.form.get("target", "").split("-"))
        except ValueError:
            flash("Choose a room and slot.")
            return redirect(url_for("main.move", alloc_id=alloc_id))
        room, slot = db.session.get(Room, room_id), db.session.get(TimeSlot, slot_id)
        if not room or not slot:
            flash("Choose a room and slot.")
            return redirect(url_for("main.move", alloc_id=alloc_id))
        reasons = check_move(alloc, room, slot, everything, unavail)
        if reasons:
            flash("Cannot move: " + "; ".join(reasons))
            return redirect(url_for("main.move", alloc_id=alloc_id))
        alloc.room, alloc.slot = room, slot
        alloc.locked = True  # the solver keeps manual moves when it regenerates
        try:
            db.session.commit()
        except IntegrityError:  # someone took that room at the same moment
            db.session.rollback()
            flash("That room was just taken. Pick another.")
            return redirect(url_for("main.move", alloc_id=alloc_id))
        flash(f"Moved {alloc.section.course.code}/{alloc.section.group_name} "
              f"to {room.name}, {slot.label}.")
        return redirect(url_for("main.my_timetable" if current_user.role == "faculty"
                                else "main.index"))

    rooms = Room.query.order_by(Room.name).all()
    slots, times = _slot_info()
    options, slot_at = {}, {}
    for s in slots:
        slot_at[(s.period, s.day)] = s
        for r in rooms:
            if not check_move(alloc, r, s, everything, unavail):
                options.setdefault((s.period, s.day), []).append(r)
    return render_template("move.html", alloc=alloc, days=DAYS,
                           periods=sorted({s.period for s in slots}), times=times,
                           options=options, slot_at=slot_at)


# ------------------------------------------------------------------------------- admin
@bp.route("/generate", methods=["POST"])
@role_required("admin")
def generate():
    result = generate_timetable(time_limit=current_app.config["SOLVER_TIME_LIMIT_SECONDS"])
    flash(f"Generation: {result}")
    return redirect(url_for("main.conflicts"))


@bp.route("/conflicts")
@role_required("admin")
def conflicts():
    return render_template("conflicts.html", conflicts=find_conflicts(
        _allocations().all(), _unavailability(), sections=Section.query.all()))


@bp.route("/publish", methods=["POST"])
@role_required("admin")
def publish():
    Allocation.query.update({Allocation.published: True})
    db.session.commit()
    flash("Timetable published")
    return redirect(url_for("main.index"))