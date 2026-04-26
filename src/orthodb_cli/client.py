from __future__ import annotations

import json
import time
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .errors import OrthoDBError

API_BASE = "https://data.orthodb.org/v12"
TEXT_COMMANDS = {"fasta", "tab", "og_description", "orthodb_release_id"}
RATE_LIMITED_COMMANDS = {"blast", "fasta", "tab"}


class OrthoDBClient:
    def __init__(self, base_url: str = API_BASE, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._last_limited_request = 0.0

    def build_url(self, command: str, params: Mapping[str, Any] | None = None) -> str:
        command = command.strip("/")
        query = clean_params(params or {})
        url = f"{self.base_url}/{command}"
        if query:
            url = f"{url}?{urlencode(query, doseq=False)}"
        return url

    def request(self, command: str, params: Mapping[str, Any] | None = None) -> Any:
        command = command.strip("/")
        if command in RATE_LIMITED_COMMANDS:
            self._rate_limit()

        url = self.build_url(command, params)
        req = Request(url, headers={"User-Agent": "orthodb-cli/0.1"})
        try:
            with urlopen(req, timeout=self.timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                body = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OrthoDBError(f"OrthoDB HTTP {exc.code} for {url}: {detail}") from exc
        except URLError as exc:
            raise OrthoDBError(f"OrthoDB request failed for {url}: {exc.reason}") from exc

        text = body.decode("utf-8", errors="replace")
        if command not in TEXT_COMMANDS and "json" in content_type.lower():
            parsed = json.loads(text)
            if isinstance(parsed, dict) and parsed.get("status") == "error":
                message = parsed.get("message") or "unknown OrthoDB API error"
                raise OrthoDBError(str(message))
            return parsed
        if command not in TEXT_COMMANDS:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        return text

    def _rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_limited_request
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self._last_limited_request = time.monotonic()


def clean_params(params: Mapping[str, Any]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if value is False:
            continue
        if isinstance(value, (list, tuple)):
            cleaned[key] = ",".join(str(item) for item in value)
        else:
            cleaned[key] = str(value)
    return cleaned

