import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URI", "sqlite:///teamliste.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_TYPE = os.environ.get("SESSION_TYPE", "filesystem")
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-me")
    APP_ENV = os.environ.get("APP_ENV", "development")
    FLASK_DEBUG = os.environ.get("FLASK_DEBUG")
    SOCKETIO_HOST = os.environ.get("SOCKETIO_HOST", "0.0.0.0")
    SOCKETIO_PORT = int(os.environ.get("SOCKETIO_PORT", 5000))

    DEBUG = (
        FLASK_DEBUG == "1" if FLASK_DEBUG is not None else APP_ENV != "production"
    )
