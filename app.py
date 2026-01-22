"""Zentrale Steuerung für Kassensystem und Shotcounter.

Die Anwendung bündelt zwei eigenständige Subsysteme (Kasse & Shotcounter)
unter einer gemeinsamen Event-Verwaltung. Im Adminbereich können Events
angelegt, aktiviert, archiviert und mit eigenen Einstellungen versehen
werden. Pro Event lässt sich separat steuern, ob Kassensystem oder
Shotcounter aktiv sein sollen.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import secrets
import sqlite3
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Iterable, List

from flask import (
    Flask,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_migrate import Migrate
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, func, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import attributes
from werkzeug.datastructures import FileStorage

from credentials_manager import credentials_manager


# ---------------------------------------------------------------------------
# App- und DB-Konfiguration
# ---------------------------------------------------------------------------
app = Flask(__name__, instance_relative_config=True)

is_production = os.environ.get("FLASK_ENV") == "production" or os.environ.get("APP_ENV") == "production"

# Configure credentials storage path (default: instance/credentials.json).
credentials_file_env = os.environ.get("CREDENTIALS_FILE")
if credentials_file_env:
    credentials_manager.credentials_file = Path(credentials_file_env)
else:
    repo_root = Path(__file__).resolve().parent
    legacy_path = repo_root / "credentials.json"
    instance_path = Path(app.instance_path) / "credentials.json"
    if legacy_path.exists() and os.access(legacy_path.parent, os.W_OK):
        credentials_manager.credentials_file = legacy_path
    else:
        credentials_manager.credentials_file = instance_path

# Load credentials from file or environment
creds = credentials_manager.get_credentials()
secret_key = creds.get("secret_key") or os.environ.get("SECRET_KEY") or app.config.get("SECRET_KEY")
if not secret_key:
    if is_production and not app.config.get("TESTING"):
        raise RuntimeError("SECRET_KEY muss in Produktion gesetzt sein.")
    secret_key = "dev-secret-key"

app.config["SECRET_KEY"] = secret_key
app.config.setdefault("SQLALCHEMY_DATABASE_URI", f"sqlite:///{Path(app.instance_path) / 'app.db'}")
app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
app.config.setdefault("SESSION_TYPE", "filesystem")

Path(app.instance_path).mkdir(parents=True, exist_ok=True)
session_dir = Path(app.instance_path) / "sessions"
session_dir.mkdir(parents=True, exist_ok=True)
app.config.setdefault("SESSION_FILE_DIR", str(session_dir))

# Upload configuration
UPLOAD_FOLDER = Path(app.instance_path) / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB max file size
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

db = SQLAlchemy(app)
Session(app)
Migrate(app, db)


def configure_logging(flask_app: Flask) -> None:
    """Richtet sauberes, rotierendes Logging ein."""

    log_dir = Path(flask_app.instance_path) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_dir / "app.log", maxBytes=512_000, backupCount=3)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)

    flask_app.logger.handlers.clear()
    flask_app.logger.addHandler(handler)
    flask_app.logger.setLevel(logging.INFO)
    flask_app.logger.propagate = False
    flask_app.logger.info("Logging initialisiert")


configure_logging(app)

@event.listens_for(Engine, "connect")
def set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.execute("PRAGMA foreign_keys=ON;")
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# Datenbank-Modelle
# ---------------------------------------------------------------------------
class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    is_archived = db.Column(db.Boolean, default=False)
    kassensystem_enabled = db.Column(db.Boolean, default=True)
    shotcounter_enabled = db.Column(db.Boolean, default=True)
    shared_settings = db.Column(db.JSON, default=dict)
    kassensystem_settings = db.Column(db.JSON, default=dict)
    shotcounter_settings = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Team(db.Model):
    __table_args__ = (db.UniqueConstraint("event_id", "name", name="uq_team_event_name"),)

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    shots = db.Column(db.Integer, default=0, nullable=False)

    event = db.relationship("Event", backref=db.backref("teams", cascade="all, delete-orphan"))


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id", ondelete="CASCADE"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    total = db.Column(db.Integer, nullable=False)

    event = db.relationship("Event", backref=db.backref("orders", cascade="all, delete-orphan"))


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)

    order = db.relationship("Order", backref=db.backref("items", cascade="all, delete-orphan"))


class DrinkSale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, default=0, nullable=False)

    order = db.relationship("Order", backref=db.backref("drink_sales", cascade="all, delete-orphan"))


class OrderLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id", ondelete="CASCADE"), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id", ondelete="CASCADE"), nullable=True)
    total = db.Column(db.Integer, nullable=False)
    items = db.Column(db.JSON, default=list)  # [{"name": str, "qty": int, "price": int}]
    actor = db.Column(db.String(200))
    user_agent = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    event = db.relationship("Event", backref=db.backref("order_logs", cascade="all, delete-orphan"))


class ShotLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id", ondelete="CASCADE"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id", ondelete="SET NULL"), nullable=True)
    team_name = db.Column(db.String(150))
    amount = db.Column(db.Integer, nullable=False)
    actor = db.Column(db.String(200))
    user_agent = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    event = db.relationship("Event", backref=db.backref("shot_logs", cascade="all, delete-orphan"))
    team = db.relationship("Team")


# ---------------------------------------------------------------------------
# CSV Export Helpers
# ---------------------------------------------------------------------------
def csv_response(filename: str, headers: List[str], rows: Iterable[Iterable[object]]) -> Response:
    """Return a CSV download with the given rows."""

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([value if value is not None else "" for value in row])

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---------------------------------------------------------------------------
# Kassensystem-Konfiguration
# ---------------------------------------------------------------------------
@dataclass
class ButtonConfig:
    name: str
    label: str
    price: int
    css_class: str
    color: str | None = None
    category: str = "Standard"


DEFAULT_BUTTONS: List[ButtonConfig] = [
    ButtonConfig(
        name="Süssgetränke",
        label="Süssgetränke",
        price=6,
        css_class="suess",
        color="#1f2a44",
        category="Getränke",
    ),
    ButtonConfig(
        name="Bier",
        label="Bier / Mate / Red Bull / Smirnoff",
        price=7,
        css_class="bier",
        color="#193f8a",
        category="Alkohol",
    ),
    ButtonConfig(name="Wein", label="Wein", price=7, css_class="wein", color="#8a1f6f", category="Alkohol"),
    ButtonConfig(
        name="Weinflasche 0.7",
        label="Weinflasche",
        price=22,
        css_class="flasche",
        color="#5b2d30",
        category="Alkohol",
    ),
    ButtonConfig(name="Drink 10", label="Drink 10", price=12, css_class="gross", color="#2e4c3d", category="Alkohol"),
    ButtonConfig(name="Depot rein", label="Depot rein", price=-2, css_class="depot", color="#374151", category="Diverses"),
    ButtonConfig(
        name="Weinglassdepot",
        label="Weinglas Depot",
        price=2,
        css_class="Weinglassdepot",
        color="#3f2d67",
        category="Diverses",
    ),
    ButtonConfig(name="Kaffee", label="Kaffee", price=3, css_class="kaffee", color="#4b3322", category="Getränke"),
    ButtonConfig(name="Shot", label="Shot", price=5, css_class="shot", color="#7a1f2a", category="Alkohol"),
]

DEFAULT_SHOTCOUNTER_SETTINGS: Dict[str, int | float | str] = {
    "background_color": "#0b1222",
    "primary_color": "#1e293b",
    "secondary_color": "#38bdf8",
    "tertiary_color": "#34d399",
    "title_size": 3.2,  # rem
    "team_size": 1.6,  # rem
    "leaderboard_limit": 10,
}

HEX_COLOR_PATTERN = re.compile(r"^#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


def parse_json_field(raw_value: str | None) -> Dict:
    if not raw_value:
        return {}
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON ungültig: {exc}")


def get_active_event() -> Event | None:
    return Event.query.filter_by(is_active=True, is_archived=False).first()


def _sanitize_hex_color(value: str | None, fallback: str) -> str:
    if isinstance(value, str) and HEX_COLOR_PATTERN.match(value.strip()):
        return value.strip()
    return fallback


def _sanitize_font_size(value: float | int | str | None, fallback: float) -> float:
    if value is None:
        return fallback
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(0.5, min(parsed, 10.0))


def _sanitize_leaderboard_limit(value: int | str | None, fallback: int) -> int:
    try:
        parsed = int(value) if value is not None else fallback
    except (TypeError, ValueError):
        return fallback
    if parsed < 1:
        return fallback
    return min(parsed, 50)


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_background_image(file: FileStorage | None, event_id: int) -> str | None:
    """Save uploaded background image and return the filename."""
    if not file or not file.filename:
        return None
    
    if not allowed_file(file.filename):
        return None
    
    # Generate unique filename
    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"bg_{event_id}_{secrets.token_hex(8)}.{ext}"
    filepath = Path(app.config["UPLOAD_FOLDER"]) / filename
    
    try:
        file.save(str(filepath))
        return filename
    except Exception as exc:
        app.logger.error("Fehler beim Speichern des Hintergrundbildes: %s", exc)
        return None


def delete_background_image(filename: str | None) -> None:
    """Delete a background image file if it exists."""
    if not filename:
        return
    filepath = Path(app.config["UPLOAD_FOLDER"]) / filename
    try:
        if filepath.exists():
            filepath.unlink()
    except Exception as exc:
        app.logger.error("Fehler beim Löschen des Hintergrundbildes: %s", exc)


def validate_shotcounter_settings(raw: dict | None) -> Dict[str, int | float | str]:
    settings = {**DEFAULT_SHOTCOUNTER_SETTINGS}
    incoming = raw if isinstance(raw, dict) else {}
    settings["background_color"] = _sanitize_hex_color(
        incoming.get("background_color"), DEFAULT_SHOTCOUNTER_SETTINGS["background_color"]
    )
    settings["primary_color"] = _sanitize_hex_color(
        incoming.get("primary_color"), DEFAULT_SHOTCOUNTER_SETTINGS["primary_color"]
    )
    settings["secondary_color"] = _sanitize_hex_color(
        incoming.get("secondary_color"), DEFAULT_SHOTCOUNTER_SETTINGS["secondary_color"]
    )
    settings["tertiary_color"] = _sanitize_hex_color(
        incoming.get("tertiary_color"), DEFAULT_SHOTCOUNTER_SETTINGS["tertiary_color"]
    )
    settings["title_size"] = _sanitize_font_size(
        incoming.get("title_size"), float(DEFAULT_SHOTCOUNTER_SETTINGS["title_size"])
    )
    settings["team_size"] = _sanitize_font_size(
        incoming.get("team_size"), float(DEFAULT_SHOTCOUNTER_SETTINGS["team_size"])
    )
    settings["leaderboard_limit"] = _sanitize_leaderboard_limit(
        incoming.get("leaderboard_limit"), int(DEFAULT_SHOTCOUNTER_SETTINGS["leaderboard_limit"])
    )
    # Preserve background_image only if it's a valid string and file exists
    if incoming.get("background_image"):
        bg_img = str(incoming["background_image"])
        filepath = Path(app.config["UPLOAD_FOLDER"]) / bg_img
        if filepath.exists() and filepath.is_file():
            settings["background_image"] = bg_img
    return settings


def resolve_shotcounter_settings(event: Event | None) -> Dict[str, int | float | str]:
    raw_settings = event.shotcounter_settings if event and isinstance(event.shotcounter_settings, dict) else {}
    return validate_shotcounter_settings(raw_settings)


def require_active_event(*, kassensystem: bool = False, shotcounter: bool = False) -> Event:
    event = get_active_event()
    if not event:
        abort(404, description="Kein aktives Event vorhanden.")
    if kassensystem and not event.kassensystem_enabled:
        abort(404, description="Kassensystem ist für das aktuelle Event deaktiviert.")
    if shotcounter and not event.shotcounter_enabled:
        abort(404, description="Shotcounter ist für das aktuelle Event deaktiviert.")
    return event


def resolve_button_config(event: Event | None) -> List[ButtonConfig]:
    raw_items: Iterable[dict] | None = None
    if event and isinstance(event.kassensystem_settings, dict):
        raw_items = event.kassensystem_settings.get("items")
    normalized: List[ButtonConfig] = []
    default_color_lookup = {btn.css_class: btn.color for btn in DEFAULT_BUTTONS}
    items_source = raw_items if raw_items else [btn.__dict__ for btn in DEFAULT_BUTTONS]
    for item in items_source:
        try:
            normalized.append(
                ButtonConfig(
                    name=item["name"],
                    label=item.get("label") or item["name"],
                    price=int(item["price"]),
                    css_class=item.get("css_class", "suess"),
                    color=item.get("color")
                    or default_color_lookup.get(item.get("css_class", ""))
                    or "#1f2a44",
                    category=item.get("category", "Standard"),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return normalized or DEFAULT_BUTTONS


def validate_and_normalize_buttons(settings: Dict | None) -> Dict:
    """Validates kassensystem settings and normalizes product buttons."""

    if not isinstance(settings, dict):
        settings = {}

    raw_items = settings.get("items")
    items = raw_items if isinstance(raw_items, list) else []

    normalized: List[Dict] = []
    seen_names: set[str] = set()
    duplicates: List[str] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("label") or "").strip()
        if not name:
            continue

        if name in seen_names:
            duplicates.append(name)
            continue

        seen_names.add(name)
        label = (item.get("label") or name).strip() or name
        try:
            price = int(item.get("price", 0))
        except (TypeError, ValueError):
            price = 0

        normalized.append(
            {
                "name": name,
                "label": label,
                "price": price,
                "css_class": item.get("css_class") or "custom",
                "color": item.get("color"),
                "category": item.get("category") or "Standard",
            }
        )

    if duplicates:
        dup_list = ", ".join(sorted(set(duplicates)))
        raise ValueError(f"Doppelte Produktnamen gefunden: {dup_list}")

    # If no items provided, use DEFAULT_BUTTONS
    if not normalized:
        normalized = [
            {
                "name": btn.name,
                "label": btn.label,
                "price": btn.price,
                "css_class": btn.css_class,
                "color": btn.color,
                "category": btn.category,
            }
            for btn in DEFAULT_BUTTONS
        ]

    sanitized = {k: v for k, v in settings.items() if k != "items"}
    sanitized["items"] = normalized
    return sanitized


def resolve_actor() -> tuple[str, str]:
    """Returns tuple of (actor, user_agent) derived from request context."""

    try:
        ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unbekannt"
        ua = (request.user_agent.string or "").strip()[:280]
    except Exception:
        ip, ua = "unbekannt", ""
    actor = ip
    return actor, ua


def _admin_credentials() -> tuple[str, str] | None:
    """Get admin credentials from credentials manager.
    
    Returns:
        Tuple of (username, password) or None if no password is set (unlocked)
    """
    creds = credentials_manager.get_credentials()
    password = creds.get("admin_password")
    
    if not password:
        # No password set - system is unlocked, no auth required
        return None
    
    username = creds.get("admin_username") or "admin"
    return username, password


def _admin_auth_required() -> Response:
    return Response(
        "Admin-Authentifizierung erforderlich.",
        401,
        {"WWW-Authenticate": 'Basic realm="Admin"'},
    )


@app.before_request
def enforce_admin_auth():
    if not request.path.startswith("/admin"):
        return None
    credentials = _admin_credentials()
    if not credentials:
        return None
    username, password = credentials
    auth = request.authorization
    if not auth or auth.username != username or auth.password != password:
        # If the request likely comes from JS (fetch/AJAX) return JSON
        # so the client can parse the error instead of getting an HTML page.
        accept = request.headers.get("Accept", "")
        is_xhr = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        if is_xhr or "application/json" in accept:
            return jsonify({"success": False, "error": "Admin-Authentifizierung erforderlich."}), 401
        return _admin_auth_required()
    return None


def cart_key(event: Event) -> str:
    return f"cart_{event.id}"


def event_statistics(event: Event) -> Dict:
    """Aggregates revenue/orders and shot data for an event."""

    revenue = (
        db.session.query(func.coalesce(func.sum(Order.total), 0))
        .filter(Order.event_id == event.id)
        .scalar()
        or 0
    )
    order_count = db.session.query(func.count(Order.id)).filter(Order.event_id == event.id).scalar() or 0
    shots_total = (
        db.session.query(func.coalesce(func.sum(ShotLog.amount), 0))
        .filter(ShotLog.event_id == event.id)
        .scalar()
        or 0
    )
    top_products = (
        db.session.query(DrinkSale.name, func.sum(DrinkSale.quantity))
        .join(Order, Order.id == DrinkSale.order_id)
        .filter(Order.event_id == event.id)
        .group_by(DrinkSale.name)
        .order_by(func.sum(DrinkSale.quantity).desc())
        .limit(5)
        .all()
    )
    top_shots = (
        db.session.query(Team.name, Team.shots)
        .filter(Team.event_id == event.id)
        .order_by(Team.shots.desc(), Team.name.asc())
        .limit(5)
        .all()
    )
    return {
        "revenue": revenue,
        "order_count": order_count,
        "shots_total": shots_total,
        "top_products": top_products,
        "top_shots": top_shots,
    }


# ---------------------------------------------------------------------------
# Routen: Dashboard & Admin
# ---------------------------------------------------------------------------
@app.route("/")
def dashboard():
    active_event = get_active_event()
    events = Event.query.order_by(Event.created_at.desc()).all()
    stats_map = {event.id: event_statistics(event) for event in events}
    return render_template("dashboard.html", active_event=active_event, events=events, stats_map=stats_map)

@app.route("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        return {"status": "error", "db": "unavailable"}, 500
    return {"status": "ok"}


@app.route("/events/<int:event_id>")
def event_detail(event_id: int):
    event = Event.query.get_or_404(event_id)
    stats = event_statistics(event)
    order_logs = (
        OrderLog.query.filter_by(event_id=event.id).order_by(OrderLog.created_at.desc()).limit(50).all()
    )
    shot_logs = (
        ShotLog.query.filter_by(event_id=event.id).order_by(ShotLog.created_at.desc()).limit(50).all()
    )
    sales = (
        db.session.query(DrinkSale.name, func.sum(DrinkSale.quantity))
        .join(Order, Order.id == DrinkSale.order_id)
        .filter(Order.event_id == event.id)
        .group_by(DrinkSale.name)
        .order_by(func.sum(DrinkSale.quantity).desc())
        .all()
    )
    teams = (
        Team.query.filter_by(event_id=event.id).order_by(Team.shots.desc(), Team.name.asc()).all()
    )
    return render_template(
        "event_detail.html",
        event=event,
        stats=stats,
        order_logs=order_logs,
        shot_logs=shot_logs,
        sales=sales,
        teams=teams,
    )


@app.route("/events/<int:event_id>/export/order_logs.csv")
def export_order_logs(event_id: int):
    event = Event.query.get_or_404(event_id)
    logs = OrderLog.query.filter_by(event_id=event.id).order_by(OrderLog.created_at.asc()).all()

    rows = []
    for log in logs:
        item_parts = []
        for item in log.items or []:
            name = item.get("name") or "unbekannt"
            qty = item.get("qty") or 0
            price = item.get("price")
            part = f"{qty}x {name}"
            if price is not None:
                part += f" ({price} CHF)"
            item_parts.append(part)

        rows.append(
            [
                log.id,
                log.created_at.isoformat(timespec="seconds") if log.created_at else "",
                log.order_id or "",
                log.total,
                " | ".join(item_parts),
                log.actor or "",
                log.user_agent or "",
            ]
        )

    headers = ["Log-ID", "Zeit", "Order-ID", "Summe (CHF)", "Artikel", "Actor", "User Agent"]
    filename = f"event-{event.id}-order-logs.csv"
    return csv_response(filename, headers, rows)


@app.route("/events/<int:event_id>/export/shot_logs.csv")
def export_shot_logs(event_id: int):
    event = Event.query.get_or_404(event_id)
    logs = ShotLog.query.filter_by(event_id=event.id).order_by(ShotLog.created_at.asc()).all()

    rows = [
        [
            log.id,
            log.created_at.isoformat(timespec="seconds") if log.created_at else "",
            log.team_name or "",
            log.amount,
            log.actor or "",
            log.user_agent or "",
        ]
        for log in logs
    ]

    headers = ["Log-ID", "Zeit", "Team", "Shots", "Actor", "User Agent"]
    filename = f"event-{event.id}-shot-logs.csv"
    return csv_response(filename, headers, rows)


@app.route("/events/<int:event_id>/export/drink_sales.csv")
def export_drink_sales(event_id: int):
    event = Event.query.get_or_404(event_id)
    sales = (
        db.session.query(DrinkSale.name, func.coalesce(func.sum(DrinkSale.quantity), 0))
        .join(Order, Order.id == DrinkSale.order_id)
        .filter(Order.event_id == event.id)
        .group_by(DrinkSale.name)
        .order_by(DrinkSale.name.asc())
        .all()
    )

    rows = [[name, quantity] for name, quantity in sales]
    headers = ["Produkt", "Menge"]
    filename = f"event-{event.id}-drink-sales.csv"
    return csv_response(filename, headers, rows)


@app.route("/admin")
def admin():
    events = Event.query.order_by(Event.created_at.desc()).all()
    active_event = get_active_event()
    default_button_presets = [button.__dict__ for button in DEFAULT_BUTTONS]
    button_map = {event.id: [btn.__dict__ for btn in resolve_button_config(event)] for event in events}
    kass_settings = {event.id: {**(event.kassensystem_settings or {}), "items": button_map[event.id]} for event in events}
    shot_settings_map = {event.id: resolve_shotcounter_settings(event) for event in events}
    event_payloads = {
        event.id: {
            "name": event.name,
            "kassensystem_enabled": event.kassensystem_enabled,
            "shotcounter_enabled": event.shotcounter_enabled,
            "shared_settings": event.shared_settings or {},
            "shotcounter_settings": shot_settings_map[event.id],
            "kassensystem_settings": kass_settings[event.id],
        }
        for event in events
    }
    
    # Get current credentials for display in template
    current_creds = credentials_manager.get_credentials()
    admin_username = current_creds.get("admin_username", "")
    has_password = bool(current_creds.get("admin_password"))
    
    return render_template(
        "admin.html",
        events=events,
        active_event=active_event,
        default_buttons=default_button_presets,
        event_buttons=button_map,
        kass_settings=kass_settings,
        event_payloads=event_payloads,
        shotcounter_defaults=DEFAULT_SHOTCOUNTER_SETTINGS,
        shot_settings_map=shot_settings_map,
        admin_username=admin_username,
        has_password=has_password,
    )


@app.route("/admin/events", methods=["POST"])
def create_event():
    name = (request.form.get("name") or "").strip()
    kassensystem_enabled = bool(request.form.get("kassensystem_enabled"))
    shotcounter_enabled = bool(request.form.get("shotcounter_enabled"))

    if not name:
        flash("Bitte einen Eventnamen angeben.", "error")
        return redirect(url_for("admin"))

    try:
        shared_settings = parse_json_field(request.form.get("shared_settings"))
        # Add auto_reload_on_add from checkbox
        # If checkbox is present (checked), it will be "on", if unchecked it won't be in form
        # For new events without this field in the form, default to True for backward compatibility
        if "auto_reload_on_add" in request.form:
            shared_settings["auto_reload_on_add"] = bool(request.form.get("auto_reload_on_add"))
        else:
            # Default to True for backward compatibility if not in form
            shared_settings["auto_reload_on_add"] = True
        
        kass_settings = validate_and_normalize_buttons(parse_json_field(request.form.get("kassensystem_settings")))
        shot_settings = validate_shotcounter_settings(parse_json_field(request.form.get("shotcounter_settings")))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("admin"))

    event = Event(
        name=name,
        kassensystem_enabled=kassensystem_enabled,
        shotcounter_enabled=shotcounter_enabled,
        shared_settings=shared_settings,
        kassensystem_settings=kass_settings,
        shotcounter_settings=shot_settings,
    )
    db.session.add(event)
    db.session.commit()
    app.logger.info("Event erstellt: %s", name)
    flash("Event wurde angelegt.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/events/<int:event_id>/update", methods=["POST"])
def update_event(event_id: int):
    event = Event.query.get_or_404(event_id)
    event.kassensystem_enabled = bool(request.form.get("kassensystem_enabled"))
    event.shotcounter_enabled = bool(request.form.get("shotcounter_enabled"))

    try:
        event.shared_settings = parse_json_field(request.form.get("shared_settings"))
        # Handle auto_reload_on_add checkbox
        # When updating an event, if checkbox is not in form, it means it was unchecked (set to False)
        # If checkbox is in form with value "on", it's checked (set to True)
        event.shared_settings["auto_reload_on_add"] = bool(request.form.get("auto_reload_on_add"))
        
        event.kassensystem_settings = validate_and_normalize_buttons(
            parse_json_field(request.form.get("kassensystem_settings"))
        )
        event.shotcounter_settings = validate_shotcounter_settings(parse_json_field(request.form.get("shotcounter_settings")))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("admin"))

    db.session.commit()
    app.logger.info("Event aktualisiert: %s", event.name)
    flash("Event wurde aktualisiert.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/events/<int:event_id>/activate", methods=["POST"])
def activate_event(event_id: int):
    event = Event.query.get_or_404(event_id)
    Event.query.update({"is_active": False})
    event.is_active = True
    event.is_archived = False
    db.session.commit()
    app.logger.info("Event aktiviert: %s", event.name)
    flash(f"Event '{event.name}' ist jetzt aktiv.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/events/<int:event_id>/archive", methods=["POST"])
def archive_event(event_id: int):
    event = Event.query.get_or_404(event_id)
    event.is_archived = True
    event.is_active = False
    db.session.commit()
    app.logger.info("Event archiviert: %s", event.name)
    flash(f"Event '{event.name}' wurde archiviert.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/credentials", methods=["POST"])
def update_credentials():
    """Route zum Aktualisieren der Admin-Credentials über das Webinterface.
    
    If credentials are already set (locked state), this route requires authentication
    through the before_request handler. If unlocked (no password set), anyone can
    set the initial credentials.
    """
    username = request.form.get("admin_username", "").strip()
    password = request.form.get("admin_password", "").strip()
    has_password = bool(credentials_manager.get_credentials().get("admin_password"))
    
    # Validate inputs
    if not username:
        flash("Benutzername darf nicht leer sein.", "error")
        return redirect(url_for("admin"))
    if not has_password and not password:
        flash("Bitte ein Passwort setzen, damit der Admin-Bereich geschützt ist.", "error")
        return redirect(url_for("admin"))
    if password and len(password) < 8:
        flash("Passwort muss mindestens 8 Zeichen lang sein.", "error")
        return redirect(url_for("admin"))
    
    # Update credentials
    success, error_message = credentials_manager.update_credentials(
        admin_username=username,
        admin_password=password if password else None
    )
    
    if success:
        app.logger.info("Admin-Credentials aktualisiert: Benutzer=%s", username)
        flash("Credentials wurden erfolgreich aktualisiert.", "success")
    else:
        error_detail = error_message or "Unbekannter Fehler."
        app.logger.error("Fehler beim Aktualisieren der Credentials: %s", error_detail)
        flash(f"Fehler beim Speichern der Credentials: {error_detail}", "error")
    
    return redirect(url_for("admin"))


# ---------------------------------------------------------------------------
# Network Management & System Update
# ---------------------------------------------------------------------------

def _run_safe_command(cmd: list[str], timeout: int = 10) -> dict:
    """
    Safely execute a whitelisted command with timeout.
    Returns dict with 'success', 'output', 'error' keys.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout.strip(),
            "error": result.stderr.strip()
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": f"Command timed out after {timeout} seconds"
        }
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": str(e)
        }


def _get_network_interface_info(interface: str) -> dict:
    """Get information about a network interface."""
    info = {
        "interface": interface,
        "exists": False,
        "ip": None,
        "netmask": None,
        "status": "down"
    }
    
    # Check if interface exists and get IP
    result = _run_safe_command(["ip", "-4", "addr", "show", interface])
    if result["success"] and result["output"]:
        info["exists"] = True
        # Parse IP address
        for line in result["output"].split("\n"):
            if "inet " in line:
                parts = line.strip().split()
                if len(parts) >= 2:
                    ip_cidr = parts[1]
                    if "/" in ip_cidr:
                        ip, cidr = ip_cidr.split("/")
                        info["ip"] = ip
                        # Convert CIDR to netmask
                        cidr_int = int(cidr)
                        mask_int = (0xffffffff >> (32 - cidr_int)) << (32 - cidr_int)
                        info["netmask"] = f"{(mask_int >> 24) & 0xff}.{(mask_int >> 16) & 0xff}.{(mask_int >> 8) & 0xff}.{mask_int & 0xff}"
            if "state UP" in line:
                info["status"] = "up"
    
    return info


def _get_wlan_info() -> dict:
    """Get WLAN interface status."""
    wlan_info = _get_network_interface_info("wlan0")
    
    # Check if connected to a network
    result = _run_safe_command(["iwgetid", "-r"])
    if result["success"] and result["output"]:
        wlan_info["ssid"] = result["output"]
    else:
        wlan_info["ssid"] = None
    
    # Get signal strength if connected
    if wlan_info.get("ssid"):
        result = _run_safe_command(["iwconfig", "wlan0"])
        if result["success"]:
            for line in result["output"].split("\n"):
                if "Signal level" in line:
                    # Extract signal level (e.g., "-50 dBm")
                    match = re.search(r'Signal level[=:](-?\d+)', line)
                    if match:
                        wlan_info["signal_level"] = match.group(1) + " dBm"
    
    return wlan_info


def _get_dhcp_leases() -> list:
    """Get active DHCP leases from dnsmasq."""
    leases = []
    # Try common locations for DHCP lease files
    lease_files = [
        "/var/lib/misc/dnsmasq.leases",  # Common on Debian/Ubuntu/Raspbian
        "/var/lib/dhcp/dnsmasq.leases",  # Alternative location
        "/var/lib/dnsmasq/dnsmasq.leases",  # Another alternative
    ]
    
    lease_file = None
    for path in lease_files:
        if os.path.exists(path):
            lease_file = path
            break
    
    if not lease_file:
        return leases
    
    try:
        with open(lease_file, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    # Format: timestamp mac ip hostname client-id
                    timestamp, mac, ip, hostname, *rest = parts
                    leases.append({
                        "mac": mac,
                        "ip": ip,
                        "hostname": hostname if hostname != "*" else "Unknown",
                    })
    except Exception as e:
        app.logger.error(f"Error reading DHCP leases: {e}")
    
    return leases


def _get_git_status() -> dict:
    """Get current git repository status."""
    git_info = {
        "branch": None,
        "commit": None,
        "commit_short": None,
        "has_changes": False,
        "behind": 0,
        "error": None
    }
    
    # Get current branch
    result = _run_safe_command(["git", "-C", app.root_path, "rev-parse", "--abbrev-ref", "HEAD"])
    if result["success"]:
        git_info["branch"] = result["output"]
    
    # Get current commit
    result = _run_safe_command(["git", "-C", app.root_path, "rev-parse", "HEAD"])
    if result["success"]:
        git_info["commit"] = result["output"]
        git_info["commit_short"] = result["output"][:7]
    
    # Check for uncommitted changes
    result = _run_safe_command(["git", "-C", app.root_path, "status", "--porcelain"])
    if result["success"]:
        git_info["has_changes"] = bool(result["output"])
    
    # Check if behind remote
    result = _run_safe_command(["git", "-C", app.root_path, "fetch", "--dry-run"], timeout=30)
    result = _run_safe_command(["git", "-C", app.root_path, "rev-list", "--count", "HEAD..@{upstream}"])
    if result["success"] and result["output"].isdigit():
        git_info["behind"] = int(result["output"])
    
    return git_info


@app.route("/admin/network")
def admin_network():
    """Get network status information."""
    eth0_info = _get_network_interface_info("eth0")
    wlan0_info = _get_wlan_info()
    dhcp_leases = _get_dhcp_leases()
    
    return jsonify({
        "eth0": eth0_info,
        "wlan0": wlan0_info,
        "dhcp_leases": dhcp_leases
    })


@app.route("/admin/network/wifi/scan")
def admin_wifi_scan():
    """Scan for available WiFi networks."""
    networks = []
    
    # Scan for networks
    result = _run_safe_command(["iwlist", "wlan0", "scan"], timeout=15)
    if not result["success"]:
        return jsonify({"success": False, "error": result["error"]})
    
    # Parse scan results
    current_ssid = None
    current_quality = None
    current_encryption = "Open"
    
    for line in result["output"].split("\n"):
        line = line.strip()
        if "ESSID:" in line:
            match = re.search(r'ESSID:"([^"]+)"', line)
            if match:
                current_ssid = match.group(1)
        elif "Quality=" in line:
            match = re.search(r'Quality=(\d+)/(\d+)', line)
            if match:
                quality = int(match.group(1))
                max_quality = int(match.group(2))
                current_quality = int((quality / max_quality) * 100)
        elif "Encryption key:" in line:
            if "on" in line:
                current_encryption = "Encrypted"
            else:
                current_encryption = "Open"
        
        # When we have collected info for a network, add it
        if current_ssid and "IE: IEEE 802.11i/WPA2" in line:
            current_encryption = "WPA2"
        
        # Cell separator or end - save current network
        if current_ssid and ("Cell" in line or line == ""):
            networks.append({
                "ssid": current_ssid,
                "quality": current_quality or 0,
                "encryption": current_encryption
            })
            current_ssid = None
            current_quality = None
            current_encryption = "Open"
    
    # Add last network if exists
    if current_ssid:
        networks.append({
            "ssid": current_ssid,
            "quality": current_quality or 0,
            "encryption": current_encryption
        })
    
    # Remove duplicates and sort by quality
    seen_ssids = set()
    unique_networks = []
    for network in sorted(networks, key=lambda x: x["quality"], reverse=True):
        if network["ssid"] not in seen_ssids:
            seen_ssids.add(network["ssid"])
            unique_networks.append(network)
    
    return jsonify({"success": True, "networks": unique_networks})


@app.route("/admin/network/wifi/connect", methods=["POST"])
def admin_wifi_connect():
    """Connect to a WiFi network."""
    ssid = request.form.get("ssid", "").strip()
    password = request.form.get("password", "").strip()
    
    if not ssid:
        return jsonify({"success": False, "error": "SSID ist erforderlich"})
    
    if len(ssid) > 32:
        return jsonify({"success": False, "error": "SSID zu lang (max 32 Zeichen)"})
    
    # Validate SSID contains only safe characters (printable ASCII)
    if not all(32 <= ord(c) <= 126 for c in ssid):
        return jsonify({"success": False, "error": "SSID enthält ungültige Zeichen"})
    
    if password and len(password) < 8:
        return jsonify({"success": False, "error": "Passwort muss mindestens 8 Zeichen haben"})
    
    # Use the pi_manage.sh script if available
    script_path = Path(app.root_path) / "scripts" / "pi_manage.sh"
    if script_path.exists() and password:
        result = _run_safe_command(["sudo", str(script_path), "wifi-add", ssid, password], timeout=30)
        if result["success"]:
            # Try to bring up the interface
            _run_safe_command(["sudo", str(script_path), "wifi-up"], timeout=10)
            app.logger.info(f"WLAN verbunden: {ssid}")
            return jsonify({"success": True, "message": f"Verbindung zu '{ssid}' wird hergestellt..."})
        else:
            return jsonify({"success": False, "error": result["error"] or "Fehler beim Verbinden"})
    else:
        return jsonify({"success": False, "error": "WiFi-Verwaltung nicht verfügbar"})


@app.route("/admin/system/git-status")
def admin_git_status():
    """Get git repository status."""
    git_info = _get_git_status()
    return jsonify(git_info)


@app.route("/admin/system/git-update", methods=["POST"])
def admin_git_update():
    """Pull latest changes from git and restart service."""
    # Check if there are uncommitted changes
    git_info = _get_git_status()
    if git_info.get("has_changes"):
        return jsonify({
            "success": False,
            "error": "Es gibt nicht committete Änderungen. Bitte zuerst committen oder verwerfen."
        })
    
    # Use the pi_manage.sh script if available
    script_path = Path(app.root_path) / "scripts" / "pi_manage.sh"
    if not script_path.exists():
        return jsonify({"success": False, "error": "Update-Script nicht gefunden"})
    
    # Validate branch name contains only safe characters
    branch = git_info.get("branch", "main")
    if not re.match(r'^[a-zA-Z0-9/_.-]+$', branch):
        return jsonify({
            "success": False,
            "error": "Ungültiger Branch-Name"
        })
    
    # Trigger the privileged update service (runs the update script as root).
    # Use sudo with a narrow NOPASSWD sudoers entry to avoid interactive
    # polkit prompts in the web context.
    result = _run_safe_command(["sudo", "systemctl", "start", "kassensystem-update.service"], timeout=300)
    
    if result["success"]:
        app.logger.info("Git Update erfolgreich durchgeführt")
        return jsonify({
            "success": True,
            "message": "Update erfolgreich. Service wird neu gestartet..."
        })
    else:
        app.logger.error(f"Git Update fehlgeschlagen: {result['error']}")
        return jsonify({
            "success": False,
            "error": result["error"] or "Update fehlgeschlagen"
        })


# ---------------------------------------------------------------------------
# Kassensystem
# ---------------------------------------------------------------------------
def _get_cart_data(event):
    """Helper function to get cart data for an event."""
    buttons = resolve_button_config(event)
    items = session.get(cart_key(event), [])
    prices = {button.name: button.price for button in buttons}
    total = sum(prices.get(item, 0) for item in items)
    grouped = Counter(items).items()
    detailed_items = [
        {"name": name, "qty": qty, "price": prices.get(name, 0), "line_total": prices.get(name, 0) * qty}
        for name, qty in grouped
    ]
    return {
        "items": detailed_items,
        "total": total,
        "item_count": len(items)
    }


@app.route("/cashier")
def cashier():
    event = require_active_event(kassensystem=True)
    buttons = resolve_button_config(event)
    cart_data = _get_cart_data(event)
    
    # Group buttons by category
    buttons_by_category = {}
    for button in buttons:
        category = button.category
        if category not in buttons_by_category:
            buttons_by_category[category] = []
        buttons_by_category[category].append(button)
    
    # Get auto_reload setting from shared_settings (default to True for backward compatibility)
    auto_reload = event.shared_settings.get("auto_reload_on_add", True) if event.shared_settings else True
    
    return render_template(
        "cashier.html", 
        buttons=buttons, 
        buttons_by_category=buttons_by_category, 
        items=cart_data["items"], 
        total=cart_data["total"], 
        event=event,
        auto_reload=auto_reload
    )


@app.route("/cashier/add")
def add_item():
    event = require_active_event(kassensystem=True)
    buttons = resolve_button_config(event)
    prices = {button.name: button.price for button in buttons}
    name = request.args.get("name")
    if name and name in prices:
        items = session.get(cart_key(event), [])
        items.append(name)
        session[cart_key(event)] = items
        app.logger.info("Artikel hinzugefügt: %s (Event %s)", name, event.name)
    
    # Check if this is an AJAX request (wants JSON response)
    if request.args.get("ajax") == "1" or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        cart_data = _get_cart_data(event)
        return jsonify({
            "success": True,
            "cart": cart_data
        })
    
    return redirect(url_for("cashier"))


@app.route("/cashier/remove_last")
def remove_last():
    event = require_active_event(kassensystem=True)
    items = session.get(cart_key(event), [])
    if items:
        removed = items.pop()
        session[cart_key(event)] = items
        app.logger.info("Artikel entfernt: %s (Event %s)", removed, event.name)
    
    # Check if this is an AJAX request (wants JSON response)
    if request.args.get("ajax") == "1" or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        cart_data = _get_cart_data(event)
        return jsonify({
            "success": True,
            "cart": cart_data
        })
    
    return redirect(url_for("cashier"))


@app.route("/cashier/checkout")
def checkout():
    event = require_active_event(kassensystem=True)
    items = session.get(cart_key(event), [])
    prices = {btn.name: btn.price for btn in resolve_button_config(event)}
    if items:
        total = sum(prices.get(item, 0) for item in items)
        order = Order(event_id=event.id, total=total)
        db.session.add(order)
        db.session.commit()

        for item_name in items:
            db.session.add(OrderItem(order_id=order.id, name=item_name, price=prices.get(item_name, 0)))

        aggregated_items = []
        for name, qty in Counter(items).items():
            price = prices.get(name, 0)
            aggregated_items.append({"name": name, "qty": qty, "price": price})
            db.session.add(DrinkSale(order_id=order.id, name=name, quantity=qty))

        db.session.commit()
        actor, user_agent = resolve_actor()
        db.session.add(
            OrderLog(
                event_id=event.id,
                order_id=order.id,
                total=total,
                items=aggregated_items,
                actor=actor,
                user_agent=user_agent,
            )
        )
        db.session.commit()
        app.logger.info("Bestellung abgeschlossen (Event %s, Summe %s)", event.name, total)

    session[cart_key(event)] = []
    return redirect(url_for("cashier"))


@app.route("/cashier/stats")
def cashier_stats():
    event = require_active_event(kassensystem=True)
    revenue = (
        db.session.query(func.coalesce(func.sum(Order.total), 0))
        .filter(Order.event_id == event.id)
        .scalar()
        or 0
    )
    count = db.session.query(func.count(Order.id)).filter(Order.event_id == event.id).scalar() or 0
    sales = (
        db.session.query(DrinkSale.name, func.sum(DrinkSale.quantity))
        .join(Order, Order.id == DrinkSale.order_id)
        .filter(Order.event_id == event.id)
        .group_by(DrinkSale.name)
        .all()
    )
    return render_template("cashier_stats.html", revenue=revenue, count=count, sales=sales, event=event)


# ---------------------------------------------------------------------------
# Shotcounter
# ---------------------------------------------------------------------------
@app.route("/shotcounter")
def shotcounter():
    event = require_active_event(shotcounter=True)
    teams = Team.query.filter_by(event_id=event.id).order_by(Team.shots.desc(), Team.name.asc()).all()
    return render_template("shotcounter.html", teams=teams, event=event)


@app.route("/shotcounter/touch")
def shotcounter_touch():
    event = require_active_event(shotcounter=True)
    teams = Team.query.filter_by(event_id=event.id).order_by(Team.name.asc()).all()
    return render_template("shotcounter_touch.html", teams=teams, event=event)


def _leaderboard_limit(default: int) -> int:
    """Sanitizes the requested leaderboard size."""

    raw = request.args.get("limit", type=int)
    return _sanitize_leaderboard_limit(raw, default)


TEAM_NAME_PATTERN = re.compile(r"^[A-Za-z0-9ÄÖÜäöüß .,'&()/\\-]+$")


def _validate_team_name(name: str) -> tuple[bool, str | None]:
    """Validates the team name to avoid characters that fail to render."""

    if not TEAM_NAME_PATTERN.match(name):
        allowed = "Buchstaben, Zahlen, Leerzeichen sowie . , - _ & / ( ) '"
        return False, f"Ungültige Zeichen im Teamnamen. Erlaubt sind: {allowed}."
    return True, None


def _top_teams(event: Event, limit: int) -> List[Team]:
    return (
        Team.query.filter_by(event_id=event.id)
        .order_by(Team.shots.desc(), Team.name.asc())
        .limit(limit)
        .all()
    )


def _serialize_teams(teams: Iterable[Team]) -> List[Dict[str, int | str]]:
    return [{"id": team.id, "name": team.name, "shots": team.shots} for team in teams]


def _redirect_target(default: str = "shotcounter") -> str:
    """Returns a safe redirect target within the app."""

    candidate = request.form.get("next") or request.args.get("next")
    if candidate and isinstance(candidate, str) and candidate.startswith("/"):
        return candidate
    return url_for(default)


@app.route("/shotcounter/leaderboard")
def shotcounter_leaderboard():
    event = require_active_event(shotcounter=True)
    shot_settings = resolve_shotcounter_settings(event)
    limit = _leaderboard_limit(int(shot_settings["leaderboard_limit"]))
    teams = _top_teams(event, limit)
    return render_template(
        "shotcounter_leaderboard.html",
        teams=_serialize_teams(teams),
        event=event,
        limit=limit,
        shot_settings=shot_settings,
    )


@app.route("/shotcounter/leaderboard/data")
def shotcounter_leaderboard_data():
    event = require_active_event(shotcounter=True)
    shot_settings = resolve_shotcounter_settings(event)
    limit = _leaderboard_limit(int(shot_settings["leaderboard_limit"]))
    teams = _top_teams(event, limit)
    payload = {
        "event": {"id": event.id, "name": event.name},
        "limit": limit,
        "teams": _serialize_teams(teams),
    }
    return payload


@app.route("/shotcounter/teams", methods=["POST"])
def add_team():
    event = require_active_event(shotcounter=True)
    name = (request.form.get("team_name") or "").strip()
    if not name:
        flash("Bitte einen Teamnamen angeben.", "error")
        return redirect(_redirect_target())

    is_valid, error = _validate_team_name(name)
    if not is_valid:
        flash(error, "error")
        return redirect(_redirect_target())

    if Team.query.filter_by(event_id=event.id, name=name).first():
        flash("Team existiert bereits.", "error")
        return redirect(_redirect_target())

    db.session.add(Team(event_id=event.id, name=name, shots=0))
    db.session.commit()
    app.logger.info("Team hinzugefügt: %s (Event %s)", name, event.name)
    flash("Team hinzugefügt.", "success")
    return redirect(_redirect_target())


@app.route("/shotcounter/shots", methods=["POST"])
def add_shots():
    event = require_active_event(shotcounter=True)
    team_id = request.form.get("team_id", type=int)
    amount = request.form.get("amount", type=int, default=1)

    if not team_id:
        flash("Kein Team gewählt.", "error")
        return redirect(_redirect_target())

    team = Team.query.filter_by(id=team_id, event_id=event.id).first()
    if not team:
        flash("Team nicht gefunden.", "error")
        return redirect(_redirect_target())

    if amount is None or amount <= 0:
        flash("Bitte eine gültige Anzahl Shots angeben.", "error")
        return redirect(_redirect_target())

    team.shots += amount
    db.session.commit()
    actor, user_agent = resolve_actor()
    db.session.add(
        ShotLog(
            event_id=event.id,
            team_id=team.id,
            team_name=team.name,
            amount=amount,
            actor=actor,
            user_agent=user_agent,
        )
    )
    db.session.commit()
    app.logger.info("%s Shots zu Team %s hinzugefügt (Event %s)", amount, team.name, event.name)
    flash("Shots verbucht.", "success")
    return redirect(_redirect_target())


@app.route("/shotcounter/teams/<int:team_id>/update", methods=["POST"])
def update_team(team_id: int):
    event = require_active_event(shotcounter=True)
    team = Team.query.filter_by(id=team_id, event_id=event.id).first()
    if not team:
        flash("Team nicht gefunden.", "error")
        return redirect(_redirect_target())

    new_name = (request.form.get("team_name") or "").strip()
    new_shots = request.form.get("shots", type=int)

    if new_name:
        is_valid, error = _validate_team_name(new_name)
        if not is_valid:
            flash(error, "error")
            return redirect(_redirect_target())
        if new_name != team.name and Team.query.filter_by(event_id=event.id, name=new_name).first():
            flash("Teamname bereits vergeben.", "error")
            return redirect(_redirect_target())
        team.name = new_name

    if new_shots is not None:
        if new_shots < 0:
            flash("Shots müssen 0 oder höher sein.", "error")
            return redirect(_redirect_target())
        team.shots = new_shots

    db.session.commit()
    flash("Team aktualisiert.", "success")
    return redirect(_redirect_target())


@app.route("/shotcounter/teams/<int:team_id>/delete", methods=["POST"])
def delete_team(team_id: int):
    event = require_active_event(shotcounter=True)
    team = Team.query.filter_by(id=team_id, event_id=event.id).first()
    if not team:
        flash("Team nicht gefunden.", "error")
        return redirect(_redirect_target())

    db.session.delete(team)
    db.session.commit()
    flash("Team gelöscht.", "success")
    return redirect(_redirect_target())


# ---------------------------------------------------------------------------
# File Upload Routes
# ---------------------------------------------------------------------------
@app.route("/uploads/<filename>")
def uploaded_file(filename: str):
    """Serve uploaded files."""
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/admin/events/<int:event_id>/background", methods=["POST"])
def upload_background(event_id: int):
    """Upload or delete background image for an event."""
    event = Event.query.get_or_404(event_id)
    
    # Check if user wants to delete the background
    if request.form.get("delete_background"):
        shot_settings = event.shotcounter_settings or {}
        old_image = shot_settings.get("background_image")
        if old_image:
            delete_background_image(old_image)
            shot_settings.pop("background_image", None)
            event.shotcounter_settings = shot_settings
            attributes.flag_modified(event, "shotcounter_settings")
            db.session.commit()
            flash("Hintergrundbild wurde entfernt.", "success")
        return redirect(url_for("admin"))
    
    # Handle file upload
    if "background_image" not in request.files:
        flash("Keine Datei ausgewählt.", "error")
        return redirect(url_for("admin"))
    
    file = request.files["background_image"]
    if file.filename == "":
        flash("Keine Datei ausgewählt.", "error")
        return redirect(url_for("admin"))
    
    if not allowed_file(file.filename):
        flash(
            f"Ungültiger Dateityp. Erlaubt sind: {', '.join(ALLOWED_EXTENSIONS)}",
            "error"
        )
        return redirect(url_for("admin"))
    
    # Delete old background image if exists
    shot_settings = event.shotcounter_settings or {}
    old_image = shot_settings.get("background_image")
    if old_image:
        delete_background_image(old_image)
    
    # Save new image
    filename = save_background_image(file, event_id)
    if filename:
        shot_settings["background_image"] = filename
        event.shotcounter_settings = shot_settings
        attributes.flag_modified(event, "shotcounter_settings")
        db.session.commit()
        app.logger.info("Hintergrundbild hochgeladen für Event %s: %s", event.name, filename)
        flash("Hintergrundbild wurde hochgeladen.", "success")
    else:
        flash("Fehler beim Hochladen des Bildes.", "error")
    
    return redirect(url_for("admin"))



# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
