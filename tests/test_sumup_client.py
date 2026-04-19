import io
import json
from urllib import error

from sumup_client import SumUpClient


class _FakeResponse:
    def __init__(self, body: dict):
        self._body = json.dumps(body).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_create_terminal_payment_uses_reader_checkout(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=10):
        calls.append((req.full_url, req.method, req.data))
        return _FakeResponse({"data": {"client_transaction_id": "txn-123"}})

    monkeypatch.setattr("sumup_client.request.urlopen", fake_urlopen)

    client = SumUpClient(
        access_token="token",
        merchant_id="MH4H92C7",
        base_url="https://api.sumup.com",
    )
    response = client.create_terminal_payment(
        amount_cents=1250,
        currency="CHF",
        device_id="rdr_6PSXAMCT6B91V9JYYH60TY2X79",
        reference="test-ref",
    )

    assert response.payment_id == "txn-123"
    assert response.status == "pending"
    assert len(calls) == 1
    assert "/v0.1/merchants/MH4H92C7/readers/rdr_6PSXAMCT6B91V9JYYH60TY2X79/checkout" in calls[0][0]
    payload = json.loads(calls[0][2].decode("utf-8"))
    assert payload["total_amount"] == {"currency": "CHF", "minor_unit": 2, "value": 1250}
    assert payload["description"] == "test-ref"


def test_create_terminal_payment_falls_back_to_legacy_endpoint(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=10):
        calls.append((req.full_url, req.method, req.data))
        if len(calls) == 1:
            raise error.HTTPError(
                req.full_url,
                404,
                "Not Found",
                hdrs=None,
                fp=io.BytesIO(b'{"detail":"Resource not found"}'),
            )
        return _FakeResponse({"id": "legacy-payment-1", "status": "PENDING"})

    monkeypatch.setattr("sumup_client.request.urlopen", fake_urlopen)

    client = SumUpClient(
        access_token="token",
        merchant_id="MH4H92C7",
        base_url="https://api.sumup.com",
    )
    response = client.create_terminal_payment(
        amount_cents=500,
        currency="CHF",
        device_id="rdr_6PSXAMCT6B91V9JYYH60TY2X79",
        reference="fallback-ref",
    )

    assert response.payment_id == "legacy-payment-1"
    assert response.status == "PENDING"
    assert len(calls) == 2
    assert "/readers/" in calls[0][0]
    assert "/v0.1/terminal/payments" in calls[1][0]


def test_create_terminal_payment_resolves_device_identifier_after_404(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=10):
        calls.append((req.full_url, req.method, req.data))
        if "/readers/dev-123456/checkout" in req.full_url:
            raise error.HTTPError(
                req.full_url,
                404,
                "Not Found",
                hdrs=None,
                fp=io.BytesIO(b'{"detail":"Resource not found"}'),
            )
        if req.full_url.endswith("/readers"):
            return _FakeResponse(
                {
                    "items": [
                        {
                            "id": "rdr_6PSXAMCT6B91V9JYYH60TY2X79",
                            "device": {"identifier": "dev-123456", "model": "solo"},
                        }
                    ]
                }
            )
        return _FakeResponse({"data": {"client_transaction_id": "txn-resolved"}})

    monkeypatch.setattr("sumup_client.request.urlopen", fake_urlopen)

    client = SumUpClient(
        access_token="token",
        merchant_id="MH4H92C7",
        base_url="https://api.sumup.com",
    )
    response = client.create_terminal_payment(
        amount_cents=999,
        currency="CHF",
        device_id="dev-123456",
        reference="resolve-ref",
    )

    assert response.payment_id == "txn-resolved"
    assert len(calls) == 3
    assert "/readers/dev-123456/checkout" in calls[0][0]
    assert calls[1][0].endswith("/v0.1/merchants/MH4H92C7/readers")
    assert "/readers/rdr_6PSXAMCT6B91V9JYYH60TY2X79/checkout" in calls[2][0]


def test_get_reader_status_resolves_non_rdr_identifier(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=10):
        calls.append((req.full_url, req.method, req.data))
        if req.full_url.endswith("/readers/dev-ABC/status"):
            raise error.HTTPError(
                req.full_url,
                404,
                "Not Found",
                hdrs=None,
                fp=io.BytesIO(b'{"detail":"Resource not found"}'),
            )
        if req.full_url.endswith("/readers"):
            return _FakeResponse(
                {
                    "items": [
                        {
                            "id": "rdr_6PSXAMCT6B91V9JYYH60TY2X79",
                            "details": {"identifier": "dev-ABC"},
                        }
                    ]
                }
            )
        return _FakeResponse({"data": {"status": "ONLINE", "state": "IDLE"}})

    monkeypatch.setattr("sumup_client.request.urlopen", fake_urlopen)

    client = SumUpClient(
        access_token="token",
        merchant_id="MH4H92C7",
        base_url="https://api.sumup.com",
    )
    response = client.get_reader_status("dev-ABC")

    assert response["data"]["status"] == "ONLINE"
    assert len(calls) == 3
    assert calls[1][0].endswith("/v0.1/merchants/MH4H92C7/readers")
    assert calls[2][0].endswith("/v0.1/merchants/MH4H92C7/readers/rdr_6PSXAMCT6B91V9JYYH60TY2X79/status")
