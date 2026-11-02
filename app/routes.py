from functools import wraps

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .extensions import db
from .models import DAYS, Allocation, FacultyUnavailability, TimeSlot, User
from .scheduler import find_conflicts, generate_timetable

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


@bp.route("/")
@login_required
def index():
    slots = TimeSlot.query.order_by(TimeSlot.period, TimeSlot.day).all()
    periods = sorted({s.period for s in slots})
    grid = {}
    q = Allocation.query
    if current_user.role != "admin":
        q = q.filter_by(published=True)
    for a in q.all():
        grid.setdefault((a.slot.period, a.slot.day), []).append(a)
    return render_template("timetable.html", days=DAYS, periods=periods, grid=grid)


@bp.route("/generate", methods=["POST"])
@role_required("admin")
def generate():
    result = generate_timetable(time_limit=current_app.config["SOLVER_TIME_LIMIT_SECONDS"])
    flash(f"Generation: {result}")
    return redirect(url_for("main.conflicts"))


@bp.route("/conflicts")
@role_required("admin")
def conflicts():
    unavail = [(u.faculty_id, u.slot_id) for u in FacultyUnavailability.query.all()]
    return render_template("conflicts.html",
                           conflicts=find_conflicts(Allocation.query.all(), unavail))


@bp.route("/publish", methods=["POST"])
@role_required("admin")
def publish():
    Allocation.query.update({Allocation.published: True})
    db.session.commit()
    flash("Timetable published")
    return redirect(url_for("main.index"))
