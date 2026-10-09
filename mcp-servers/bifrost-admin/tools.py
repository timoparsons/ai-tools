"""Tool implementations: plain functions returning masked JSON text."""
import functools
import os
import re

import bifrost_api as api
from masking import dumps, env_names, mask_tree, safe_args, safe_url, scrub_string

NAME_OK = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
ENV_NAME_OK = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
ENV_REF_OK = re.compile(r"^env\.[A-Za-z_][A-Za-z0-9_]{0,127}$")
HEADER_NAME_OK = re.compile(r"^[A-Za-z0-9\-]{1,64}$")
URL_OK = re.compile(r"^https?://[^\s@?#]+$")
PROTECTED = {"bifrost_admin"}
CONNECTION_TYPES = ("http", "sse", "stdio")


def _safe(fn):
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except api.BifrostError as e:
            return "Error: %s" % scrub_string(str(e))
    return wrapper


def _names(items, field="name"):
    out = []
    for it in items or []:
        out.append(it.get(field) or it.get("id") or "?" if isinstance(it, dict) else str(it))
    return out


def _tool_names(c):
    tools = c.get("tools") or []
    return [t.get("name") if isinstance(t, dict) else str(t) for t in tools]


def summarise(c, with_tools=False):
    cfg = c.get("config") if isinstance(c.get("config"), dict) else c
    stdio = cfg.get("stdio_config") or {}
    out = {
        "name": cfg.get("name"),
        "client_id": cfg.get("client_id") or c.get("client_id"),
        "connection_type": cfg.get("connection_type"),
        "url": safe_url(cfg.get("connection_string")) if cfg.get("connection_string") else None,
        "stdio": {
            "command": scrub_string(stdio.get("command")),
            "args": safe_args(stdio.get("args")),
            "env_names": env_names(stdio.get("envs")),
        } if stdio else None,
        "auth_type": cfg.get("auth_type"),
        "header_names": sorted((cfg.get("headers") or {}).keys()),
        "per_user_header_keys": sorted(cfg.get("per_user_header_keys") or []),
        "disabled": cfg.get("disabled", c.get("disabled")),
        "state": c.get("state") or cfg.get("state"),
        "last_failure": scrub_string(c.get("last_failure") or cfg.get("last_failure")),
        "tool_count": len(_tool_names(c)),
        "tools_to_execute": cfg.get("tools_to_execute"),
        "allow_on_all_virtual_keys": cfg.get("allow_on_all_virtual_keys"),
        "is_code_mode_client": cfg.get("is_code_mode_client"),
        "virtual_keys": _names(cfg.get("vk_configs"), "virtual_key_name"),
    }
    if with_tools:
        out["tools"] = _tool_names(c)
    return out


def _clients(search=None, state=None, limit=100):
    limit = max(1, min(int(limit or 100), 100))
    data = api.get("/api/mcp/clients", {"search": search, "state": state, "limit": limit})
    return data.get("clients", []) if isinstance(data, dict) else data


def _find(client):
    """Exact match on name or client_id, or None."""
    for c in _clients(search=client):
        s = summarise(c)
        if client in (s["name"], s["client_id"]):
            if s["client_id"] and api.ID_OK.match(s["client_id"]):
                return s
    # search may not match on id; fall back to a full scan
    for c in _clients():
        s = summarise(c)
        if client in (s["name"], s["client_id"]) and s["client_id"] and api.ID_OK.match(s["client_id"]):
            return s
    return None


def _tools_list(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = [v.strip() for v in value.split(",") if v.strip()]
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise api.BifrostError("tools_to_execute must be a list of tool names, or [\"*\"]")
    return value


def _truthy(v):
    return v is True or (isinstance(v, str) and v.lower() in ("true", "1", "yes"))


# ---------------------------------------------------------------- read tools

@_safe
def bifrost_status():
    """Bifrost health and version."""
    return dumps({"health": mask_tree(api.get("/health")), "version": mask_tree(api.get("/api/version"))})


@_safe
def bifrost_list_mcp_clients(search="", state="", limit=100):
    """List MCP clients registered in Bifrost (masked summary, no secrets)."""
    return dumps([summarise(c) for c in _clients(search, state, limit)])


@_safe
def bifrost_get_mcp_client(name):
    """One MCP client by name or client_id, including tool names (masked)."""
    for c in _clients(search=name):
        s = summarise(c, with_tools=True)
        if name in (s["name"], s["client_id"]):
            return dumps(s)
    return "No MCP client named %r" % name


@_safe
def bifrost_get_config():
    """Bifrost core configuration with secrets removed."""
    return dumps(mask_tree(api.get("/api/config")))


@_safe
def bifrost_list_plugins():
    """Installed Bifrost plugins with secrets removed."""
    return dumps(mask_tree(api.get("/api/plugins")))


# --------------------------------------------------------------- write tools

@_safe
def bifrost_reconnect_mcp_client(client, confirm=False):
    """Reconnect one MCP client (name or id). Does nothing unless confirm is true."""
    target = _find(client)
    if not target:
        return "No MCP client named %r" % client
    if not _truthy(confirm):
        return "Dry run: would reconnect %s (%s). Call again with confirm=true." % (target["name"], target["client_id"])
    api.post("/api/mcp/client/%s/reconnect" % target["client_id"])
    return "Reconnect requested for %s" % target["name"]


@_safe
def bifrost_create_mcp_client(name, connection_type, url="", command="", args=None, env_names=None,
                              header_env_refs=None, tools_to_execute=None, is_code_mode_client=True,
                              is_ping_available=None, confirm=False):
    """Register a new MCP client in Bifrost. Dry run unless confirm is true.

    connection_type: http, sse or stdio.
    url: for http/sse (no credentials or query string in the URL).
    command, args, env_names: for stdio. env_names are variable NAMES only; values are
      inherited from the Bifrost process environment. stdio creation is off unless
      BIFROST_ALLOW_STDIO_CREATE=1 is set for this server.
    header_env_refs: {"Header-Name": "env.VAR_NAME"} for http/sse auth. Literal secret
      values are refused: put the value in Bifrost's environment, or add the header in
      the Bifrost UI after creating the client.
    tools_to_execute: list of tool names, default ["*"].
    """
    if not NAME_OK.match(name or ""):
        raise api.BifrostError("name must be ASCII letters, digits and underscores, not starting with a digit")
    if connection_type not in CONNECTION_TYPES:
        raise api.BifrostError("connection_type must be one of %s" % ", ".join(CONNECTION_TYPES))
    if _find(name):
        raise api.BifrostError("A client named %r already exists; delete or update it instead" % name)

    body = {
        "name": name,
        "connection_type": connection_type,
        "tools_to_execute": _tools_list(tools_to_execute) or ["*"],
        "is_code_mode_client": _truthy(is_code_mode_client) if is_code_mode_client is not None else True,
        "auth_type": "none",
    }
    if is_ping_available is not None:
        body["is_ping_available"] = _truthy(is_ping_available)

    if connection_type in ("http", "sse"):
        if command or args or env_names:
            raise api.BifrostError("command/args/env_names are only for stdio clients")
        if not URL_OK.match(url or ""):
            raise api.BifrostError("url must be http(s)://host/path with no credentials, query string or fragment")
        body["connection_string"] = url
        if header_env_refs:
            if not isinstance(header_env_refs, dict):
                raise api.BifrostError("header_env_refs must be an object of header name to env.VAR_NAME")
            headers = {}
            for k, v in header_env_refs.items():
                if not HEADER_NAME_OK.match(str(k)):
                    raise api.BifrostError("Invalid header name %r" % k)
                if not isinstance(v, str) or not ENV_REF_OK.match(v):
                    raise api.BifrostError(
                        "Header %s: value must be an env reference like env.MY_TOKEN. Literal secrets are "
                        "refused; add the header in the Bifrost UI instead." % k)
                headers[k] = v
            body["auth_type"] = "headers"
            body["headers"] = headers
    else:
        if os.environ.get("BIFROST_ALLOW_STDIO_CREATE") != "1":
            raise api.BifrostError("Creating stdio clients is disabled (it runs a command on the Bifrost host). "
                                   "Set BIFROST_ALLOW_STDIO_CREATE=1 for bifrost_admin, or add it in the Bifrost UI.")
        if url or header_env_refs:
            raise api.BifrostError("url/header_env_refs are not used for stdio clients")
        if not command or not os.path.isabs(command) and "/" in command:
            raise api.BifrostError("command must be an absolute path or a bare program name on PATH")
        if args is not None and (not isinstance(args, list) or not all(isinstance(a, str) for a in args)):
            raise api.BifrostError("args must be a list of strings")
        names = env_names or []
        if not isinstance(names, list) or not all(isinstance(n, str) and ENV_NAME_OK.match(n) for n in names):
            raise api.BifrostError("env_names must be a list of variable NAMES (no NAME=value)")
        body["stdio_config"] = {"command": command, "args": args or [], "envs": names}

    preview = {k: v for k, v in body.items() if k not in ("stdio_config",)}
    if "stdio_config" in body:
        preview["stdio"] = {"command": command, "args": safe_args(args), "env_names": names}
    if not _truthy(confirm):
        return dumps({"dry_run": True, "would_create": mask_tree(preview),
                      "next": "Call again with confirm=true to create it."})
    api.post(api.CREATE_PATH, body)
    created = _find(name)
    return dumps({"created": name, "client": created or "created; not yet listed, check again shortly"})


@_safe
def bifrost_update_mcp_client(client, disabled=None, tools_to_execute=None, is_code_mode_client=None,
                              is_ping_available=None, confirm=False):
    """Change an existing client's enabled state, tool allowlist, code-mode or ping setting.

    Only the fields you pass are changed. Connection details, headers and env values are
    not editable here; use the Bifrost UI for those. Dry run unless confirm is true.
    """
    target = _find(client)
    if not target:
        return "No MCP client named %r" % client
    if target["name"] in PROTECTED and disabled is not None and _truthy(disabled):
        raise api.BifrostError("Refusing to disable %s (it would remove these tools)" % target["name"])
    changes = {}
    if disabled is not None:
        changes["disabled"] = _truthy(disabled)
    if tools_to_execute is not None:
        changes["tools_to_execute"] = _tools_list(tools_to_execute)
    if is_code_mode_client is not None:
        changes["is_code_mode_client"] = _truthy(is_code_mode_client)
    if is_ping_available is not None:
        changes["is_ping_available"] = _truthy(is_ping_available)
    if not changes:
        return "Nothing to change. Pass disabled, tools_to_execute, is_code_mode_client or is_ping_available."
    body = dict(changes, name=target["name"])
    if not _truthy(confirm):
        return dumps({"dry_run": True, "client": target["name"], "client_id": target["client_id"],
                      "current": {k: target.get(k) for k in changes if k in target},
                      "would_set": changes, "next": "Call again with confirm=true to apply."})
    api.put("/api/mcp/client/%s" % target["client_id"], body)
    return dumps({"updated": target["name"], "client": _find(target["client_id"]) or _find(target["name"])})


@_safe
def bifrost_delete_mcp_client(client, confirm=False):
    """Remove an MCP client from Bifrost (name or id). Dry run unless confirm is true.

    Clients declared in Bifrost's config.json come back on restart unless removed there too.
    """
    target = _find(client)
    if not target:
        return "No MCP client named %r" % client
    if target["name"] in PROTECTED:
        raise api.BifrostError("Refusing to delete %s from itself" % target["name"])
    if not _truthy(confirm):
        return dumps({"dry_run": True, "would_delete": target, "next": "Call again with confirm=true to delete."})
    api.delete("/api/mcp/client/%s" % target["client_id"])
    still = _find(target["client_id"])
    return dumps({"deleted": target["name"], "client_id": target["client_id"],
                  "verified_gone": still is None})
