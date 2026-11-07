import sqlite3

from flask_login import UserMixin
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager

ROLES = ("admin", "faculty", "student")
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]


@event.listens_for(Engine, "connect")
def _enforce_sqlite_foreign_keys(dbapi_connection, _record):
    """SQLite ignores foreign keys unless asked, so deletes could leave orphan rows."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), nullable=False, default="student")

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    weekly_sessions = db.Column(db.Integer, nullable=False, default=3)
    room_type = db.Column(db.String(16), nullable=False, default="lecture")  # lecture | lab


class Faculty(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(128))
    # login account of this teacher (None until linked); used by "my timetable"
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True)
    user = db.relationship("User")


class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    room_type = db.Column(db.String(16), nullable=False, default="lecture")


class TimeSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.Integer, nullable=False)  # 0=Mon .. 4=Fri
    period = db.Column(db.Integer, nullable=False)  # 1..N
    start = db.Column(db.String(5), nullable=False)
    end = db.Column(db.String(5), nullable=False)
    __table_args__ = (db.UniqueConstraint("day", "period"),)

    @property
    def label(self):
        return f"{DAYS[self.day]} P{self.period} ({self.start}-{self.end})"


class StudentGroup(db.Model):
    """One cohort (e.g. CSE-3A). Its size lives here, once, not on every section."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)
    strength = db.Column(db.Integer, nullable=False)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("student_group.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True)
    group = db.relationship("StudentGroup")
    user = db.relationship("User")


class Section(db.Model):
    """A course offered to a student group, taught by one faculty member."""

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("student_group.id"), nullable=False)
    course = db.relationship("Course")
    faculty = db.relationship("Faculty")
    group = db.relationship("StudentGroup")
    __table_args__ = (db.UniqueConstraint("course_id", "group_id"),)

    # Read-only shortcuts so the solver and conflict code keep working unchanged.
    @property
    def group_name(self):
        return self.group.name

    @property
    def strength(self):
        return self.group.strength


class FacultyUnavailability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey("time_slot.id"), nullable=False)
    __table_args__ = (db.UniqueConstraint("faculty_id", "slot_id"),)


class Allocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey("section.id"), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey("time_slot.id"), nullable=False)
    locked = db.Column(db.Boolean, default=False)  # manual adjustment, solver keeps it
    published = db.Column(db.Boolean, default=False)
    section = db.relationship("Section")
    room = db.relationship("Room")
    slot = db.relationship("TimeSlot")
    # a room can host only one class per slot (also protects against two teachers
    # grabbing the same free room at the same moment)
    __table_args__ = (db.UniqueConstraint("room_id", "slot_id"),)