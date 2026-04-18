import frappe
import requests

_PROD_BASE = "https://api.pax8.com"
_TOKEN_URL = "https://login.pax8.com/oauth/token"
_TOKEN_CACHE_KEY = "pax8_access_token_{settings_name}"
_TOKEN_TTL = 82800  # 23h — slightly less than 24h expiry


def get_pax8_client(settings_name: str) -> "Pax8Client":
    settings = frappe.get_doc("Pax8 Settings", settings_name)
    return Pax8Client(settings)


class Pax8Client:
    def __init__(self, settings):
        self.settings = settings
        self.base_url = _PROD_BASE

    def _get_token(self) -> str:
        cache_key = _TOKEN_CACHE_KEY.format(settings_name=self.settings.name)
        cached = frappe.cache.get(cache_key)
        if cached:
            return cached.decode() if isinstance(cached, bytes) else cached

        resp = requests.post(
            _TOKEN_URL,
            json={
                "grant_type": "client_credentials",
                "client_id": self.settings.client_id,
                "client_secret": self.settings.get_password("client_secret"),
                "audience": "https://api.pax8.com",
            },
            timeout=15,
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        frappe.cache.setex(cache_key, _TOKEN_TTL, token)
        return token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}"}

    def _get_all(self, path: str, params: dict = None) -> list:
        """Fetch all pages from a paginated Pax8 endpoint."""
        results = []
        page = 0
        size = 200
        base_params = dict(params or {})
        while True:
            base_params.update({"page": page, "size": size})
            resp = requests.get(
                f"{self.base_url}{path}",
                headers=self._headers(),
                params=base_params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("content", data.get("data", []))
            results.extend(content)
            total_pages = data.get("totalPages", data.get("total_pages", 1))
            if page + 1 >= total_pages or not content:
                break
            page += 1
        return results

    def get_companies(self) -> list:
        return self._get_all("/v1/companies", {"status": "Active"})

    def get_invoices(self, billing_period: str = None) -> list:
        """billing_period: YYYY-MM or None for latest."""
        params = {}
        if billing_period:
            params["billingPeriod"] = billing_period
        return self._get_all("/v1/invoices", params)

    def get_invoice_items(self, invoice_id: str) -> list:
        return self._get_all(f"/v1/invoices/{invoice_id}/items")

    def register_webhook(self, endpoint_url: str, bearer_secret: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/v1/webhooks",
            headers={**self._headers(), "Content-Type": "application/json"},
            json={
                "name": "ERPNext Invoice Import",
                "url": endpoint_url,
                "authType": "BEARER",
                "authToken": bearer_secret,
                "topics": [{"topic": "INVOICE", "filters": [{"action": "CREATED"}]}],
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
