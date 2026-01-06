from flask import Flask, redirect, render_template, request, session, url_for, abort, render_template_string
from collections import Counter
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from flask_session import Session

app = Flask(__name__)
app.secret_key = b'gskjd%hsgd82jsd'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///teamliste.db'
db = SQLAlchemy(app)
socketio = SocketIO(app, manage_session=True)
app.config['SESSION_TYPE'] = 'filesystem'  # Session-Daten auf dem Server speichern
Session(app)

class teamliste(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, unique=False, nullable=False)
    team = db.Column(db.String(150), unique=True, nullable=False)

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

html_template = """
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8" />
  <title>Kassensystem</title>
  <style>
    html, body {
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      font-family: Arial, sans-serif;
      font-size: 18px;
      overflow: hidden;
    }

    .wrapper {
      display: flex;
      flex-direction: column; 
      height: 100vh;
    }

    .bestellung-container h3 {
      margin: 5px 0;
    }
    .top-section {
      flex: 0 0 33%;
      border-bottom: 1px solid #999;
      box-sizing: border-box;
      padding: 10px 20px;
      overflow-y: auto;
    }
    .top-section h1 {
      margin-top: 0;
    }

    #total {
      font-weight: bold;
      margin-top: 10px;
      font-size: 1.5em;
      background-color: #ffe680;
      border: 2px solid #ccc;
      border-radius: 5px;
      padding: 10px;
      text-align: center;
      width: fit-content;
    }

    .bottom-section {
      flex: 1;
      padding: 10px;
      box-sizing: border-box;
    }


  .buttons-container {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(400px, 2fr)); /* Breite reduziert */
    gap: 5px; /* Geringerer Abstand zwischen Buttons */
    height: 200%;
    box-sizing: border-box;
    align-content: start;
  }

  .item-button {
    display: flex;
    justify-content: center;
    align-items: center;
    text-decoration: none;
    color: white;
    border: 1px solid #999;
    border-radius: 4px;
    font-size: 60px; /* Kleinere Schriftgröße */
    padding: 10px; /* Geringeres Padding */
    text-align: center;
  }

  .item-button:hover {
    background-color: #bbb;
  }


  /* Anpassung für spezifische Farben bleibt gleich */
  .item-button.suess {
    background-color: #0099ff;
  }
  .item-button.bier {
    background-color: #ffd900;
  }
  .item-button.wein {
    background-color: #350097;
  }
  .item-button.shots {
    background-color: #ffe4b5;
  }
  .item-button.gross {
    background-color: #ff00c8;
  }
  .item-button.depot {
    background-color: #000000;
  }  
  .item-button.clear {
    background-color: #fc0303;
  }
  .item-button.Kunde {
    background-color: #696969;
  }
</style>
</head>
<body>
  <div class="wrapper">
    <div class="top-section">
      <h1>Kassensystem Demo</h1>
      <div id="total">
        Total: {{ total }} CHF
      </div>
      <div class="bestellung-container">
        <h3>Bestellliste</h3>
        {% if items %}
            <ul>
            {% for (item, count) in items %}
                <li>{{ count }}x {{ item }}</li>
            {% endfor %}
            </ul>
        {% else %}
            <p>(Noch keine Artikel)</p>
        {% endif %}
      </div>
    </div>

    <div class="bottom-section">
      <div class="buttons-container">
        <a class="item-button suess" href="{{ url_for('add_item', name='Süssgetränke') }}">Süssgetränke</a>
        <a class="item-button bier" href="{{ url_for('add_item', name='Bier') }}">Bier, Mate, Redbull, Smirnoff</a>
        <a class="item-button wein" href="{{ url_for('add_item', name='Wein') }}">Weinflasche \n  </a>  
        <a class="item-button gross" href="{{ url_for('add_item', name='Drink') }}">Drink 10</a>
        <a class="item-button depot" href="{{ url_for('add_item', name='Depot rein') }}">Depot rein</a>
        <a class="item-button depot" href="{{ url_for('add_item', name='Weinglassdepot') }}">Weinglassdepot</a>
        <a class="item-button clear" href="{{ url_for('remove_last') }}">1 zurück</a>
        <a class="item-button Kunde" href="{{ url_for('clear_order') }}">Neuer Kunde</a>
      </div>
    </div>
  </div>
</body>
</html>
"""

PRICES = {
    'Süssgetränke': 6,
    'Bier': 7,
    'Wein': 7,
    'Drink 10': 12,
    'Depot rein': -2,
    'Weinflasche 0.7': 22,
    'Weinglassdepot': 2,

}



@app.route("/")
def index():
    """Startseite mit der Bestell-Liste (zusammengefasst) und Gesamtbetrag."""
    items = session.get('items', [])
    total_price = sum(PRICES.get(item, 0) for item in items)
    # Artikel zusammenfassen, z.B. 2x Bier
    counts = Counter(items)
    grouped_items = list(counts.items())  # [(artikel, anzahl), ...]

    return render_template_string(
        html_template,
        items=grouped_items,
        total=total_price
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
    """Löscht die gesamte Bestellung."""
    session['items'] = []
    return redirect(url_for('index'))
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

