import pytest

from app import app, db, teamliste


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


def test_index_route_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Kassensystem Demo" in response.data


def test_registration_creates_team_and_shows_message(client):
    response = client.post(
        "/registration", data={"Teamname": "Team Alpha"}, follow_redirects=True
    )
    assert response.status_code == 200
    assert b"erfolgreich hinzugef" in response.data

    with app.app_context():
        assert teamliste.query.filter_by(team="Team Alpha").count() == 1


def test_leaderboard_displays_saved_team(client):
    with app.app_context():
        db.session.add(teamliste(team="Leaderboard Team", score=5))
        db.session.commit()

    response = client.get("/leaderboard")
    assert response.status_code == 200
    assert b"Leaderboard Team" in response.data
