# University Timetable and Resource Scheduling System (Phase 1)

## Setup
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python create_admin.py  # empty database + logins (use this to enter your own data)
# or: python seed.py    # demo data + users (admin/admin123, faculty/faculty123, student/student123)
python run.py           # http://127.0.0.1:5000
pytest                  # run tests
```

## Layout
```
app/
  __init__.py        app factory
  models.py          SQLAlchemy models
  admin.py           setup screens (courses, faculty, rooms, slots, sections, availability)
  routes.py          login, timetable view, generate, conflicts, publish
  scheduler/
    solver.py        CP-SAT generation (hard constraints + objective)
    conflicts.py     conflict detection (also used after manual edits)
  templates/
config.py  seed.py  run.py
tests/
docs/CODING_PLAN.md
```

## Project overview
This project is a university timetable and resource scheduling system designed to help academic administrators build balanced class schedules without conflicts. It combines a Flask web application, a relational database, and an OR-Tools CP-SAT constraint solver to generate valid weekly timetables for courses, faculty, rooms, and student sections.

The system is meant to handle the common scheduling challenges of a department or faculty: assigning lectures and labs to available time slots, matching the correct room type and capacity, avoiding faculty clashes, respecting unavailability, and keeping multiple section groups from being scheduled at the same time.

## What the project does
The application supports the full administrative workflow needed to create a timetable from structured data:

- Manage courses and their weekly session requirements
- Add faculty members and assign them to sections
- Define classroom inventory by room name, capacity, and type
- Create time slots across the week
- Set up course sections for different student groups and cohort sizes
- Record faculty unavailability by day/period
- Generate an automatically optimized timetable
- Detect scheduling conflicts after generation or manual edit
- Publish the schedule for non-admin users to view
- Restrict access by user role (admin, faculty, student)

## Core functionality and capacities
The system is built around a set of hard constraints and optimization rules that make the generated timetable usable in real academic environments:

- Each course session is assigned exactly once within the required weekly session count
- No room is double-booked in the same slot
- No faculty member teaches two classes at the same time
- No student group is scheduled in two places at once
- Room capacity must be greater than or equal to student strength
- Room type must match the course type (lecture vs lab)
- Faculty unavailability is respected
- A section is limited to one session per day

The solver also minimizes wasted seating capacity by reducing the difference between room size and section population. This helps produce compact, practical schedules rather than merely any valid timetable.

## Capacity and practical scope
This project is structured for departmental-level scheduling and currently supports a typical academic timetable workflow with:

- Multiple departments or course offerings in one database
- Multiple faculty members and student groups
- Room management for lecture and lab spaces
- Weekly scheduling across Monday to Friday
- Default slot templates of 6 periods per day
- Role-based access for admin, faculty, and student users
- Manual locking of specific allocations before regeneration

It is best suited to small to medium university scheduling tasks where schedule generation needs to be fast, transparent, and constraint-driven.

## Tech stack
- Python 3.x
- Flask web framework
- Flask-Login for authentication
- Flask-SQLAlchemy for persistence
- SQLite database (default)
- OR-Tools CP-SAT for timetable optimization
- pytest for automated validation

## Typical workflow
1. Create an empty database or load demo data with the included scripts.
2. Log in as the admin user.
3. Add courses, faculty, rooms, slots, and sections.
4. Mark unavailable times for faculty when needed.
5. Generate the timetable.
6. Review conflicts and fix any issue manually.
7. Publish the approved schedule.
8. View the timetable from the role-specific interface.

## Roles
- Admin: manages data and generates/publishes the schedule
- Faculty: can view the published timetable relevant to their teaching assignment
- Student: can view the published timetable for their group or general published schedule

## Files and responsibilities
- app/models.py: database schema for users, courses, faculty, rooms, slots, sections, and allocations
- app/admin.py: CRUD screens for all scheduling entities
- app/routes.py: login, timetable view, generate, conflicts, and publish endpoints
- app/scheduler/solver.py: CP-SAT scheduling engine and optimization logic
- app/scheduler/conflicts.py: conflict-detection logic
- seed.py: inserts example data for demos
- create_admin.py: creates a clean database with login accounts
- tests/: coverage for generation, conflict detection, validation, and access control

## Summary
This project turns a scheduling problem into a manageable, data-driven workflow. Instead of manually assigning lectures to times and rooms, it lets administrators define course and resource data, applies hard constraints, and generates a timetable that is valid, optimized, and easy to review.

It is a practical academic scheduling solution for universities and training institutions that need a lightweight, database-backed timetable planner with automated optimization and conflict checking.
