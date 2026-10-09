# bifrost-admin

Secret-masking MCP server for the Bifrost management API. Register it **inside Bifrost** as a stdio client so Claude can discover it on demand, read the gateway's config, and manage MCP clients.

## Tools
Read:
- `bifrost_status` - health and version
- `bifrost_list_mcp_clients(search, state, limit)` - masked summary of every registered MCP client
- `bifrost_get_mcp_client(name)` - one client including tool names
- `bifrost_get_config`, `bifrost_list_plugins` - masked config

Write (every one is a dry run unless `confirm=true`):
- `bifrost_reconnect_mcp_client(client)`
- `bifrost_create_mcp_client(name, connection_type, url, command, args, env_names, header_env_refs, tools_to_execute, is_code_mode_client, is_ping_available)`
- `bifrost_update_mcp_client(client, disabled, tools_to_execute, is_code_mode_client, is_ping_available)` - only the fields passed are changed
- `bifrost_delete_mcp_client(client)` - reports whether the client is verifiably gone afterwards

## Safety
- GET allowlist: `/health`, `/api/version`, `/api/config`, `/api/plugins`, `/api/mcp/clients`. Providers, governance (virtual keys), sessions, OAuth, vault and logs are not reachable (`/api/logs` opt-in with `BIFROST_ALLOW_LOGS=1`).
- Write allowlist: `POST /api/mcp/client`, `PUT|DELETE /api/mcp/client/{id}`, `POST /api/mcp/client/{id}/reconnect`. Nothing else.
- Kill switches: `BIFROST_DISABLE_WRITES=1` (create/update/delete), `BIFROST_DISABLE_RECONNECT=1`.
- **No secrets pass through the model.** Header values must be `env.VAR_NAME` references that Bifrost resolves from its own environment; literal values are refused. stdio `env_names` are names only. For a secret that is not in Bifrost's environment, create the client without it and add the header in the Bifrost UI.
- **stdio creation is off by default** because it makes Bifrost run a command on this Mac. Enable with `BIFROST_ALLOW_STDIO_CREATE=1` on this client.
- `bifrost_admin` refuses to delete or disable itself.
- Output is masked server-side (`masking.py`): sensitive keys, header/env values, URL userinfo and query strings, token-shaped strings. Fails closed. Error text from Bifrost is scrubbed too.
- Talks to `http://127.0.0.1:8085` by default and refuses non-loopback hosts unless `BIFROST_ALLOW_REMOTE=1`.
- Credentials are read from the environment only: `BIFROST_API_KEY` (Bearer), or `BIFROST_ADMIN_USER` + `BIFROST_ADMIN_PASSWORD` (Basic), optional `BIFROST_SETUP_TOKEN`.

## Install (on the Mac Studio)
    cd ~/Documents/Coding/ai-tools/mcp-servers/bifrost-admin
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/python test_bifrost_admin.py

## Register in Bifrost
Add an MCP client: connection type stdio, command = absolute path to `.venv/bin/python`, args = absolute path to `server.py`, envs = the credential variable names. Leave "allow on all virtual keys" off. After changing the code, reconnect the client (or toggle it off and on) so Bifrost restarts the process.

## Status
- Read tools and reconnect: verified against live Bifrost v2.2.4.
- Create/update/delete (added 2026-10-06): 15 unit tests against a fake Bifrost, plus a live round-trip on v2.2.4 (created an http client, disabled it with a partial PUT that kept its URL and settings, deleted it, confirmed gone). Not yet verified live: stdio creation, and whether a partial PUT keeps existing headers on a header-auth client. Previous version is in `backup-2026-10-06/`.
- Bifrost code mode treats an `Error: ...` result as a failed call, so refusals abort the script. Run writes in their own executeToolCode call.
