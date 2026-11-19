from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.padding import PSS, MGF1
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from .config import Settings


class KalshiAPIError(RuntimeError):
    pass


class KalshiClient:
    def __init__(self, settings: Settings, session: requests.Session | None = None):
        self.settings = settings
        self.session = session or requests.Session()
        self._private_key: Ed25519PrivateKey | RSAPrivateKey | None = None

    def get_market(self, ticker: str) -> dict[str, Any]:
        return self._request("GET", f"/markets/{ticker}", authenticated=False)

    def get_balance(self) -> dict[str, Any]:
        self.settings.validate_kalshi()
        return self._request("GET", "/portfolio/balance")

    def list_events(self, series_ticker: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        cursor = None
        for _ in range(20):
            params: dict[str, Any] = {
                "limit": 200,
                "status": "open",
                "with_nested_markets": "true",
                "series_ticker": series_ticker,
            }
            if cursor:
                params["cursor"] = cursor
            body = self._request("GET", "/events", authenticated=False, params=params)
            events.extend(body.get("events", []))
            cursor = body.get("cursor")
            if not cursor:
                break
        return events

    def create_combo(self, selected_markets: list[dict[str, str]]) -> dict[str, Any]:
        self.settings.validate_kalshi()
        return self._request(
            "POST",
            f"/multivariate_event_collections/{self.settings.combo_collection}",
            json_body={
                "selected_markets": selected_markets,
                "with_market_payload": True,
            },
        )

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.settings.validate_kalshi()
        return self._request("POST", "/portfolio/events/orders", json_body=payload)

    def _request(
        self,
        method: str,
        path: str,
        authenticated: bool = True,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.settings.kalshi_base_url}{path}"
        headers = {"Accept": "application/json"}
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        if authenticated:
            headers.update(self._auth_headers(method, url))

        try:
            response = self.session.request(
                method,
                url,
                headers=headers,
                json=json_body,
                params=params,
                timeout=15,
            )
        except requests.RequestException as exc:
            raise KalshiAPIError(f"Error de red con Kalshi: {exc}") from exc

        if not response.ok:
            raise KalshiAPIError(
                f"Kalshi respondió HTTP {response.status_code}: {response.text[:1000]}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise KalshiAPIError("Kalshi devolvió una respuesta JSON no válida") from exc
        if not isinstance(body, dict):
            raise KalshiAPIError("Kalshi devolvió una estructura inesperada")
        return body

    def _auth_headers(self, method: str, url: str) -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        sign_path = urlsplit(url).path
        message = f"{timestamp}{method.upper()}{sign_path}".encode()
        key = self._load_private_key()
        if isinstance(key, Ed25519PrivateKey):
            signature = key.sign(message)
        else:
            signature = key.sign(
                message,
                PSS(mgf=MGF1(hashes.SHA256()), salt_length=PSS.DIGEST_LENGTH),
                hashes.SHA256(),
            )
        return {
            "KALSHI-ACCESS-KEY": self.settings.kalshi_api_key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
        }

    def _load_private_key(self) -> Ed25519PrivateKey | RSAPrivateKey:
        if self._private_key is not None:
            return self._private_key
        try:
            pem = Path(self.settings.kalshi_private_key_path).read_bytes()
            key = serialization.load_pem_private_key(pem, password=None)
        except (OSError, ValueError) as exc:
            raise KalshiAPIError(f"No se pudo cargar la clave privada: {exc}") from exc
        if not isinstance(key, (Ed25519PrivateKey, RSAPrivateKey)):
            raise KalshiAPIError("La clave debe ser Ed25519 o RSA")
        self._private_key = key
        return key
