import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
import sys

logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

app = Flask(__name__)

# Validate SESSION_SECRET
session_secret = os.environ.get("SESSION_SECRET")
if not session_secret or len(session_secret) < 16:
    print("ERROR: SESSION_SECRET must be set and at least 16 characters.", file=sys.stderr)
else:
    app.secret_key = session_secret

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    database_url = "sqlite:///data.db"
    logging.warning("DATABASE_URL not set, defaulting to sqlite:///data.db for local development.")

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    'pool_pre_ping': True,
    "pool_recycle": 300,
}

db.init_app(app)

with app.app_context():
    try:
        import models  # noqa: F401
        db.create_all()
        logging.info("Database tables created")
    except Exception as e:
        logging.exception("Database initialization failed: %s", e)
