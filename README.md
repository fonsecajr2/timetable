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
