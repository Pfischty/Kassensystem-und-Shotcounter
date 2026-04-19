"""Simple SumUp API client for terminal payments."""

from __future__ import annotations

import json
from urllib.parse import urlencode
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib import error, request


class SumUpClientError(RuntimeError):
    """Raised when SumUp API communication fails."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        error_type: str = "unknown",
        detail: Optional[str] = None,
        hint: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.detail = detail
        self.hint = hint


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
        merchant_id: Optional[str],
        base_url: str,
        affiliate_key: Optional[str] = None,
    ) -> None:
        self._access_token = access_token
        self._merchant_id = (merchant_id or "").strip()
        self._base_url = base_url.rstrip("/")
        self._affiliate_key = affiliate_key

    def _require_merchant_id(self) -> str:
        merchant = (self._merchant_id or "").strip()
        if not merchant:
            raise SumUpClientError(
                "SumUp Merchant Code fehlt.",
                error_type="config",
                hint="Merchant Code im Adminbereich setzen oder per Verbindungstest aus Token übernehmen.",
            )
        return merchant

    def create_terminal_payment(self, *, amount_cents: int, currency: str, device_id: str, reference: str) -> SumUpResponse:
        merchant_id = self._require_merchant_id()
        # Prefer modern Reader Checkout API.
        reader_payload = {
            "total_amount": amount_cents / 100,
            "description": reference,
        }
        try:
            response = self._request(
                "POST",
                f"/v0.1/merchants/{merchant_id}/readers/{device_id}/checkout",
                reader_payload,
            )
            data = response.get("data") if isinstance(response.get("data"), dict) else {}
            payment_id = data.get("client_transaction_id") or data.get("id")
            return SumUpResponse(payment_id=payment_id, status="pending", raw=response)
        except SumUpClientError as exc:
            # Legacy fallback for older integrations/accounts.
            if exc.status_code != 404:
                raise

        legacy_payload = {
            "amount": f"{amount_cents / 100:.2f}",
            "currency": currency,
            "device_id": device_id,
            "reference": reference,
            "merchant_id": merchant_id,
        }
        response = self._request("POST", "/v0.1/terminal/payments", legacy_payload)
        return SumUpResponse(
            payment_id=response.get("id") or response.get("payment_id"),
            status=response.get("status") or "pending",
            raw=response,
        )

    def get_payment_status(self, payment_id: str) -> SumUpResponse:
        # Prefer transaction lookup in modern API.
        query = urlencode({"id": payment_id})
        try:
            response = self._request("GET", f"/v0.1/me/transactions?{query}")
            status = response.get("simple_status") or response.get("status")
            return SumUpResponse(
                payment_id=response.get("client_transaction_id") or response.get("id") or payment_id,
                status=status,
                raw=response,
            )
        except SumUpClientError as exc:
            if exc.status_code != 404:
                raise

        # Legacy fallback.
        response = self._request("GET", f"/v0.1/terminal/payments/{payment_id}")
        return SumUpResponse(
            payment_id=response.get("id") or payment_id,
            status=response.get("status"),
            raw=response,
        )

    def get_profile(self) -> Dict[str, Any]:
        """Fetch merchant profile data to validate credentials and connectivity."""
        return self._request("GET", "/v0.1/me")

    def get_reader_status(self, reader_id: str) -> Dict[str, Any]:
        """Fetch status information for a specific reader device."""
        merchant_id = self._require_merchant_id()
        return self._request("GET", f"/v0.1/merchants/{merchant_id}/readers/{reader_id}/status")

    def list_readers(self) -> list[Dict[str, Any]]:
        """List readers configured for the merchant account."""
        merchant_id = self._require_merchant_id()
        response = self._request("GET", f"/v0.1/merchants/{merchant_id}/readers")
        items = response.get("items") if isinstance(response, dict) else None
        return items if isinstance(items, list) else []

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
            parsed_detail = detail
            try:
                payload = json.loads(detail)
                parsed_detail = (
                    payload.get("message")
                    or payload.get("error")
                    or payload.get("error_description")
                    or payload.get("detail")
                    or detail
                )
            except (TypeError, json.JSONDecodeError):
                parsed_detail = detail

            hint_map = {
                400: "Anfrage ist ungültig. Prüfe Parameter und Device-ID.",
                401: "Token ungültig oder abgelaufen. Bitte Access Token prüfen.",
                403: "Kein Zugriff erlaubt. Prüfe Merchant-ID und Berechtigungen.",
                404: "Ressource nicht gefunden. Prüfe Reader-ID (z. B. rdr_...), Merchant-Code und API-Berechtigungen.",
                429: "Zu viele Anfragen. Bitte kurz warten und erneut versuchen.",
                500: "SumUp Serverfehler. Bitte später erneut versuchen.",
                502: "SumUp Gateway-Fehler. Bitte später erneut versuchen.",
                503: "SumUp Dienst nicht verfügbar. Bitte später erneut versuchen.",
            }
            raise SumUpClientError(
                f"SumUp API Fehler ({exc.code}): {parsed_detail}",
                status_code=exc.code,
                error_type="http",
                detail=detail,
                hint=hint_map.get(exc.code),
            ) from exc
        except error.URLError as exc:
            raise SumUpClientError(
                f"SumUp API nicht erreichbar: {exc}",
                error_type="network",
                detail=str(exc),
                hint="Prüfe Internetverbindung, DNS und Firewall-Regeln.",
            ) from exc

        if not body:
            return {}
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise SumUpClientError(
                "Ungültige SumUp API Antwort",
                error_type="decode",
                detail=body[:500],
                hint="Die API hat eine unerwartete Antwort geliefert. Bitte erneut versuchen.",
            ) from exc
