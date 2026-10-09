---
name: ansible-mcp
description: Use when managing hosts, LXC containers, services, playbooks or ad-hoc commands through the Ansible MCP server (inventory, ansible_task, ansible_playbook).
---

# ansible-mcp

Reach this server through bifrost-gateway (see local-environment): `listToolFiles`, then `readToolFile` on `servers/ansible.pyi`, then `executeToolCode`. Read the stub once per session.

**Status 2026-10-06:** the `ansible` server was missing from the gateway earlier in the day and reappeared later. Verified live through it: `ansible-mcp` is active under systemd on LXC 157 and listening on port 8000 (`http://10.1.1.57:8000/mcp`), and there is no ansible container on management (a leftover rsync cron entry and `/opt/ansible-mcp` remain there). Restarting `ansible-mcp.service` drops the gateway session, so a missing server may just need reconnecting. If the server is not listed, say so instead of guessing.

## Known issues

**`_raw_params` mangling (`module="shell"` and `"command"`): patched 2026-07-05.** Both modules work normally, with no `true;` prefix needed. If the first word of a command starts silently vanishing again, the patch has probably been lost (it lives in a `uv` cache path that can be replaced). Full root cause, the patch and the file path are in `Library/AI/Wiki – AI – MCP Server Stack.md`, section "Ansible MCP server". Fallback while re-diagnosing: prefix `cmd` with `true; `.

**Go template syntax `{{ }}` is still broken (unrelated bug).** Commands containing it, such as `docker ps --format 'table {{.Names}}...'`, fail with `Syntax error in template: unexpected '.'`, because the whole `cmd` string goes through Ansible's Jinja2 templating first. Avoid it entirely: use plain `docker ps`, or post-process with `awk`, `grep` or `cut`.

**Other notes**
- `ansible_inventory(show_hostvars=True)` resolves a friendly hostname to its `ansible_host` IP. Useful before cross-referencing Proxmox output, which uses node and vmid.
- `args` must be a dictionary object, never a JSON string. A string raises a pydantic validation error.
- If a host is unreachable after 2 attempts, or a task fails twice, stop and report to the user.

## Calling convention

```python
result = ansible.ansible_task(hosts="myhost", module="shell", args={"cmd": "ls /opt"}, become=True)
print(result)
```

| Module | Keys | Example |
|---|---|---|
| `shell` | `cmd` | `"cat /opt/*.yml"` |
| `command` | `cmd` | `"ls /opt"` |
| `ping` | none | omit `args` |
| `find` | `paths`, `patterns` | `"/opt"`, `"*.yml"` |
| `copy` | `src`, `dest` | `"/tmp/x"`, `"/opt/x"` |
| `service` | `name`, `state` | `"nginx"`, `"started"` |

## Standard workflows

Find and read a file on a remote host:

```python
result = ansible.ansible_ping(hosts="management")
result = ansible.ansible_task(hosts="management", module="find", args={"paths": "/opt", "patterns": "docker-compose*.yml"})
result = ansible.ansible_task(hosts="management", module="shell", args={"cmd": "cat /opt/docker-compose.yml"})
```

Discover hosts:

```python
result = ansible.ansible_inventory()
result = ansible.inventory_find_host(hostname="NAME")
```

Manage a service (prefer this over `ansible_task` with the `service` module):

```python
result = ansible.ansible_ping(hosts="NAME")
result = ansible.ansible_service_manager(hosts="NAME", service="nginx", state="started")
```

Run a playbook. Dry-run first (`check=True` is `--check --diff`) and review it:

```python
result = ansible.list_projects()
result = ansible.project_playbooks(project="PROJECT")
result = ansible.ansible_playbook(project="PROJECT", playbook="site.yml", limit="management", check=True, diff=True)
```

Then, after the user has seen the dry-run, the real run:

```python
result = ansible.ansible_playbook(project="PROJECT", playbook="site.yml", limit="management")
```

`ansible_playbook` takes `limit` (not `hosts`) to scope which hosts run.

## Host unreachable

1. Check spelling with `inventory_find_host` to confirm the exact hostname.
2. Try the host's IP address instead of its name.
3. After 2 timeout failures, report to the user and stop.

## Tools

| Tool | When to use |
|---|---|
| `ansible_inventory` | List all hosts and groups |
| `inventory_find_host` | Details on one host |
| `inventory_graph` | Inventory in graph form |
| `ansible_ping` | Test SSH connectivity |
| `ansible_task` | Run one ad-hoc module on a host |
| `ansible_gather_facts` | System info (OS, IP, memory) |
| `ansible_diagnose_host` | Deep connectivity and config diagnostics |
| `ansible_playbook` | Run a full playbook |
| `ansible_service_manager` | Manage systemd services |
| `list_projects`, `project_playbooks` | Registered projects and their playbooks |
| `validate_playbook`, `create_playbook` | Syntax-check a playbook; create a new one (ask first) |

Vault (`vault_view`, `vault_decrypt`, `vault_encrypt`), galaxy and project-management tools exist. Ask the user before using them.
