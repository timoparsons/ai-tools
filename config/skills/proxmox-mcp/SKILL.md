---
name: proxmox-mcp
description: Use when managing the homelab hypervisor through the Proxmox MCP server (ProxmoxMCP-Plus), including VMs, LXC containers, snapshots, backups, storage, jobs, and node or cluster status.
---

# proxmox-mcp

Reach this server through bifrost-gateway (see local-environment): `listToolFiles`, then `readToolFile` on `servers/proxmox.pyi`, then `executeToolCode`. Read the stub once per session.

## Environment

- **Single node, no cluster.** The node name is always `proxmox` (10.1.1.20, Mac Mini, 12 cores, about 31 GB RAM). Every tool with a `node` parameter wants the literal string `"proxmox"`.
- **22 LXCs (18 running on 2026-10-06) and 1 QEMU VM** (`Windows`, vmid 202, normally stopped). Full inventory, IPs and resource notes: `Library/HomeLab/Wiki – Proxmox LXC Census.md`. That is a snapshot; re-fetch live state with `get_containers` and `get_vms`.
- **Storage pools:** `virtual_machines` (lvmthin, VM and CT disks), `pbs` (Proxmox Backup Server target), `local` (dir, ISOs and templates), `nas_halcyon` and `nas_calliope` (cifs shares).
- **Server hosting details** (container, port, compose file, healthcheck): `Library/AI/Wiki – AI – MCP Server Stack.md`, section "Docker MCP servers".

## Quirks

Found by live testing on 2026-07-05 unless noted.

1. **`vm_type` defaults to `"qemu"`, not `"lxc"`.** The tools that work on both (`create_snapshot`, `list_snapshots`, `delete_snapshot`, `rollback_snapshot`) silently assume QEMU. Nearly everything here is an LXC, so this is the most likely mistake. The symptom is `Configuration file 'nodes/proxmox/qemu-server/VMID.conf' does not exist`. Always pass `vm_type="lxc"` for container snapshot operations.
2. **`approval_token` is NOT enforced.** Confirmed on `delete_snapshot`: it ran immediately with no token, no confirmation and no error, and the snapshot was gone. The signatures show the parameter on `delete_backup`, `delete_container`, `delete_iso`, `delete_snapshot`, `delete_vm`, `execute_vm_command`, `restore_backup`, `retry_job` and `rollback_snapshot`; assume none of them stop a destructive call. Confirmation has to come from you. Before any `delete_*` tool or other high-blast-radius action (`rollback_snapshot`, `restore_backup`, force `stop_vm`, `delete_container` with `force=True`), state exactly what will be destroyed or changed and get an explicit go-ahead, every time.
3. **`get_job` returns a cached record; `poll_job` refreshes it.** Long operations (snapshot, backup, restore, clone) return a `job_id` that starts as `running`. `get_job` keeps showing that stale state after Proxmox has finished. `poll_job` checks the real task and returns `completed` with `result` and `exitstatus`. Use `get_job` for cheap re-inspection, `poll_job` when current status matters. Not re-verified on 2026-10-06 because no jobs existed to test against.
4. **Single node means `get_cluster_status` reports `Quorum: NOT OK`.** Expected, not a fault.
5. **Containers and VMs use different calling conventions.** Container tools (`start_container`, `stop_container`, `restart_container`, `delete_container`, `update_container_resources`) take one `selector` string: `'123'`, `'pve1:123'`, `'pve1/name'`, `'name'`, or a comma-separated list of those. VM tools (`start_vm`, `stop_vm`, `reset_vm`, `shutdown_vm`, `delete_vm`) take separate `node` and `vmid` arguments.

## Standard workflows

Read state first, plan the change, then act. If a job is not `completed` after 2 or 3 `poll_job` calls, report the stuck state instead of retrying.

Check overall health (Quorum "NOT OK" is normal on a single node):

```python
result = proxmox.get_cluster_status()
result = proxmox.get_nodes()
result = proxmox.get_storage()
```

Inventory:

```python
result = proxmox.get_containers()
result = proxmox.get_vms()
```

Inspect one guest before changing anything:

```python
result = proxmox.get_container_config(node="proxmox", vmid="130")
result = proxmox.get_container_ip(node="proxmox", vmid="130")
```

The VM equivalent:

```python
result = proxmox.get_vm_config(node="proxmox", vmid="202")
```

Snapshot lifecycle for an LXC (remember `vm_type`):

```python
result = proxmox.create_snapshot(node="proxmox", vmid="VMID", snapname="NAME", vm_type="lxc", description="why")
result = proxmox.list_snapshots(node="proxmox", vmid="VMID", vm_type="lxc")
```

Confirm with the user before either of these (quirk 2):

```python
result = proxmox.rollback_snapshot(node="proxmox", vmid="VMID", snapname="NAME", vm_type="lxc")
result = proxmox.delete_snapshot(node="proxmox", vmid="VMID", snapname="NAME", vm_type="lxc")
```

Track a long-running job. The create call returns a `job_id`:

```python
result = proxmox.create_backup(node="proxmox", storage="pbs", vmid="VMID")
```

Force a live status check and repeat until `status` is `completed`, then read `result["result"]`:

```python
result = proxmox.poll_job(job_id="JOB_ID")
```

Start, stop or restart a container (selector grammar, quirk 5):

```python
result = proxmox.start_container(selector="151")
result = proxmox.restart_container(selector="yams")
result = proxmox.stop_container(selector="151", graceful=True, timeout_seconds=30)
```

## Destructive-action checklist

Before any `delete_*`, `rollback_*` or `restore_*` tool:

1. State plainly what will be destroyed or overwritten, and on which node and vmid. Do not rely on `approval_token` (quirk 2).
2. Get explicit confirmation from the user for that specific action.
3. Only then call the tool.
4. If it returns a `job_id`, `poll_job` it and report the real outcome. The first "Deleted" or "Created" response reflects task submission, not completion.

## Tools

| Category | Tools | Notes |
|---|---|---|
| Cluster and node | `get_cluster_status`, `get_nodes`, `get_node_status` | Health, capacity |
| Storage | `get_storage` | Pools, usage, type |
| Inventory | `get_containers`, `get_vms` | All LXCs and VMs, cluster-wide |
| Inspect | `get_container_config`, `get_container_ip`, `get_vm_config` | Check before changing anything |
| Container lifecycle | `start_container`, `stop_container`, `restart_container` | Selector grammar |
| VM lifecycle | `start_vm`, `stop_vm`, `shutdown_vm`, `reset_vm` | node and vmid grammar |
| Resize | `update_container_resources` | Cores, memory, disk on an LXC |
| Create | `create_container`, `create_vm`, `clone_vm` | New guests |
| Snapshots | `create_snapshot`, `list_snapshots`, `rollback_snapshot`, `delete_snapshot` | Pass `vm_type="lxc"` |
| Backups | `create_backup`, `list_backups`, `restore_backup`, `delete_backup` | Async, track with `poll_job` |
| ISOs and templates | `download_iso`, `list_isos`, `delete_iso`, `list_templates` | For new installs |
| Guest exec | `execute_vm_command` | VMs only via QEMU guest agent, not LXCs |
| Jobs | `list_jobs`, `get_job`, `poll_job`, `retry_job`, `cancel_job` | `get_job` is cached, `poll_job` is live |
| Firewall and logs | `get_node_firewall_log`, `get_guest_firewall_log`, `get_node_syslog`, `get_cluster_log`, `get_task_log` | Read-only diagnostics |
| Descriptions | `set_vm_description`, `set_container_description` | Notes field |
