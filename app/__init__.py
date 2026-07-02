import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app(config=None):
    app = Flask(__name__, static_folder="static", static_url_path="")

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///zillim.db"
    ).replace("postgres://", "postgresql://", 1)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only")

    # Program configuration — pilot-tunable, but gates themselves are locked.
    app.config.setdefault("HESITATION_MS", 4000)
    app.config.setdefault("SESSIONS_PER_DAY", 1)   # cap 3
    app.config.setdefault("VERIFIED_TEST_SIZE", 25)
    app.config.setdefault("LESSON_MIN_NEW_WORDS", 18)
    app.config.setdefault("LESSON_MAX_NEW_WORDS", 30)
    app.config.setdefault("DRILL_MIX", (0.4, 0.4, 0.2))  # new / weak / maintenance
    app.config.setdefault("POOL_INTERVALS_DAYS", (0, 1, 3, 7))

    if config:
        app.config.update(config)

    db.init_app(app)

    from app.api import api

    app.register_blueprint(api, url_prefix="/api")

    @app.route("/")
    def index():
        return app.send_static_file("index.html")

    with app.app_context():
        db.create_all()

    return app
