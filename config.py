import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///timetable.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SOLVER_TIME_LIMIT_SECONDS = 30


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SOLVER_TIME_LIMIT_SECONDS = 10
