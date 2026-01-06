import json
from pathlib import Path
from collections import Counter
from datetime import datetime
from flask import Flask, redirect, render_template, request, session, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_session import Session
from sqlalchemy import func

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = BASE_DIR / "kassensystem_config.json"
EXAMPLE_CONFIG_PATH = BASE_DIR / "kassensystem_config.example.json"

app = Flask(__name__)
app.secret_key = b'gskjd%hsgd82jsd'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{INSTANCE_DIR / 'teamliste.db'}"
app.config['SESSION_TYPE'] = 'filesystem'  # Session-Daten auf dem Server speichern
db = SQLAlchemy(app)
socketio = SocketIO(app, manage_session=True)
Session(app)

class teamliste(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, unique=False, nullable=False)
    team = db.Column(db.String(150), unique=True, nullable=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    total = db.Column(db.Integer, nullable=False)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)

    order = db.relationship("Order", backref=db.backref("items", lazy=True))

class DrinkSale(db.Model):
    """Aggregierte Stückzahlen pro Getränk und Bestellung"""

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, default=0, nullable=False)

    order = db.relationship("Order", backref=db.backref("drink_sales", lazy=True))

with app.app_context():
    db.create_all()

DEFAULT_CONFIG = {
    "items": [
        {"name": "Süssgetränke", "label": "Süssgetränke", "price": 6, "css_class": "suess"},
        {
            "name": "Bier",
            "label": "Bier / Mate / Red Bull / Smirnoff",
            "price": 7,
            "css_class": "bier",
        },
        {"name": "Wein", "label": "Wein", "price": 7, "css_class": "wein"},
        {"name": "Weinflasche 0.7", "label": "Weinflasche", "price": 22, "css_class": "flasche"},
        {"name": "Drink 10", "label": "Drink 10", "price": 12, "css_class": "gross"},
        {"name": "Depot rein", "label": "Depot rein", "price": -2, "css_class": "depot"},
        {"name": "Weinglassdepot", "label": "Weinglas Depot", "price": 2, "css_class": "Weinglassdepot"},
        {"name": "Kaffee", "label": "Kaffee", "price": 3, "css_class": "kaffee"},
        {"name": "Shot", "label": "Shot", "price": 5, "css_class": "shot"},
    ]
}

def load_button_config() -> dict:
    """Load button and price configuration from JSON, fall back to defaults."""
    for candidate in (CONFIG_PATH, EXAMPLE_CONFIG_PATH):
        if candidate.exists():
            try:
                with candidate.open("r", encoding="utf-8") as config_file:
                    return json.load(config_file)
            except (OSError, json.JSONDecodeError):
                continue
    return DEFAULT_CONFIG.copy()


button_config = load_button_config()
ITEM_BUTTONS = button_config.get("items", DEFAULT_CONFIG["items"])
PRICES = {item["name"]: item["price"] for item in ITEM_BUTTONS}

@app.route('/registration', methods=('GET', 'POST'))
def registration():
    message = ""
    if request.method == 'POST':
        name = request.form["Teamname"]
        if not name:
            message = "Bitte gebe einen gültigen Namen ein"
        if not message:
            team_item = teamliste(team=name, score=0)
            db.session.add(team_item)
            db.session.commit()
            message = "Team wurde erfolgreich hinzugefügt."
            socketio.emit('update_leaderboard', namespace='/', to=None)
    return render_template('registration.html', message=message)

@app.route('/punkte', methods=('GET', 'POST'))
def punkte():
    if request.method == 'POST':
        team_name = request.form["Team"]
        punkte = request.form["number"]
        if not team_name:
            session['message'] = "Bitte ein Team angeben"
        elif not punkte.isnumeric():
            session['message'] = "Bitte eine Zahl angeben"
        else:
            team_item = teamliste.query.filter_by(team=team_name).first()
            if team_item:
                team_item.score += int(punkte)
                db.session.commit()
                session['message'] = f"{punkte} Punkte wurden zu {team_name} hinzugefügt."
                
                # WebSocket-Ereignis senden
                socketio.emit('update_leaderboard', namespace='/', to=None)
            else:
                session['message'] = "Team nicht gefunden."
        return redirect(url_for('punkte'))

    message = session.pop('message', '')
    teams = teamliste.query.all()
    return render_template('punkte.html', message=message, teams=teams)

@app.route('/leaderboard')
def leaderboard():
    teams = teamliste.query.order_by(teamliste.score.desc()).all()
    return render_template('leaderboard.html', teams=teams)

@app.route('/admin', methods=('GET', 'POST'))
def admin():
    teams = db.session.execute(
        db.select(teamliste).order_by(teamliste.score)).scalars()
    return render_template('admin.html', teams=teams) 

@app.route('/team/delete/<id>')
def loescher(id):
    grocery = teamliste.query.filter_by(id=id).first()
    if grocery == None:
        abort(404)
    else:
        db.session.delete(grocery)
        db.session.commit()
        return redirect(url_for("admin"))

@app.route('/team/update/<id>', methods=('GET', 'POST'))
def update(id):
    message = ''
    teams = teamliste.query.filter_by(id=id).first()
    if teams == None:
        abort(404)
    if request.method == 'POST':
        message = ''
        score = request.form["score"]
        teamname = request.form["teamname"]

        if not score.isnumeric():
            message = "Bitte geben Sie bei Anzahl eine Zahl ein."
            return render_template('update.html', id=id, message=message)
        if not teamname: 
            message = "Bitte geben Sie bei der Beschreibung einen Text ein."
        if not message:
            teams.score = score
            teams.team = teamname
            db.session.commit()
            return redirect(url_for("admin"))        

    return render_template('update.html', id=id, teams=teams, message=message)

@app.route('/preisliste')
def preisliste():
    return render_template('Preisliste.html')

@app.route('/Liste')
def liste():
    return render_template('index.html')
@app.route('/manage', methods=('GET', 'POST'))
def manage():
    teams = teamliste.query.all()
    if request.method == 'POST':
        action = request.form.get('action')
        message = ""
        if action == 'register':
            # Registrierung eines neuen Teams
            name = request.form.get("Teamname")
            if not name:
                message = "Bitte geben Sie einen gültigen Namen ein."
            else:
                existing_team = teamliste.query.filter_by(team=name).first()
                if existing_team:
                    message = "Team existiert bereits."
                else:
                    team_item = teamliste(team=name, score=0)
                    db.session.add(team_item)
                    db.session.commit()
                    message = "Team wurde erfolgreich hinzugefügt."
                    # WebSocket-Ereignis senden
                    socketio.emit('update_leaderboard')
        elif action == 'add_points':
            # Punkte zu einem Team hinzufügen
            team_name = request.form.get("Team")
            punkte = request.form.get("number")
            if not team_name:
                message = "Bitte ein Team angeben."
            elif not punkte or not punkte.isnumeric():
                message = "Bitte eine gültige Zahl angeben."
            else:
                team_item = teamliste.query.filter_by(team=team_name).first()
                if team_item:
                    team_item.score += int(punkte)
                    db.session.commit()
                    message = f"{punkte} Punkte wurden zu {team_name} hinzugefügt."
                    # WebSocket-Ereignis senden
                    socketio.emit('update_leaderboard')
                else:
                    message = "Team nicht gefunden."
        elif action == 'admin_update':
            # Teamdaten aktualisieren
            team_id = request.form.get("team_id")
            teamname = request.form.get("teamname")
            score = request.form.get("score")
            if not team_id or not teamname or not score:
                message = "Alle Felder müssen ausgefüllt werden."
            elif not score.isnumeric():
                message = "Punkte müssen eine Zahl sein."
            else:
                team = teamliste.query.get(team_id)
                if team:
                    team.team = teamname
                    team.score = int(score)
                    db.session.commit()
                    message = "Team wurde aktualisiert."
                    socketio.emit('update_leaderboard')
                else:
                    message = "Team nicht gefunden."
        elif action == 'admin_delete':
            # Team löschen
            team_id = request.form.get("team_id")
            team = teamliste.query.get(team_id)
            if team:
                db.session.delete(team)
                db.session.commit()
                message = "Team wurde gelöscht."
                socketio.emit('update_leaderboard')
            else:
                message = "Team nicht gefunden."
        # Nachricht in der Session speichern und Weiterleitung zur Verhinderung von doppelten Aktionen
        session['message'] = message
        return redirect(url_for('manage'))
    # GET-Anfrage
    message = session.pop('message', '')
    teams = teamliste.query.all()
    return render_template('manage.html', message=message, teams=teams)

@app.route("/")
def index():
    """Startseite mit der Bestell-Liste (zusammengefasst) und Gesamtbetrag."""
    items = session.get('items', [])
    total_price = sum(PRICES.get(item, 0) for item in items)
    # Artikel zusammenfassen, z.B. 2x Bier
    counts = Counter(items)
    grouped_items = list(counts.items())  # [(artikel, anzahl), ...]

    return render_template(
        "Kasse.html",
        items=grouped_items,
        total=total_price,
        buttons=ITEM_BUTTONS,
    )

@app.route("/add")
def add_item():
    """Fügt einen Artikel zur Bestellung hinzu."""
    name = request.args.get('name')
    if name:
        items = session.get('items', [])
        items.append(name)
        session['items'] = items
    return redirect(url_for('index'))

@app.route("/remove_last")
def remove_last():
    """Entfernt den zuletzt hinzugefügten Artikel."""
    items = session.get('items', [])
    if items:
        items.pop()
        session['items'] = items
    return redirect(url_for('index'))

@app.route("/clear_order")
def clear_order():
    """Bestellung abschliessen, in DB sichern, Zähler hochzählen"""
    items = session.get("items", [])
    if items:
        total_price = sum(PRICES.get(item, 0) for item in items)
        order = Order(total=total_price)
        db.session.add(order)
        db.session.commit()

        for item_name in items:
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    name=item_name,
                    price=PRICES.get(item_name, 0),
                )
            )

        for name, qty in Counter(items).items():
            db.session.add(DrinkSale(order_id=order.id, name=name, quantity=qty))
        db.session.commit()

    session["items"] = []
    return redirect(url_for("index"))


@app.route("/stats")
def stats():
    revenue = db.session.query(func.coalesce(func.sum(Order.total), 0)).scalar() or 0
    count = db.session.query(func.count(Order.id)).scalar() or 0
    sales = (
        db.session.query(DrinkSale.name, func.sum(DrinkSale.quantity))
        .group_by(DrinkSale.name)
        .all()
    )
    return render_template(
        "kassen_stats.html", revenue=revenue, count=count, sales=sales
    )
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
