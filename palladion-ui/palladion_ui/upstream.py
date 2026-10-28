"""The one place that talks to Palladion's HTTP API, with its errors turned into something a person can read."""
from __future__ import annotations

from typing import Any

import httpx


class UpstreamError(Exception):
    def __init__(self, status: int, message: str, code: str = "UPSTREAM_ERROR") -> None:
        super().__init__(message)
        self.status, self.message, self.code = status, message, code

    def public(self) -> dict[str, Any]:
        return {"error": {"status": self.status, "code": self.code, "message": self.message}}


class UpstreamDown(UpstreamError):
    def __init__(self, message: str = "Palladion is not reachable. Start the runtime from the model menu.") -> None:
        super().__init__(502, message, "UPSTREAM_DOWN")


_CODES = {403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT", 400: "INVALID", 422: "INVALID", 503: "UNAVAILABLE"}


def explain(response: httpx.Response) -> str:
    """Palladion answers {"detail": text} or, for a malformed body, a list of field errors."""
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    if isinstance(detail, list) and detail:
        first = detail[0]
        where = ".".join(str(part) for part in first.get("loc", ())[1:])
        return f"{where}: {first.get('msg', 'invalid')}" if where else str(first.get("msg", "invalid"))
    if isinstance(detail, str) and detail:
        return detail
    return f"Palladion answered {response.status_code}"


class Upstream:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def raw(self, method: str, path: str, token: str, *, json: Any = None,
                  params: dict[str, Any] | None = None, timeout: float | None = None) -> httpx.Response:
        try:
            response = await self.client.request(method, path, headers={"Authorization": f"Bearer {token}"},
                                                 json=json, params=params, timeout=timeout)
        except httpx.TimeoutException as error:
            raise UpstreamError(504, "Palladion did not answer in time.", "TIMEOUT") from error
        except httpx.TransportError as error:
            raise UpstreamDown() from error
        if response.status_code >= 400:
            code = _CODES.get(response.status_code, "UPSTREAM_ERROR")
            raise UpstreamError(response.status_code, explain(response), code)
        return response

    async def call(self, method: str, path: str, token: str, **options: Any) -> Any:
        response = await self.raw(method, path, token, **options)
        return response.json() if response.content else None

    async def alive(self) -> bool:
        try:
            return (await self.client.get("/health/live", timeout=2)).status_code == 200
        except httpx.HTTPError:
            return False

    async def ready(self) -> tuple[bool, str | None]:
        """(fully ready, model boundary) — a search-only server is alive but reports 503 here by design."""
        try:
            response = await self.client.get("/health/ready", timeout=5)
        except httpx.HTTPError:
            return False, None
        if response.status_code != 200:
            return False, None
        return True, response.json().get("model_boundary")
