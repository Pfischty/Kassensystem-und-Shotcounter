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
import sqlite3
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
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_migrate import Migrate
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, func, text
from sqlalchemy.engine import Engine

from credentials_manager import credentials_manager


# ---------------------------------------------------------------------------
# App- und DB-Konfiguration
# ---------------------------------------------------------------------------
app = Flask(__name__, instance_relative_config=True)

is_production = os.environ.get("FLASK_ENV") == "production" or os.environ.get("APP_ENV") == "production"

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


DEFAULT_BUTTONS: List[ButtonConfig] = [
    ButtonConfig(
        name="Süssgetränke",
        label="Süssgetränke",
        price=6,
        css_class="suess",
        color="#1f2a44",
    ),
    ButtonConfig(
        name="Bier",
        label="Bier / Mate / Red Bull / Smirnoff",
        price=7,
        css_class="bier",
        color="#193f8a",
    ),
    ButtonConfig(name="Wein", label="Wein", price=7, css_class="wein", color="#8a1f6f"),
    ButtonConfig(
        name="Weinflasche 0.7",
        label="Weinflasche",
        price=22,
        css_class="flasche",
        color="#5b2d30",
    ),
    ButtonConfig(name="Drink 10", label="Drink 10", price=12, css_class="gross", color="#2e4c3d"),
    ButtonConfig(name="Depot rein", label="Depot rein", price=-2, css_class="depot", color="#374151"),
    ButtonConfig(
        name="Weinglassdepot",
        label="Weinglas Depot",
        price=2,
        css_class="Weinglassdepot",
        color="#3f2d67",
    ),
    ButtonConfig(name="Kaffee", label="Kaffee", price=3, css_class="kaffee", color="#4b3322"),
    ButtonConfig(name="Shot", label="Shot", price=5, css_class="shot", color="#7a1f2a"),
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
    
    # Validate inputs
    if not username:
        flash("Benutzername darf nicht leer sein.", "error")
        return redirect(url_for("admin"))
    
    # Update credentials
    success = credentials_manager.update_credentials(
        admin_username=username,
        admin_password=password if password else None
    )
    
    if success:
        app.logger.info("Admin-Credentials aktualisiert: Benutzer=%s", username)
        flash("Credentials wurden erfolgreich aktualisiert.", "success")
    else:
        app.logger.error("Fehler beim Aktualisieren der Credentials")
        flash("Fehler beim Speichern der Credentials.", "error")
    
    return redirect(url_for("admin"))


# ---------------------------------------------------------------------------
# Kassensystem
# ---------------------------------------------------------------------------
@app.route("/cashier")
def cashier():
    event = require_active_event(kassensystem=True)
    buttons = resolve_button_config(event)
    items = session.get(cart_key(event), [])
    prices = {button.name: button.price for button in buttons}
    total = sum(prices.get(item, 0) for item in items)
    grouped = Counter(items).items()
    detailed_items = [
        {"name": name, "qty": qty, "price": prices.get(name, 0), "line_total": prices.get(name, 0) * qty}
        for name, qty in grouped
    ]
    return render_template(
        "cashier.html", buttons=buttons, items=detailed_items, total=total, event=event
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
    return redirect(url_for("cashier"))


@app.route("/cashier/remove_last")
def remove_last():
    event = require_active_event(kassensystem=True)
    items = session.get(cart_key(event), [])
    if items:
        removed = items.pop()
        session[cart_key(event)] = items
        app.logger.info("Artikel entfernt: %s (Event %s)", removed, event.name)
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
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
