"""Simple SumUp API client for terminal payments."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib import error, request


class SumUpClientError(RuntimeError):
    """Raised when SumUp API communication fails."""


@dataclass
class SumUpResponse:
    payment_id: Optional[str]
    status: Optional[str]
    raw: Dict[str, Any]


class SumUpClient:
    def __init__(
        self,
        *,
        access_token: str,
        merchant_id: str,
        base_url: str,
        affiliate_key: Optional[str] = None,
    ) -> None:
        self._access_token = access_token
        self._merchant_id = merchant_id
        self._base_url = base_url.rstrip("/")
        self._affiliate_key = affiliate_key

    def create_terminal_payment(self, *, amount_cents: int, currency: str, device_id: str, reference: str) -> SumUpResponse:
        payload = {
            "amount": f"{amount_cents / 100:.2f}",
            "currency": currency,
            "device_id": device_id,
            "reference": reference,
            "merchant_id": self._merchant_id,
        }
        response = self._request("POST", "/v0.1/terminal/payments", payload)
        return SumUpResponse(
            payment_id=response.get("id") or response.get("payment_id"),
            status=response.get("status"),
            raw=response,
        )

    def get_payment_status(self, payment_id: str) -> SumUpResponse:
        response = self._request("GET", f"/v0.1/terminal/payments/{payment_id}")
        return SumUpResponse(
            payment_id=response.get("id") or payment_id,
            status=response.get("status"),
            raw=response,
        )

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }
        if self._affiliate_key:
            headers["X-SumUp-Affiliate-Key"] = self._affiliate_key
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=10) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8") if exc.fp else str(exc)
            raise SumUpClientError(f"SumUp API Fehler ({exc.code}): {detail}") from exc
        except error.URLError as exc:
            raise SumUpClientError(f"SumUp API nicht erreichbar: {exc}") from exc

        if not body:
            return {}
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise SumUpClientError("Ungültige SumUp API Antwort") from exc
