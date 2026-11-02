from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager

ROLES = ("admin", "faculty", "student")
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]


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


class Section(db.Model):
    """A course offered to a student group, taught by one faculty member."""

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=False)
    group_name = db.Column(db.String(32), nullable=False)  # e.g. "CSE-3A"
    strength = db.Column(db.Integer, nullable=False)
    course = db.relationship("Course")
    faculty = db.relationship("Faculty")


class FacultyUnavailability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey("time_slot.id"), nullable=False)


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
