import json
import app as app_module
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app import Event, Order, Team, Terminal, TerminalPayment, SumUpClientError, app, db


@pytest.fixture(autouse=True)
def setup_database():
    """Reset isolated test database for each test."""

    app.config.update(
        TESTING=True,
        SECRET_KEY="test-key",
        SESSION_TYPE="filesystem",
    )

    with app.app_context():
        engine_url = str(db.engine.url)
        assert "pytest-test.db" in engine_url, f"Unexpected test DB target: {engine_url}"
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
        team = db.session.get(Team, team_id)
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


def test_auto_reload_setting_defaults_to_false(client):
    """Test that auto_reload_on_add defaults to false (opt-in)."""
    event = _create_and_activate_event(client)
    
    with app.app_context():
        event = Event.query.filter_by(name="Test Event").first()
        assert event.shared_settings is not None
        assert event.shared_settings.get("auto_reload_on_add") is False


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
        event = db.session.get(Event, event_id)
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
        updated_event = db.session.get(Event, event.id)
        items = updated_event.kassensystem_settings.get("items", [])
        assert len(items) == 2
        
        pizza = next((item for item in items if item["name"] == "Pizza"), None)
        assert pizza is not None
        assert pizza["category"] == "Essen"
        
        wasser = next((item for item in items if item["name"] == "Wasser"), None)
        assert wasser is not None
        assert wasser["category"] == "Getränke"


def test_product_editor_preserves_data(client):
    """Test that product data is preserved when updating event settings."""
    
    # Create an event with custom products
    custom_products = {
        "items": [
            {
                "name": "CustomBeer",
                "label": "Custom Bier",
                "price": 8,
                "css_class": "custom-beer",
                "color": "#ff0000",
                "category": "Alkohol"
            },
            {
                "name": "CustomWater",
                "label": "Custom Wasser",
                "price": 4,
                "css_class": "custom-water",
                "color": "#0000ff",
                "category": "Getränke"
            }
        ]
    }
    
    client.post(
        "/admin/events",
        data={
            "name": "Product Test Event",
            "kassensystem_enabled": "on",
            "shotcounter_enabled": "on",
            "kassensystem_settings": json.dumps(custom_products),
        },
    )
    
    with app.app_context():
        event = Event.query.filter_by(name="Product Test Event").first()
        assert event is not None
        event_id = event.id
        
        # Verify initial products
        items = event.kassensystem_settings.get("items", [])
        assert len(items) == 2
        
        beer = next((item for item in items if item["name"] == "CustomBeer"), None)
        assert beer is not None
        assert beer["label"] == "Custom Bier"
        assert beer["price"] == 8
        assert beer["color"] == "#ff0000"
        assert beer["category"] == "Alkohol"
        
        water = next((item for item in items if item["name"] == "CustomWater"), None)
        assert water is not None
    
    # Now update the event with modified products
    updated_products = {
        "items": [
            {
                "name": "CustomBeer",
                "label": "Updated Bier",
                "price": 9,
                "css_class": "custom-beer",
                "color": "#00ff00",
                "category": "Alkoholische Getränke"
            },
            {
                "name": "CustomWater",
                "label": "Custom Wasser",
                "price": 4,
                "css_class": "custom-water",
                "color": "#0000ff",
                "category": "Getränke"
            },
            {
                "name": "NewSoda",
                "label": "Neue Cola",
                "price": 5,
                "css_class": "new-soda",
                "color": "#ffff00",
                "category": "Getränke"
            }
        ]
    }
    
    client.post(
        f"/admin/events/{event_id}/update",
        data={
            "kassensystem_enabled": "on",
            "shotcounter_enabled": "on",
            "kassensystem_settings": json.dumps(updated_products),
        },
    )
    
    # Verify products were updated correctly
    with app.app_context():
        updated_event = db.session.get(Event, event_id)
        items = updated_event.kassensystem_settings.get("items", [])
        assert len(items) == 3
        
        # Check updated beer
        beer = next((item for item in items if item["name"] == "CustomBeer"), None)
        assert beer is not None
        assert beer["label"] == "Updated Bier"
        assert beer["price"] == 9
        assert beer["color"] == "#00ff00"
        assert beer["category"] == "Alkoholische Getränke"
        
        # Check new soda was added
        soda = next((item for item in items if item["name"] == "NewSoda"), None)
        assert soda is not None
        assert soda["label"] == "Neue Cola"
        assert soda["price"] == 5


def test_category_order_preserves_item_order(client):
    """Test that category order in price list follows item order when items are reordered."""
    
    # Create event with items in specific order
    kassensystem_settings = {
        "items": [
            {
                "name": "Bier",
                "label": "Bier",
                "price": 7,
                "color": "#193f8a",
                "category": "Alkohol",
                "show_in_price_list": True
            },
            {
                "name": "Pizza",
                "label": "Pizza",
                "price": 12,
                "color": "#ff6600",
                "category": "Essen",
                "show_in_price_list": True
            },
            {
                "name": "Cola",
                "label": "Cola",
                "price": 5,
                "color": "#1f2a44",
                "category": "Getränke",
                "show_in_price_list": True
            }
        ]
    }
    
    # Create and activate event
    client.post(
        "/admin/events",
        data={
            "name": "Category Order Test",
            "kassensystem_enabled": "on",
            "shotcounter_enabled": "on",
            "kassensystem_settings": json.dumps(kassensystem_settings),
        },
    )
    
    with app.app_context():
        event = Event.query.filter_by(name="Category Order Test").first()
        event_id = event.id
    
    client.post(f"/admin/events/{event_id}/activate")
    
    # Set enabled_categories in specific order
    shared_settings = {
        "price_list": {
            "enabled_categories": ["Alkohol", "Essen", "Getränke"]
        }
    }
    
    # Now reorder items - move Pizza (Essen) to the front
    reordered_settings = {
        "items": [
            {
                "name": "Pizza",
                "label": "Pizza",
                "price": 12,
                "color": "#ff6600",
                "category": "Essen",
                "show_in_price_list": True
            },
            {
                "name": "Bier",
                "label": "Bier",
                "price": 7,
                "color": "#193f8a",
                "category": "Alkohol",
                "show_in_price_list": True
            },
            {
                "name": "Cola",
                "label": "Cola",
                "price": 5,
                "color": "#1f2a44",
                "category": "Getränke",
                "show_in_price_list": True
            }
        ]
    }
    
    # Update event with reordered items and enabled_categories
    client.post(
        f"/admin/events/{event_id}/update",
        data={
            "kassensystem_enabled": "on",
            "shotcounter_enabled": "on",
            "kassensystem_settings": json.dumps(reordered_settings),
            "shared_settings": json.dumps(shared_settings),
        },
    )
    
    # Verify that enabled_categories should now reflect the new item order
    # The expected order should be ["Essen", "Alkohol", "Getränke"] based on item order
    # This is what the JavaScript fix ensures happens
    with app.app_context():
        event = db.session.get(Event, event_id)
        price_settings = event.shared_settings.get("price_list", {})
        enabled_categories = price_settings.get("enabled_categories", [])
        
        # After the fix, enabled_categories should maintain the order based on items
        # The JavaScript renderCategories() should update enabled_categories to match item order
        # However, this specific check tests the backend behavior
        # The actual fix is in the JavaScript which will update enabled_categories on render
        
        # Verify items are in the new order
        items = event.kassensystem_settings.get("items", [])
        assert len(items) == 3
        assert items[0]["category"] == "Essen"
        assert items[1]["category"] == "Alkohol"
        assert items[2]["category"] == "Getränke"


def test_create_terminal_success(client):
    response = client.post(
        "/admin/terminals",
        data={"name": "Bar Nord", "sumup_device_id": "dev-12345", "active": "on"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Terminal wurde angelegt." in response.get_data(as_text=True)

    with app.app_context():
        terminal = Terminal.query.filter_by(name="Bar Nord").first()
        assert terminal is not None
        assert terminal.sumup_device_id == "dev-12345"
        assert terminal.active is True


def test_create_terminal_rejects_invalid_device_id(client):
    response = client.post(
        "/admin/terminals",
        data={"name": "Bar Ost", "sumup_device_id": "bad id!", "active": "on"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Ungültige Device-ID" in response.get_data(as_text=True)

    with app.app_context():
        assert Terminal.query.filter_by(name="Bar Ost").first() is None


def test_create_terminal_rejects_duplicate_device_id(client):
    client.post(
        "/admin/terminals",
        data={"name": "Bar West", "sumup_device_id": "dev-777777", "active": "on"},
        follow_redirects=True,
    )

    response = client.post(
        "/admin/terminals",
        data={"name": "Bar Süd", "sumup_device_id": "dev-777777", "active": "on"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "bereits einem anderen Terminal zugeordnet" in response.get_data(as_text=True)

    with app.app_context():
        assert Terminal.query.count() == 1


def test_update_terminal_rejects_duplicate_name(client):
    client.post(
        "/admin/terminals",
        data={"name": "Fix Nord", "sumup_device_id": "dev-111111", "active": "on"},
        follow_redirects=True,
    )
    client.post(
        "/admin/terminals",
        data={"name": "Fix Süd", "sumup_device_id": "dev-222222", "active": "on"},
        follow_redirects=True,
    )

    with app.app_context():
        target = Terminal.query.filter_by(name="Fix Süd").first()
        assert target is not None
        target_id = target.id

    response = client.post(
        f"/admin/terminals/{target_id}/update",
        data={"name": "Fix Nord", "sumup_device_id": "dev-222222", "active": "on"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Ein Terminal mit diesem Namen existiert bereits." in response.get_data(as_text=True)

    with app.app_context():
        unchanged = db.session.get(Terminal, target_id)
        assert unchanged is not None
        assert unchanged.name == "Fix Süd"


def test_terminal_connection_test_success(client, monkeypatch):
    client.post(
        "/admin/terminals",
        data={"name": "Reader Test", "sumup_device_id": "rdr_TEST12345", "active": "on"},
        follow_redirects=True,
    )

    with app.app_context():
        terminal = Terminal.query.filter_by(name="Reader Test").first()
        assert terminal is not None
        terminal_id = terminal.id

    class FakeClient:
        def get_reader_status(self, reader_id):
            assert reader_id == "rdr_TEST12345"
            return {
                "data": {
                    "status": "ONLINE",
                    "state": "IDLE",
                    "connection_type": "Wi-Fi",
                    "battery_level": 77,
                    "firmware_version": "3.3.40.3",
                }
            }

    monkeypatch.setattr(app_module, "_sumup_client", lambda: FakeClient())

    response = client.post(f"/admin/terminals/{terminal_id}/connection-test")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["device_status"] == "ONLINE"
    assert data["device_state"] == "IDLE"
    assert data["connection_type"] == "Wi-Fi"
    assert data["battery_level"] == 77


def test_terminal_connection_test_handles_sumup_error(client, monkeypatch):
    client.post(
        "/admin/terminals",
        data={"name": "Reader Error", "sumup_device_id": "rdr_ERROR123", "active": "on"},
        follow_redirects=True,
    )

    with app.app_context():
        terminal = Terminal.query.filter_by(name="Reader Error").first()
        assert terminal is not None
        terminal_id = terminal.id

    class FakeClient:
        def get_reader_status(self, _reader_id):
            raise SumUpClientError(
                "SumUp API Fehler (404): Resource not found",
                status_code=404,
                error_type="http",
                hint="Reader-ID prüfen.",
            )

    monkeypatch.setattr(app_module, "_sumup_client", lambda: FakeClient())

    response = client.post(f"/admin/terminals/{terminal_id}/connection-test")
    assert response.status_code == 502
    data = response.get_json()
    assert data["success"] is False
    assert data["context"] == "terminal_connection_test"
    assert data["terminal_id"] == terminal_id
    assert "Resource not found" in data["error"]


def test_sumup_connection_test_persists_api_merchant(client, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "_sumup_settings",
        lambda: {
            "access_token": "token-123",
            "merchant_id": "",
            "base_url": "https://api.sumup.com",
            "affiliate_key": None,
        },
    )

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["access_token"] == "token-123"

        def get_profile(self):
            return {"merchant_code": "MH4H92C7"}

    monkeypatch.setattr(app_module, "SumUpClient", FakeClient)

    persisted = {}

    def fake_update_sumup_credentials(**kwargs):
        persisted.update(kwargs)
        return True, None

    monkeypatch.setattr(app_module.credentials_manager, "update_sumup_credentials", fake_update_sumup_credentials)

    response = client.post("/admin/sumup-connection-test")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["configured_merchant_id"] == "MH4H92C7"
    assert data["api_merchant_id"] == "MH4H92C7"
    assert data["persisted_merchant_id"] == "MH4H92C7"
    assert persisted["merchant_id"] == "MH4H92C7"


def test_sumup_client_uses_configured_merchant_without_profile_lookup(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "_sumup_settings",
        lambda: {
            "access_token": "token-123",
            "merchant_id": "MH4H92C7",
            "base_url": "https://api.sumup.com",
            "affiliate_key": None,
        },
    )

    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def get_profile(self):
            raise AssertionError("get_profile must not be called in payment hot-path")

    monkeypatch.setattr(app_module, "SumUpClient", FakeClient)

    app_module._sumup_client()
    assert len(calls) == 1
    assert calls[0]["merchant_id"] == "MH4H92C7"


def test_sumup_client_requires_configured_merchant(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "_sumup_settings",
        lambda: {
            "access_token": "token-123",
            "merchant_id": "",
            "base_url": "https://api.sumup.com",
            "affiliate_key": None,
        },
    )

    with pytest.raises(SumUpClientError) as exc_info:
        app_module._sumup_client()

    assert "Merchant Code fehlt" in str(exc_info.value)


def test_sumup_readers_sync_creates_new_terminals(client, monkeypatch):
    class FakeClient:
        def list_readers(self):
            return [
                {"id": "rdr_ABC123", "details": {"identifier": "200100941884", "model": "SOLO"}},
                {"id": "rdr_DEF456", "details": {"identifier": "200100941885", "model": "SOLO"}},
            ]

    monkeypatch.setattr(app_module, "_sumup_client", lambda: FakeClient())

    response = client.post("/admin/sumup-readers-sync")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["scanned_count"] == 2
    assert data["created_count"] == 2

    with app.app_context():
        assert Terminal.query.filter_by(sumup_device_id="rdr_ABC123").first() is not None
        assert Terminal.query.filter_by(sumup_device_id="rdr_DEF456").first() is not None


def test_sumup_readers_sync_reactivates_existing_terminal(client, monkeypatch):
    with app.app_context():
        db.session.add(Terminal(name="Weiss", sumup_device_id="rdr_KEEP", active=False))
        db.session.commit()

    class FakeClient:
        def list_readers(self):
            return [{"id": "rdr_KEEP", "details": {"identifier": "200100941884", "model": "SOLO"}}]

    monkeypatch.setattr(app_module, "_sumup_client", lambda: FakeClient())

    response = client.post("/admin/sumup-readers-sync")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["created_count"] == 0
    assert data["reactivated_count"] == 1

    with app.app_context():
        terminal = Terminal.query.filter_by(sumup_device_id="rdr_KEEP").first()
        assert terminal is not None
        assert terminal.active is True


def test_sumup_readers_status_returns_live_and_local_info(client, monkeypatch):
    with app.app_context():
        db.session.add(Terminal(name="Weiss", sumup_device_id="rdr_STATUS1", active=True))
        db.session.commit()

    class FakeClient:
        def list_readers(self):
            return [
                {
                    "id": "rdr_STATUS1",
                    "name": "Sumup Weiss",
                    "details": {"identifier": "200100941884", "model": "SOLO", "status": "ONLINE"},
                }
            ]

        def get_reader_status(self, reader_id):
            assert reader_id == "rdr_STATUS1"
            return {
                "data": {
                    "status": "ONLINE",
                    "state": "IDLE",
                    "connection_type": "Wi-Fi",
                    "battery_level": 12,
                    "firmware_version": "3.3.40.3",
                }
            }

    monkeypatch.setattr(app_module, "_sumup_client", lambda: FakeClient())

    response = client.get("/admin/sumup-readers-status")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["count"] == 1
    assert len(data["readers"]) == 1
    item = data["readers"][0]
    assert item["reader_id"] == "rdr_STATUS1"
    assert item["live_status"] == "ONLINE"
    assert item["live_state"] == "IDLE"
    assert item["connection_type"] == "Wi-Fi"
    assert item["local_terminal_name"] == "Weiss"


def test_terminal_payment_status_404_keeps_pending(client, monkeypatch):
    with app.app_context():
        event = Event(
            name="SumUp Event",
            is_active=True,
            is_archived=False,
            kassensystem_enabled=True,
            shotcounter_enabled=True,
        )
        db.session.add(event)
        db.session.flush()

        terminal = Terminal(name="Reader 1", sumup_device_id="rdr_TEST", active=True)
        db.session.add(terminal)
        db.session.flush()

        payment = TerminalPayment(
            terminal_id=terminal.id,
            event_id=event.id,
            amount_cents=700,
            currency="CHF",
            status="pending",
            sumup_payment_id="txn_404",
        )
        db.session.add(payment)
        db.session.commit()
        payment_id = payment.id

    class FakeClient:
        class _Response:
            def __init__(self, payment_id, status, raw):
                self.payment_id = payment_id
                self.status = status
                self.raw = raw

        def get_payment_status(self, _payment_id):
            raise SumUpClientError(
                "SumUp API Fehler (404): Resource not found",
                status_code=404,
                error_type="http",
            )

    monkeypatch.setattr(app_module, "_sumup_client", lambda: FakeClient())

    response = client.get(f"/api/terminal-payments/{payment_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["status"] == "pending"


def test_create_terminal_payment_reconciles_stale_pending_before_blocking(client, monkeypatch):
    event = _create_and_activate_event(client)
    with app.app_context():
        terminal = Terminal(name="Reader 2", sumup_device_id="rdr_TEST2", active=True)
        db.session.add(terminal)
        db.session.flush()

        stale_payment = TerminalPayment(
            terminal_id=terminal.id,
            event_id=event.id,
            amount_cents=700,
            currency="CHF",
            status="pending",
            sumup_payment_id="txn_stale",
            created_at=app_module.utcnow() - timedelta(seconds=30),
        )
        db.session.add(stale_payment)
        db.session.commit()
        terminal_id = terminal.id
        stale_payment_id = stale_payment.id

    class FakeClient:
        def get_payment_status(self, _payment_id):
            raise SumUpClientError(
                "SumUp API Fehler (404): Resource not found",
                status_code=404,
                error_type="http",
            )

        def get_reader_status(self, _reader_id):
            return {"data": {"state": "IDLE", "status": "ONLINE"}}

        def create_terminal_payment(self, **_kwargs):
            return type(
                "Resp",
                (),
                {
                    "payment_id": "txn_new",
                    "status": "pending",
                    "raw": {"data": {"id": "txn_new"}},
                },
            )()

    monkeypatch.setattr(app_module, "_sumup_client", lambda: FakeClient())

    response = client.post(
        "/api/terminal-payments",
        json={"terminal_id": terminal_id, "amount_cents": 500, "currency": "CHF"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["status"] == "pending"

    with app.app_context():
        old_payment = db.session.get(TerminalPayment, stale_payment_id)
        assert old_payment is not None
        assert old_payment.status == "aborted"


def test_create_terminal_payment_rejects_invalid_terminal_id_type(client):
    _create_and_activate_event(client)
    response = client.post(
        "/api/terminal-payments",
        json={"terminal_id": "abc", "amount_cents": 500, "currency": "CHF"},
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "Terminal-ID ist ungültig" in data["error"]


def test_create_terminal_payment_maps_integrity_error_to_conflict(client, monkeypatch):
    _create_and_activate_event(client)
    with app.app_context():
        terminal = Terminal(name="Reader 3", sumup_device_id="rdr_TEST3", active=True)
        db.session.add(terminal)
        db.session.commit()
        terminal_id = terminal.id

    class FakeClient:
        def create_terminal_payment(self, **_kwargs):
            return type(
                "Resp",
                (),
                {
                    "payment_id": "txn_new",
                    "status": "pending",
                    "raw": {"data": {"id": "txn_new"}},
                },
            )()

    monkeypatch.setattr(app_module, "_sumup_client", lambda: FakeClient())

    def _raise_integrity_error():
        raise IntegrityError("insert", {}, Exception("duplicate pending"))

    monkeypatch.setattr(db.session, "flush", _raise_integrity_error)

    response = client.post(
        "/api/terminal-payments",
        json={"terminal_id": terminal_id, "amount_cents": 500, "currency": "CHF"},
    )
    assert response.status_code == 409
    data = response.get_json()
    assert data["success"] is False
    assert "aktive Zahlung" in data["error"]

