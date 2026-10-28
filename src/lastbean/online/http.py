"""Tiny async JSON-over-HTTP client without threads (DESIGN.md section 17).

Desktop: asyncio streams (plain HTTP or TLS). Browser (pygbag): the page's `fetch`, started
through a small JS helper and polled each frame. Both return (status, json_or_None);
status 0 means the request did not reach the server (offline, timeout, CORS, ...).
"""

from __future__ import annotations

import asyncio
import json
import ssl
import sys
from typing import Any
from urllib.parse import urlsplit

TIMEOUT_S = 8.0


async def request(method: str, url: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, Any]:
    if sys.platform == "emscripten":
        return await _browser_request(method, url, body, headers or {})
    try:
        return await asyncio.wait_for(_stream_request(method, url, body, headers or {}), TIMEOUT_S)
    except (TimeoutError, OSError, ValueError, ssl.SSLError):
        return 0, None


async def _stream_request(method: str, url: str, body: dict | None, headers: dict) -> tuple[int, Any]:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ValueError("only http and https URLs")
    tls = parts.scheme == "https"
    port = parts.port or (443 if tls else 80)
    host = parts.hostname or ""
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    payload = json.dumps(body).encode("utf-8") if body is not None else b""
    lines = [f"{method} {path} HTTP/1.1", f"Host: {parts.netloc}", "Connection: close", "Accept: application/json"]
    if body is not None:
        lines += ["Content-Type: application/json", f"Content-Length: {len(payload)}"]
    lines += [f"{k}: {v}" for k, v in headers.items()]
    reader, writer = await asyncio.open_connection(host, port, ssl=ssl.create_default_context() if tls else None)
    try:
        writer.write(("\r\n".join(lines) + "\r\n\r\n").encode("utf-8") + payload)
        await writer.drain()
        raw = await reader.read()
    finally:
        writer.close()
    return _parse_response(raw)


def _parse_response(raw: bytes) -> tuple[int, Any]:
    head, _, rest = raw.partition(b"\r\n\r\n")
    head_lines = head.decode("iso-8859-1").split("\r\n")
    status = int(head_lines[0].split(" ")[1])
    fields = {k.strip().lower(): v.strip() for k, _, v in (h.partition(":") for h in head_lines[1:])}
    if fields.get("transfer-encoding", "").lower() == "chunked":
        rest = _dechunk(rest)
    try:
        return status, json.loads(rest.decode("utf-8")) if rest else None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return status, None


def _dechunk(data: bytes) -> bytes:
    out = bytearray()
    while data:
        size_line, _, data = data.partition(b"\r\n")
        size = int(size_line.split(b";")[0], 16)
        if size == 0:
            break
        out += data[:size]
        data = data[size + 2 :]
    return bytes(out)


# ---------------------------------------------------------------------------- browser

_JS_HELPER = """
window.lbs = window.lbs || {next: 0, res: {}};
window.lbsFetch = function (method, url, body, headers) {
  const id = String(window.lbs.next++);
  const opts = {method: method, headers: JSON.parse(headers)};
  if (body) { opts.body = body; opts.headers["Content-Type"] = "application/json"; }
  fetch(url, opts)
    .then(r => r.text().then(t => { window.lbs.res[id] = JSON.stringify({status: r.status, body: t}); }))
    .catch(e => { window.lbs.res[id] = JSON.stringify({status: 0, body: String(e)}); });
  return id;
};
window.lbsTake = function (id) {
  const v = window.lbs.res[id];
  if (v === undefined) return "";
  delete window.lbs.res[id];
  return v;
};
"""
_helper_installed = False


async def _browser_request(method: str, url: str, body: dict | None, headers: dict) -> tuple[int, Any]:
    global _helper_installed
    import platform  # pygbag's bridge to the page

    window = platform.window
    if not _helper_installed:
        window.eval(_JS_HELPER)
        _helper_installed = True
    rid = str(window.lbsFetch(method, url, json.dumps(body) if body is not None else "", json.dumps(headers)))
    waited = 0.0
    while waited < TIMEOUT_S:
        raw = str(window.lbsTake(rid) or "")
        if raw:
            res = json.loads(raw)
            try:
                return int(res["status"]), json.loads(res["body"]) if res["body"] else None
            except json.JSONDecodeError:
                return int(res["status"]), None
        await asyncio.sleep(0.05)
        waited += 0.05
    return 0, None
