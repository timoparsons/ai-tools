"""Allowlisted HTTP client for the Bifrost management API.

Reads are limited to a fixed GET allowlist. Writes are limited to MCP client
management (create, update, delete, reconnect) and can be switched off with
environment variables. Credentials come from the environment and are never
returned or logged.
"""
import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE = "http://127.0.0.1:8085"
GET_ALLOW = {"/health", "/api/version", "/api/config", "/api/plugins", "/api/mcp/clients"}
GET_ALLOW_LOGS = "/api/logs"
PATH_OK = re.compile(r"^/[A-Za-z0-9_\-/]*$")
ID_OK = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")
LOOPBACK = {"127.0.0.1", "localhost", "::1"}

CLIENT_ID_PATH = re.compile(r"^/api/mcp/client/([^/]+)$")
RECONNECT_PATH = re.compile(r"^/api/mcp/client/([^/]+)/reconnect$")
CREATE_PATH = "/api/mcp/client"


class BifrostError(Exception):
    pass


def writes_enabled():
    return os.environ.get("BIFROST_DISABLE_WRITES") != "1"


def base_url():
    base = os.environ.get("BIFROST_BASE_URL", DEFAULT_BASE).rstrip("/")
    host = urllib.parse.urlparse(base).hostname or ""
    if host not in LOOPBACK and os.environ.get("BIFROST_ALLOW_REMOTE") != "1":
        raise BifrostError("Refusing non-loopback BIFROST_BASE_URL (set BIFROST_ALLOW_REMOTE=1 to override)")
    return base


def _headers():
    h = {"Accept": "application/json"}
    key = os.environ.get("BIFROST_API_KEY")
    user = os.environ.get("BIFROST_ADMIN_USER")
    pw = os.environ.get("BIFROST_ADMIN_PASSWORD")
    if key:
        h["Authorization"] = "Bearer " + key
    elif user and pw:
        h["Authorization"] = "Basic " + base64.b64encode((user + ":" + pw).encode()).decode()
    if os.environ.get("BIFROST_SETUP_TOKEN"):
        h["X-Bifrost-Setup-Token"] = os.environ["BIFROST_SETUP_TOKEN"]
    return h


def _id_from(pattern, path):
    m = pattern.match(path)
    return m and ID_OK.match(m.group(1))


def _check_path(path, method):
    if not PATH_OK.match(path) or ".." in path or "//" in path:
        raise BifrostError("Path not allowed")
    if method == "GET":
        ok = path in GET_ALLOW or (path == GET_ALLOW_LOGS and os.environ.get("BIFROST_ALLOW_LOGS") == "1")
        if not ok:
            raise BifrostError("GET not allowlisted: " + path)
        return
    if method == "POST" and _id_from(RECONNECT_PATH, path):
        if os.environ.get("BIFROST_DISABLE_RECONNECT") == "1":
            raise BifrostError("Reconnect disabled by configuration")
        return
    write_ok = (method == "POST" and path == CREATE_PATH) or (
        method in ("PUT", "DELETE") and _id_from(CLIENT_ID_PATH, path))
    if not write_ok:
        raise BifrostError("%s not allowlisted: %s" % (method, path))
    if not writes_enabled():
        raise BifrostError("MCP client writes disabled by configuration (BIFROST_DISABLE_WRITES=1)")


def request(method, path, params=None, body=None, timeout=15):
    _check_path(path, method)
    url = base_url() + path
    if params:
        clean = {k: v for k, v in params.items() if v not in (None, "")}
        if clean:
            url += "?" + urllib.parse.urlencode(clean)
    data = None
    if method in ("POST", "PUT"):
        data = json.dumps(body if body is not None else {}).encode()
    headers = _headers()
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read(5_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read(2000).decode("utf-8", "replace")
        except Exception:
            pass
        raise BifrostError("HTTP %s from Bifrost for %s %s" % (e.code, method, path)
                           + (": " + detail if detail else "")) from None
    except Exception as e:
        raise BifrostError("Cannot reach Bifrost (%s)" % type(e).__name__) from None
    try:
        return json.loads(text) if text.strip() else {}
    except ValueError:
        return {"raw": text[:500]}


def get(path, params=None):
    return request("GET", path, params)


def post(path, body=None):
    return request("POST", path, body=body)


def put(path, body):
    return request("PUT", path, body=body)


def delete(path):
    return request("DELETE", path)
