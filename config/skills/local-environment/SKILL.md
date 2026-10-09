---
name: local-environment
description: Use when the user names a local system (Home Assistant, Proxmox, AdGuard, UniFi, Synology, n8n, Navidrome, PriceBuddy, Obsidian, ComfyUI, DaVinci Resolve, Fusion 360, Ansible, Bifrost, local files) or says 'in' plus a system name. Routes to the bifrost-gateway server.
---

# Local environment (bifrost-gateway)

All local systems are MCP servers behind one gateway, bifrost-gateway. Their tools are not in the tool list; discover them on demand. Do not narrate the discovery, just do it and act. Never tell the user a system is unavailable until you have listed the gateway's servers.

## Reaching a system

1. Load the gateway tools with tool search (query "bifrost"): listToolFiles, readToolFile, getToolDocs, executeToolCode.
2. `listToolFiles` shows one `servers/NAME.pyi` per system.
3. `readToolFile` on that .pyi gives the authoritative callable names and parameters. Read it once per session before the first call, even if the names look familiar. Never guess from memory.
4. `getToolDocs(server, tool)` when a signature is not enough. Call it as a top-level tool; inside executeToolCode it fails with `undefined: getToolDocs`.
5. `executeToolCode` runs `result = server.tool(param=value)`.

The execution environment is Starlark, not full Python: no try/except, no classes, no imports, no f-strings (use % formatting), keyword arguments only, and every call starts in a fresh scope. Pass dict and list arguments as real objects, never JSON strings. Failures cannot be caught in code, so check a result before chaining a write onto it. Batch read-only lookups into one call. If a host or tool fails twice, stop and report instead of retrying. Never replay a call that already changed something.

## Routing map

| User says | Server | Covers | Dedicated skill |
|---|---|---|---|
| Home Assistant, lights, sensors, automations, scenes, dashboards | `home_assistant` | Entities, services, automations, scripts, helpers, devices, areas, history, logs, backups, HACS | home-assistant-mcp |
| Proxmox, VMs, containers, LXC, snapshots, backups | `proxmox` | Node, QEMU VMs, LXC, snapshots, backups, ISOs, storage, task logs | proxmox-mcp |
| Ansible, playbooks, run a command on a host | `ansible` | Inventory, ad-hoc tasks, services, playbooks | ansible-mcp |
| AdGuard, DNS, ad blocking, DHCP, blocklists, query log | `adguard_home` | DNS config, filtering, rewrites, clients, DHCP leases, stats | none yet |
| UniFi, UDM, router, network, Wi-Fi, clients, VLANs, firewall, switch ports | `unifi` | UDM SE (10.1.1.1) read-only: devices, clients, networks, WLANs, firewall policies, NAT, routes, VPN, events, alarms, stats, DPI, traffic flows | none yet |
| Synology, NAS, Calliope, DSM, shares, storage, disks, Container Manager | `synology_calliope` | Calliope NAS (10.1.1.10) read-only: system info and health, storage pools and disks, shared folders, users and groups, files and search, backup and scheduled tasks, packages, containers, logs, security settings, UPS | none yet |
| n8n, workflows, webhooks, executions | `n8n` | Workflow CRUD, validation, executions, templates, credentials, data tables | none yet |
| Navidrome, music, playlists, albums, radio | `navidrome` | Library search, playlists, stars and ratings, play history, radio | none yet |
| PriceBuddy, prices, deals, price drops, tracked products | `pricebuddy` | Tracked products, stores, tags, price history, drops, lowest price, deal insights, adding products | pricebuddy-mcp |
| Obsidian, notes, vault, tasks, daily note, links | `obsidian` | Local REST API plugin's built-in MCP: read, section patch, frontmatter, full-text and JsonLogic search, links/backlinks, commands. Needs Obsidian open | obsidian-mcp |
| ComfyUI, generate image/video/audio, LoRA, RunPod | `comfyuimcp` | Workflows, generation, queue, models, custom nodes, training | none yet |
| DaVinci Resolve, LUTs, DCTL, Resolve scripting | `davinci_resolve` | Status/launch, scripting API, LUT and DCTL files, script execution | none yet |
| Fusion 360, CAD, schematic, board | `fusion_360` | Active model read/execute, electronics data, screenshots | none yet |
| Files, folders, code on the Mac Studio | `filesystem` | Read, write, list, search, move in allowed directories | filesystem-mcp |
| Bifrost, the gateway, MCP clients/servers | `bifrost_admin` | Status, masked config, list/get clients; create, update (enable/disable, tool allowlist), delete, reconnect clients | none yet |

If Ansible is requested and no `ansible` server is listed, say so and suggest reconnecting the Ansible MCP service (LXC 157, http://10.1.1.57:8000/mcp). Restarting `ansible-mcp.service` drops the gateway session.

## Quirks for servers without a skill yet

- `comfyuimcp`: each tool takes an `action` argument and does several things. `comfyuimcp.list_tools` returns a catalog of capabilities.
- `bifrost_admin`: every write is a dry run until called again with `confirm="true"`; show the dry run to the user, then confirm. Header values must be `env.VAR_NAME` references, never literal secrets (refused); if a secret isn't in Bifrost's environment, create the client without it and ask the user to add the header in the Bifrost UI. Creating stdio clients is off unless `BIFROST_ALLOW_STDIO_CREATE=1`. It refuses to delete or disable itself. Refusals come back as errors and abort the script, so run each write in its own `executeToolCode` call. Reconnecting `bifrost_admin` itself times out (it restarts mid-call); check its `.pyi` afterwards. Code and README: `ai-tools/mcp-servers/bifrost-admin/`.
- `unifi`: read-only by design. It logs in as a View Only local account and runs with write policies off, and Bifrost allows only `get_`/`list_` tools plus `lookup_by_ip`, `recent_events` and `tool_index`. `unifi_execute` and `unifi_batch` are deliberately excluded because they would bypass the allowlist. If a change is requested, say it is out of scope rather than looking for a workaround. Container `unifi-network-mcp` on management (10.1.1.30:8096), env at `/opt/unifi-mcp/unifi.env`; it runs `UNIFI_NETWORK_MCP_CONTENT_MODE=compat` because Bifrost code mode drops `structuredContent`. Quote env-file values that contain a dollar sign, or Compose substitutes it.
- `synology_calliope`: read-only by design. Bifrost allows 52 of 71 tools: the `get_`/`list_` tools plus `search_files` and `check_dsm_update`. File writes, shared-folder changes, downloads, task runs, container/VM/package state, DSM update install, reboot and shutdown are deliberately excluded, and the server also runs with `SYNOLOGY_ENABLE_POWER_CONTROL=false`. If a change is requested, say it is out of scope rather than looking for a workaround. Logs in to DSM at https://10.1.1.10:5501 as `local-api`. Container `synology-mcp-calliope` (rafalr100/synology-mcp, built locally from `/opt/synology-mcp`) on management (10.1.1.30:8095), env at `/opt/synology-mcp/calliope.env`.
- `davinci_resolve`: prefer `run_script` over `run_script_unsafe`. Check `get_resolve_status` first and use `launch_resolve` only if the user wants Resolve started.

## Safety defaults

Read and list freely. State exactly what will change and where, get an explicit go-ahead in chat, then act, before anything that:

- Deletes or removes data: any delete or remove tool on any server, `querylog_clear`, `stats_reset`.
- Interrupts a running system: stop, reset, shutdown or restart on VMs and containers, `ha_restart`, Proxmox restore or rollback.
- Can break household services: AdGuard `dns_set_config`, `dhcp_set_config`, `dhcp_reset`, `global_set_protection`, `access_set_list`, `filtering_set_rules`.
- Controls physical or security devices in Home Assistant: locks, alarms, garage doors, heating, anything that moves or unlocks.
- Touches secrets or overwrites files: `n8n_manage_credentials`, `write_file` over an existing file, Obsidian `vault_write` over an existing note, `run_script_unsafe`.
- Changes the gateway: `bifrost_create_mcp_client`, `bifrost_update_mcp_client`, `bifrost_delete_mcp_client`, `bifrost_reconnect_mcp_client` (with `confirm`). Also Obsidian `command_execute`, which can run any command-palette action.

Do not rely on a tool's own safeguards. Proxmox `approval_token` is not enforced (confirmed on `delete_snapshot`), so confirmation has to come from you. See proxmox-mcp.

## Homelab and AI context lives in the vault

Re-fetch the live note instead of trusting memory or any summary here. Use obsidian-mcp to read them.

- `Overview/Area – HomeLab.md`: index, open tasks, and what is currently fragile. Check it before touching a service.
- `Library/HomeLab/`: architecture, network topology, Proxmox LXC census, maintenance cheatsheet, install logs.
- `Overview/Area – AI.md`: index and open tasks for the AI stack (MCP servers, local LLMs, Claude, generative media).
- `Library/AI/`: all `AI –` reference notes, including:
- `Library/AI/Wiki – AI – MCP Server Stack.md`: how the MCP servers are hosted.
- `Library/AI/Wiki – AI – Local LLM Stack.md`: local inference engines, models and clients.

## Changing skills

Claude loads the user's saved account skills. The files in `/Users/tim/Documents/Coding/ai-tools/skills/<name>/SKILL.md` are the source copies; editing them alone changes nothing Claude sees.

1. Read the current saved skill (the synced copy in the session's skills folder) and the source file, whole.
2. Edit the source file with filesystem `edit_file`, dry run first.
3. Propose the complete updated SKILL.md as a review card (`propose_skills`, kind `improvement`). A card holds up to three skills; send another card for the rest.
4. The user saves it from the card in the app. Until then the old version stays live.

Keep the source file and the saved skill identical. `Library/External Docs/ai-tools/skills/` in the vault is a read-only mirror of the repo that updates when the repo syncs; never edit it. When a vault note that skills point to moves or is renamed, search the source skills for the old path and send cards for every skill that changes.

## Working conventions

- Prefer minimal, targeted changes over refactors unless asked. Assume the existing system works.
- After a fix or feature, propose a short changelog entry (date, what changed, why) formatted to paste into the relevant Obsidian note. Do not write into the vault unless asked.
- If the root cause is unclear, say what you have ruled out, not just what you tried.
- When writing notes through MCP, never put a line starting with # inside a code fence. The housekeeping workflow has been turning those into headings and breaking the fence (observed 2026-10-06, cause inferred). Use trailing comments or prose instead.
