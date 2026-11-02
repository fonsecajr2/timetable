from flask import Flask

from config import Config

from .extensions import db, login_manager


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    login_manager.init_app(app)

    from .admin import admin_bp
    from .routes import bp
    app.register_blueprint(bp)
    app.register_blueprint(admin_bp)

    with app.app_context():
        db.create_all()
    return app
