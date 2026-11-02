import pytest

from app import create_app
from app.extensions import db
from config import TestConfig
from seed import seed


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
        seed()
        yield app
        db.session.remove()
