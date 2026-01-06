from flask import Flask, redirect, render_template_string, request, session, url_for
from collections import Counter
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

app = Flask(__name__)
app.secret_key = b'gskjd%hsgd82jsd'

# ---------------------------------------------------------------------------
# Datenbank-Konfiguration
# ---------------------------------------------------------------------------
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///orders.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ---------------------------------------------------------------------------
# Datenbank-Modelle
# ---------------------------------------------------------------------------
class Order(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    total     = db.Column(db.Integer, nullable=False)

class OrderItem(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    name     = db.Column(db.String(100), nullable=False)
    price    = db.Column(db.Integer, nullable=False)

    order = db.relationship("Order", backref=db.backref("items", lazy=True))

class DrinkSale(db.Model):
    """Aggregierte Stückzahlen pro Getränk und Bestellung"""
    id       = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    name     = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, default=0, nullable=False)

    order = db.relationship("Order", backref=db.backref("drink_sales", lazy=True))

with app.app_context():
    db.create_all()

# ---------------------------------------------------------------------------
# Artikel-Preise
# ---------------------------------------------------------------------------
PRICES = {
    "Süssgetränke":     6,
    "Bier":             7,
    "Wein":             7,
    "Weinflasche 0.7":  22,
    "Drink 10":         12,
    "Depot rein":      -2,
    "Weinglassdepot":   2,
    "Kaffee":           3,
    "Shot":             5,
}

# ---------------------------------------------------------------------------
# HTML-Vorlagen
# ---------------------------------------------------------------------------
index_template = """
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
  <title>Kassensystem</title>
  <style>
    :root{
      --bg:#121212; --fg:#e0e0e0; --card:#333; --border:#444;
      --btn-radius:1rem;
      --btn-padding:clamp(0.5rem,3vw,1.2rem);
      --btn-font:clamp(1rem,4vw,1.8rem);
    }
    html,body{
      margin:0;height:100%;width:100%;
      font-family:Arial,Helvetica,sans-serif;
      font-size:18px;background:var(--bg);color:var(--fg);
      -webkit-touch-callout:none;-webkit-user-select:none;user-select:none;
      touch-action:manipulation;overscroll-behavior:contain;
    }
    a{color:#90caf9;text-decoration:none;}

    .wrapper{display:flex;flex-direction:column;height:100vh;}

    /* Top-Bereich */
    .top-section{
      flex:0 0 24%;
      border-bottom:2px solid var(--border);
      padding:1rem 1.3rem;
      display:flex;flex-direction:column;gap:.6rem;
      overflow-y:auto;scrollbar-width:none;
    }
    .top-bar{display:flex;align-items:center;gap:1rem;flex-wrap:wrap;}
    #total{
      font-weight:bold;font-size:clamp(1.3rem,4vw,2.2rem);
      background:var(--card);border:2px solid var(--border);
      border-radius:.6rem;padding:.45rem 1.2rem;
    }
    .top-action{
      background:#ff5722;color:#fff;font-weight:bold;
      border-radius:.6rem;padding:.7rem 1.6rem;
      font-size:clamp(1.1rem,4vw,1.7rem);box-shadow:0 3px 6px rgba(0,0,0,.4);
    }

    .bestellung-container ul{
      padding-left:0;margin:.3rem 0 0;
      font-size:clamp(0.9rem,3.4vw,1.4rem);
      column-count:2;column-gap:.5rem;list-style:none;
    }

    /* Buttons-Grid */
    .bottom-section{flex:1;padding:1rem 1.3rem;overflow-y:auto;}
    .buttons-container{
      display:grid;
      grid-template-columns:repeat(2,minmax(0,1fr));
      grid-auto-rows:1fr;
      gap:0.8rem;
    }
    .item-button{
      display:flex;justify-content:center;align-items:center;
      text-decoration:none;color:#fff;text-align:center;font-weight:bold;
      border-radius:var(--btn-radius);font-size:var(--btn-font);
      padding:var(--btn-padding);min-height:70px;
      box-shadow:0 2px 4px rgba(0,0,0,.3);
      white-space:normal;line-height:1.2;word-break:break-word;
      transition:transform .1s ease;
    }
    .item-button:active{transform:scale(.96);}
    .item-button.suess  {background:#1e88e5;}
    .item-button.bier   {background:#ffd900;color:#222;}
    .item-button.wein   {background:#6a1b9a;}
    .item-button.flasche{background:#5b7c00;}
    .item-button.gross  {background:#ff4cc3;}
    .item-button.depot  {background:#576268;}
    .item-button.Weinglassdepot{background:#fa8d45;}
    .item-button.kaffee {background:#795548;}
    .item-button.shot   {background:#c2185b;}
    .item-button.clear  {background:#e53935;}
  </style>
</head>
<body>
  <div class="wrapper">
    <!-- Top -->
    <div class="top-section">
      <div class="top-bar">
        <div id="total">Total: {{ total }} CHF</div>
        <a class="top-action" href="{{ url_for('clear_order') }}">Neuer&nbsp;Kunde</a>
        <a href="{{ url_for('stats') }}">Statistik</a>
      </div>
      <div class="bestellung-container">
        <h3 style="margin:0;font-size:1rem;">Bestellliste</h3>
        {% if items %}
          <ul>
          {% for item, count in items %}
            <li>{{ count }}× {{ item }}</li>
          {% endfor %}
          </ul>
        {% else %}
          <p style="margin:.2rem 0;">(Noch keine Artikel)</p>
        {% endif %}
      </div>
    </div>

    <!-- Buttons -->
    <div class="bottom-section">
      <div class="buttons-container">
        <a class="item-button suess"   href="{{ url_for('add_item', name='Süssgetränke') }}">Süssgetränke</a>
        <a class="item-button bier"    href="{{ url_for('add_item', name='Bier') }}">Bier&nbsp;/&nbsp;Mate&nbsp;/&nbsp;Red&nbsp;Bull&nbsp;/&nbsp;Smirnoff</a>
        <a class="item-button wein"    href="{{ url_for('add_item', name='Wein') }}">Wein</a>
        <a class="item-button flasche" href="{{ url_for('add_item', name='Weinflasche 0.7') }}">Weinflasche</a>
        <a class="item-button gross"   href="{{ url_for('add_item', name='Drink 10') }}">Drink&nbsp;10</a>
        <a class="item-button depot"   href="{{ url_for('add_item', name='Depot rein') }}">Depot&nbsp;rein</a>
        <a class="item-button Weinglassdepot" href="{{ url_for('add_item', name='Weinglassdepot') }}">Weinglas&nbsp;Depot</a>
        <a class="item-button kaffee"  href="{{ url_for('add_item', name='Kaffee') }}">Kaffee</a>
        <a class="item-button shot"    href="{{ url_for('add_item', name='Shot') }}">Shot</a>
        <a class="item-button clear"   href="{{ url_for('remove_last') }}">1&nbsp;zurück</a>
      </div>
    </div>
  </div>
</body>
</html>
"""

stats_template = """
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
  <title>Statistik</title>
  <style>
    body{background:#121212;color:#e0e0e0;font-family:Arial,Helvetica,sans-serif;margin:0;padding:1.5rem;}
    table{width:100%;border-collapse:collapse;margin-top:1rem;}
    th,td{padding:.5rem;border-bottom:1px solid #444;text-align:left;}
    th{background:#333;}
    a{color:#90caf9;text-decoration:none;}
  </style>
</head>
<body>
  <h1>Statistik</h1>
  <p><strong>Gesamtumsatz:</strong> {{ revenue }} CHF<br>
     <strong>Anzahl Bestellungen:</strong> {{ count }}</p>

  <h2>Verkaufte Getränke</h2>
  <table>
    <tr><th>Getränk</th><th>Menge</th></tr>
    {% for name, qty in sales %}
      <tr><td>{{ name }}</td><td>{{ qty }}</td></tr>
    {% endfor %}
  </table>
  <p><a href="{{ url_for('index') }}">Zurück</a></p>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Routen
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    items = session.get("items", [])
    total = sum(PRICES.get(item, 0) for item in items)
    grouped = list(Counter(items).items())
    return render_template_string(index_template, items=grouped, total=total)

@app.route("/add")
def add_item():
    name = request.args.get("name")
    if name:
        items = session.get("items", [])
        items.append(name)
        session["items"] = items
    return redirect(url_for("index"))

@app.route("/remove_last")
def remove_last():
    items = session.get("items", [])
    if items:
        items.pop()
        session["items"] = items
    return redirect(url_for("index"))

@app.route("/clear_order")
def clear_order():
    """Bestellung abschliessen, in DB sichern, Zähler hochzählen"""
    items = session.get("items", [])
    if items:
        total = sum(PRICES.get(item, 0) for item in items)
        # 1) Order speichern
        order = Order(total=total)
        db.session.add(order)
        db.session.commit()
        # 2) Einzelne Positionen
        for item_name in items:
            db.session.add(OrderItem(order_id=order.id,
                                     name=item_name,
                                     price=PRICES.get(item_name, 0)))
        # 3) Aggregierte Zählung
        for name, qty in Counter(items).items():
            db.session.add(DrinkSale(order_id=order.id, name=name, quantity=qty))
        db.session.commit()
    session["items"] = []
    return redirect(url_for("index"))

@app.route("/stats")
def stats():
    revenue = db.session.query(func.coalesce(func.sum(Order.total), 0)).scalar() or 0
    count   = db.session.query(func.count(Order.id)).scalar() or 0
    sales   = (db.session.query(DrinkSale.name, func.sum(DrinkSale.quantity))
                      .group_by(DrinkSale.name)
                      .all())
    return render_template_string(stats_template,
                                  revenue=revenue,
                                  count=count,
                                  sales=sales)

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
