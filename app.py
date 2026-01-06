"""Zentrale Steuerung für Kassensystem und Shotcounter.

Die Anwendung bündelt zwei eigenständige Subsysteme (Kasse & Shotcounter)
unter einer gemeinsamen Event-Verwaltung. Im Adminbereich können Events
angelegt, aktiviert, archiviert und mit eigenen Einstellungen versehen
werden. Pro Event lässt sich separat steuern, ob Kassensystem oder
Shotcounter aktiv sein sollen.
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Iterable, List

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func


# ---------------------------------------------------------------------------
# App- und DB-Konfiguration
# ---------------------------------------------------------------------------
app = Flask(__name__, instance_relative_config=True)

# Ensure a usable secret key even when Flask's default (None) is present.
secret_key = os.environ.get("SECRET_KEY") or app.config.get("SECRET_KEY") or "dev-secret-key"
app.config["SECRET_KEY"] = secret_key
app.config.setdefault("SQLALCHEMY_DATABASE_URI", f"sqlite:///{Path(app.instance_path) / 'app.db'}")
app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
app.config.setdefault("SESSION_TYPE", "filesystem")

Path(app.instance_path).mkdir(parents=True, exist_ok=True)
db = SQLAlchemy(app)


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


with app.app_context():
    db.create_all()


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


def parse_json_field(raw_value: str | None) -> Dict:
    if not raw_value:
        return {}
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON ungültig: {exc}")


def get_active_event() -> Event | None:
    return Event.query.filter_by(is_active=True, is_archived=False).first()


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

    if not normalized:
        raise ValueError("Mindestens ein Produkt erforderlich.")

    sanitized = {k: v for k, v in settings.items() if k != "items"}
    sanitized["items"] = normalized
    return sanitized


def cart_key(event: Event) -> str:
    return f"cart_{event.id}"


# ---------------------------------------------------------------------------
# Routen: Dashboard & Admin
# ---------------------------------------------------------------------------
@app.route("/")
def dashboard():
    active_event = get_active_event()
    events = Event.query.order_by(Event.created_at.desc()).all()
    return render_template("dashboard.html", active_event=active_event, events=events)


@app.route("/admin")
def admin():
    events = Event.query.order_by(Event.created_at.desc()).all()
    active_event = get_active_event()
    default_button_presets = [button.__dict__ for button in DEFAULT_BUTTONS]
    button_map = {event.id: [btn.__dict__ for btn in resolve_button_config(event)] for event in events}
    kass_settings = {event.id: {**(event.kassensystem_settings or {}), "items": button_map[event.id]} for event in events}
    return render_template(
        "admin.html",
        events=events,
        active_event=active_event,
        default_buttons=default_button_presets,
        event_buttons=button_map,
        kass_settings=kass_settings,
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
        shot_settings = parse_json_field(request.form.get("shotcounter_settings"))
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
        event.shotcounter_settings = parse_json_field(request.form.get("shotcounter_settings"))
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
    return render_template("cashier.html", buttons=buttons, items=grouped, total=total, event=event)


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

        for name, qty in Counter(items).items():
            db.session.add(DrinkSale(order_id=order.id, name=name, quantity=qty))

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


def _leaderboard_limit(default: int = 10) -> int:
    """Sanitizes the requested leaderboard size."""

    raw = request.args.get("limit", default=default, type=int)
    if not raw or raw < 1:
        return default
    return min(raw, 50)


def _top_teams(event: Event, limit: int) -> List[Team]:
    return (
        Team.query.filter_by(event_id=event.id)
        .order_by(Team.shots.desc(), Team.name.asc())
        .limit(limit)
        .all()
    )


def _serialize_teams(teams: Iterable[Team]) -> List[Dict[str, int | str]]:
    return [{"id": team.id, "name": team.name, "shots": team.shots} for team in teams]


@app.route("/shotcounter/leaderboard")
def shotcounter_leaderboard():
    event = require_active_event(shotcounter=True)
    limit = _leaderboard_limit()
    teams = _top_teams(event, limit)
    return render_template(
        "shotcounter_leaderboard.html",
        teams=_serialize_teams(teams),
        event=event,
        limit=limit,
    )


@app.route("/shotcounter/leaderboard/data")
def shotcounter_leaderboard_data():
    event = require_active_event(shotcounter=True)
    limit = _leaderboard_limit()
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
        return redirect(url_for("shotcounter"))

    if Team.query.filter_by(event_id=event.id, name=name).first():
        flash("Team existiert bereits.", "error")
        return redirect(url_for("shotcounter"))

    db.session.add(Team(event_id=event.id, name=name, shots=0))
    db.session.commit()
    app.logger.info("Team hinzugefügt: %s (Event %s)", name, event.name)
    flash("Team hinzugefügt.", "success")
    return redirect(url_for("shotcounter"))


@app.route("/shotcounter/shots", methods=["POST"])
def add_shots():
    event = require_active_event(shotcounter=True)
    team_id = request.form.get("team_id", type=int)
    amount = request.form.get("amount", type=int, default=1)

    if not team_id:
        flash("Kein Team gewählt.", "error")
        return redirect(url_for("shotcounter"))

    team = Team.query.filter_by(id=team_id, event_id=event.id).first()
    if not team:
        flash("Team nicht gefunden.", "error")
        return redirect(url_for("shotcounter"))

    if amount is None or amount <= 0:
        flash("Bitte eine gültige Anzahl Shots angeben.", "error")
        return redirect(url_for("shotcounter"))

    team.shots += amount
    db.session.commit()
    app.logger.info("%s Shots zu Team %s hinzugefügt (Event %s)", amount, team.name, event.name)
    flash("Shots verbucht.", "success")
    return redirect(url_for("shotcounter"))


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
