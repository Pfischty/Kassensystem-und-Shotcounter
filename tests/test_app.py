import json

import pytest

from app import Event, Order, Team, app, db


@pytest.fixture(autouse=True)
def setup_database():
    """Configure an in-memory database for each test."""

    app.config.update(
        TESTING=True,
        SECRET_KEY="test-key",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SESSION_TYPE="filesystem",
    )

    with app.app_context():
        db.drop_all()
        db.create_all()
    yield
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client():
    with app.test_client() as client:
        yield client


def _create_and_activate_event(client):
    client.post(
        "/admin/events",
        data={
            "name": "Test Event",
            "kassensystem_enabled": "on",
            "shotcounter_enabled": "on",
        },
    )
    with app.app_context():
        event = Event.query.filter_by(name="Test Event").first()
    client.post(f"/admin/events/{event.id}/activate")
    return event


def test_event_creation_and_activation(client):
    event = _create_and_activate_event(client)
    with app.app_context():
        active = Event.query.filter_by(is_active=True).first()
        assert active is not None
        assert active.id == event.id


def test_cashier_checkout_records_order(client):
    event = _create_and_activate_event(client)
    client.get("/cashier/add?name=Süssgetränke")
    client.get("/cashier/add?name=Bier")
    client.get("/cashier/checkout")

    with app.app_context():
        orders = Order.query.filter_by(event_id=event.id).all()
        assert len(orders) == 1
        assert orders[0].total == 13  # 6 + 7 CHF
        assert len(orders[0].items) == 2
        assert len(orders[0].drink_sales) >= 1


def test_shotcounter_tracks_shots(client):
    event = _create_and_activate_event(client)
    client.post("/shotcounter/teams", data={"team_name": "Alpha"})

    with app.app_context():
        team = Team.query.filter_by(event_id=event.id, name="Alpha").first()
        assert team is not None
        team_id = team.id

    client.post("/shotcounter/shots", data={"team_id": team_id, "amount": 3})

    with app.app_context():
        team = Team.query.get(team_id)
        assert team.shots == 3


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"


def test_cashier_add_item_ajax_mode(client):
    """Test that add_item endpoint returns JSON when ajax=1 is passed."""
    event = _create_and_activate_event(client)
    
    # Add item via AJAX
    response = client.get("/cashier/add?name=Bier&ajax=1")
    assert response.status_code == 200
    data = response.get_json()
    
    assert data["success"] is True
    assert "cart" in data
    assert data["cart"]["total"] == 7
    assert data["cart"]["item_count"] == 1
    assert len(data["cart"]["items"]) == 1
    assert data["cart"]["items"][0]["name"] == "Bier"


def test_cashier_remove_last_ajax_mode(client):
    """Test that remove_last endpoint returns JSON when ajax=1 is passed."""
    event = _create_and_activate_event(client)
    
    # Add items first
    client.get("/cashier/add?name=Bier")
    client.get("/cashier/add?name=Süssgetränke")
    
    # Remove last item via AJAX
    response = client.get("/cashier/remove_last?ajax=1")
    assert response.status_code == 200
    data = response.get_json()
    
    assert data["success"] is True
    assert "cart" in data
    assert data["cart"]["total"] == 7  # Only Bier remains
    assert data["cart"]["item_count"] == 1


def test_auto_reload_setting_defaults_to_true(client):
    """Test that auto_reload_on_add defaults to true for backward compatibility."""
    event = _create_and_activate_event(client)
    
    with app.app_context():
        event = Event.query.filter_by(name="Test Event").first()
        # If shared_settings is None or doesn't have the key, it should default to True
        assert event.shared_settings is None or event.shared_settings.get("auto_reload_on_add", True) is True


def test_auto_reload_setting_can_be_disabled(client):
    """Test that auto_reload_on_add can be set to false via admin."""
    # First create an event with it enabled
    client.post(
        "/admin/events",
        data={
            "name": "No Reload Event",
            "kassensystem_enabled": "on",
            "shotcounter_enabled": "on",
            "auto_reload_on_add": "on",  # Initially enabled
        },
    )
    
    with app.app_context():
        event = Event.query.filter_by(name="No Reload Event").first()
        assert event is not None
        event_id = event.id
        assert event.shared_settings.get("auto_reload_on_add") is True
    
    # Now update it to disable auto_reload (checkbox not sent = unchecked)
    client.post(
        f"/admin/events/{event_id}/update",
        data={
            "kassensystem_enabled": "on",
            "shotcounter_enabled": "on",
            # auto_reload_on_add checkbox is not included (unchecked)
        },
    )
    
    with app.app_context():
        event = Event.query.get(event_id)
        assert event is not None
        # When checkbox is not in form during update, it should be set to False
        # But our current logic preserves it or defaults to True
        # We need to update the logic to handle this case
        assert event.shared_settings.get("auto_reload_on_add") is False
def test_event_category_saving(client):
    """Test that categories are correctly saved and retrieved for event products."""
    
    # Create event with custom categories
    kassensystem_settings = {
        "items": [
            {
                "name": "Bier",
                "label": "Bier",
                "price": 7,
                "css_class": "bier",
                "color": "#193f8a",
                "category": "Alkohol"
            },
            {
                "name": "Cola",
                "label": "Cola",
                "price": 5,
                "css_class": "cola",
                "color": "#1f2a44",
                "category": "Getränke"
            }
        ]
    }
    
    client.post(
        "/admin/events",
        data={
            "name": "Category Test Event",
            "kassensystem_enabled": "on",
            "shotcounter_enabled": "on",
            "kassensystem_settings": json.dumps(kassensystem_settings),
        },
    )
    
    # Verify categories are saved
    with app.app_context():
        event = Event.query.filter_by(name="Category Test Event").first()
        assert event is not None
        items = event.kassensystem_settings.get("items", [])
        assert len(items) == 2
        
        bier = next((item for item in items if item["name"] == "Bier"), None)
        assert bier is not None
        assert bier["category"] == "Alkohol"
        
        cola = next((item for item in items if item["name"] == "Cola"), None)
        assert cola is not None
        assert cola["category"] == "Getränke"


def test_event_category_update(client):
    """Test that categories are preserved when updating an event."""
    
    # Create an event
    event = _create_and_activate_event(client)
    
    # Update with custom categories
    kassensystem_settings = {
        "items": [
            {
                "name": "Pizza",
                "label": "Pizza",
                "price": 12,
                "css_class": "pizza",
                "color": "#ff6600",
                "category": "Essen"
            },
            {
                "name": "Wasser",
                "label": "Wasser",
                "price": 3,
                "css_class": "wasser",
                "color": "#0066cc",
                "category": "Getränke"
            }
        ]
    }
    
    client.post(
        f"/admin/events/{event.id}/update",
        data={
            "kassensystem_enabled": "on",
            "shotcounter_enabled": "on",
            "kassensystem_settings": json.dumps(kassensystem_settings),
        },
    )
    
    # Verify categories are saved
    with app.app_context():
        updated_event = Event.query.get(event.id)
        items = updated_event.kassensystem_settings.get("items", [])
        assert len(items) == 2
        
        pizza = next((item for item in items if item["name"] == "Pizza"), None)
        assert pizza is not None
        assert pizza["category"] == "Essen"
        
        wasser = next((item for item in items if item["name"] == "Wasser"), None)
        assert wasser is not None
        assert wasser["category"] == "Getränke"

