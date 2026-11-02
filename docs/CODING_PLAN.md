# Coding Plan: University Timetable and Resource Scheduling System

Stack: Python 3.12, Flask, SQLAlchemy (SQLite), Flask-Login, OR-Tools CP-SAT, pytest.

## Milestones
| # | Milestone | Deliverable | Status |
|---|-----------|-------------|--------|
| 0 | Project setup | Repo layout, config, app factory, seed data, tests | Done |
| 1 | Data model | Courses, faculty, sections, rooms, slots, unavailability, allocations | Done (base) |
| 2 | Constraint engine | Hard constraints H1-H8, conflict detector | Done |
| 3 | Auto generation | CP-SAT solver with optimisation objective | Done (base) |
| 4 | Manual adjustment | Move/swap an allocation, lock it, re-validate on save | Next |
| 5 | CRUD screens | Admin pages for courses, faculty, rooms, slots, sections, availability | Done |
| 6 | Role-based views | Admin / faculty (own timetable) / student (own group) | Partial |
| 7 | Publish + reports | Publish flow, Excel/PDF export, utilisation report | Next |
| 8 | Evaluation | Scalability test with larger data, solver-time and quality metrics | Later |
| 9 | Documentation | SRS alignment, WPR notes, final report, PPT screenshots | Ongoing |

## Hard constraints
H1 each session placed once | H2 room one session per slot | H3 faculty one session per slot |
H4 student group one session per slot | H5 capacity >= strength | H6 room type matches course |
H7 faculty unavailability | H8 at most one session per day per section

## Optimisation objective
Minimise wasted seats (room capacity minus section strength). Extra soft goals can be added later by extending the objective in `app/scheduler/solver.py`.

## Scope decisions
- "Should" category: manual adjustments only.
- Future-scope items are excluded.
