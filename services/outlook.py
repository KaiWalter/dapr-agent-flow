from __future__ import annotations

from .http_client import HttpClient
from .token_state_store import TokenStateStore

from typing import Optional, Dict, Any
import logging
import msal
import os


class OutlookService:
    """
    Outlook adapter using Microsoft Graph. Reuses MSAL token cache persisted in the Dapr state store (TR001).

    Provides a method to send email via POST /me/sendMail with delegated permissions.
    """

    TOKEN_STATE_KEY = "global_ms_graph_token_cache"

    def __init__(self, http: Optional[HttpClient] = None):
        self.http = http or HttpClient()
        self.base_url = "https://graph.microsoft.com/v1.0/me"
        self.state = TokenStateStore()
        self.logger = logging.getLogger("outlook")
        self.client_id = os.getenv("MS_GRAPH_CLIENT_ID")
        self.client_secret = os.getenv("MS_GRAPH_CLIENT_SECRET")
        self.authority = os.getenv("MS_GRAPH_AUTHORITY", "https://login.microsoftonline.com/consumers")
        # Delegated scopes required for sending mail
        self.scopes = [
            "User.Read",
            "Mail.Send",
        ]

        # Load MSAL token cache from state
        self.cache = msal.SerializableTokenCache()
        raw = self.state.get(self.TOKEN_STATE_KEY)
        if raw:
            try:
                self.cache.deserialize(raw)
            except Exception:
                self.logger.warning("Failed to deserialize token cache; starting fresh.")

        self.app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret,
            token_cache=self.cache,
        )

        self._ensure_token()

    # ---- First-time bootstrap (run once after user consents) ----
    def get_authorization_url(self, redirect_uri: str) -> str:
        return self.app.get_authorization_request_url(self.scopes, redirect_uri=redirect_uri)

    def redeem_auth_code(self, code: str, redirect_uri: str):
        result = self.app.acquire_token_by_authorization_code(
            code, scopes=self.scopes, redirect_uri=redirect_uri
        )
        self._ensure_ok(result)
        self._persist_cache()

    # ---- Normal operation / refresh-on-demand ----
    def _ensure_token(self):
        accounts = self.app.get_accounts()
        result = self.app.acquire_token_silent(self.scopes, account=accounts[0] if accounts else None)
        if not result:
            raise RuntimeError(
                "No cached delegated token. Run interactive consent (auth code) once to bootstrap."
            )
        self._ensure_ok(result)
        self._persist_cache()

    def _headers(self) -> Dict[str, str]:
        accounts = self.app.get_accounts()
        result = self.app.acquire_token_silent(self.scopes, account=accounts[0] if accounts else None)
        self._ensure_ok(result)
        self._persist_cache()
        return {
            "Authorization": f"Bearer {result['access_token']}",
            "Content-Type": "application/json",
        }

    def _persist_cache(self):
        if self.cache.has_state_changed:
            self.state.set(self.TOKEN_STATE_KEY, self.cache.serialize())

    def _ensure_ok(self, result: Dict[str, Any]):
        if not result or "access_token" not in result:
            raise RuntimeError(f"MSAL token failure: {result.get('error_description', result)}")

    # ---- Capability ----
    def send_email(self, to: str, subject: str, body_html: str, save_to_sent: bool = True) -> None:
        """Send an email via Graph /me/sendMail.

        Raises an exception on non-2xx responses.
        """
        url = f"{self.base_url}/sendMail"
        payload: Dict[str, Any] = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": body_html,
                },
                "toRecipients": [
                    {"emailAddress": {"address": to}}
                ],
            },
            "saveToSentItems": bool(save_to_sent),
        }
        resp = self.http.post(url, json=payload, headers=self._headers())
        # Graph returns 202 Accepted with no body
        resp.raise_for_status()
