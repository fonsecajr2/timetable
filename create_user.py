"""Create a login, or reset its password, straight from the terminal.

    python create_user.py admin   alice  secret123
    python create_user.py faculty rao    secret123
    python create_user.py student asha   secret123

If the username exists, its password is reset (and its role is left unchanged).
Faculty and student logins still need to be linked to a faculty/student record:
do that in the app under People.
"""
import sys

from app import create_app
from app.extensions import db
from app.models import ROLES, User


def main(argv):
    if len(argv) != 3 or argv[0] not in ROLES:
        sys.exit(__doc__)
    role, username, password = argv
    if len(password) < 6:
        sys.exit("Password must be at least 6 characters.")
    with create_app().app_context():
        user = User.query.filter_by(username=username).first()
        if user:
            user.set_password(password)
            print(f"Password reset for '{username}' (role: {user.role}).")
        else:
            user = User(username=username, role=role)
            user.set_password(password)
            db.session.add(user)
            print(f"Created {role} login '{username}'.")
        db.session.commit()


if __name__ == "__main__":
    main(sys.argv[1:])