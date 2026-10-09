---
name: filesystem-mcp
description: Use when reading, searching, editing or writing files on the Mac Studio through the filesystem MCP server (allowed roots under /Users/tim/Documents/Coding and the ai-tools SSD volume at /Volumes/SSD/ai-tools).
---

# filesystem-mcp

Reach this server through bifrost-gateway (see local-environment): `listToolFiles`, then `readToolFile` on `servers/filesystem.pyi`, then `executeToolCode`. Read the stub once per session.

## Environment

- Allowed directories as of 2026-10-09: `/Users/tim/Documents/Coding` and `/Volumes/SSD/ai-tools`. The SSD folder was renamed from `ai_tools` to `ai-tools` on 2026-10-09 and the Bifrost client updated to match. Config drifts, so call `list_allowed_directories()` when scope matters.
- Paths outside the allowed roots are refused cleanly with `Access denied - path outside allowed directories`. Just check the path.
- Top-level dirs under Coding on 2026-07-05 (snapshot): `Apple Notes`, `ai-tools`, `ansible-macos-deploy`, `backup`, `homeassistant-dev`, `macos-scripts`, `proxmox-calliope`, `proxmox-halcyon`, `proxmox-scripts`, `resolve-scripts`, `swiftbar`. The old internal `ai-tools` copy is being retired in favour of the SSD copy.
- Homelab-relevant: `proxmox-calliope/` (Ansible playbooks and per-LXC config snapshots in `ansible/`, `lxc-*/`, `vm-*/`, `proxmox-host/`).
- `/Volumes/SSD/ai-tools/` layout: `config/` and `mcp-servers/bifrost-admin/` are the git repo (whitelist `.gitignore`, so new folders stay untracked until added). `apps/` (ComfyUI, open-webui) and `models/` are large and untracked. Other folders in `mcp-servers/` are untracked.
- `config/skills/` holds the skill source folders, one `SKILL.md` each.
- The SSD must be mounted. If it isn't, this server and bifrost_admin both fail.

## Quirks

1. **`search_files` works, with glob semantics (re-tested 2026-10-06).** The pattern is a glob matched against the path relative to `path`, and it does not recurse on its own. Use `**/name` or `**/*.ext` to search subfolders. A bare substring such as `docker` matches nothing. The 2026-07-05 finding that it always returned "No matches found" no longer reproduces; the glob behaviour is the likely cause. Verify with a known file before trusting a "no matches" result.
2. **`edit_file` with `dryRun=True` is reliable** (verified 2026-07-05: correct diff, zero changes). Always dry-run first, show the diff for anything non-trivial, then apply.
3. **Prefer `read_text_file`.** `read_file` is a legacy alias; `read_text_file` supports `head` and `tail`.
4. **`write_file` overwrites completely.** No append, no merge, no dry-run, no undo. For an existing file, read it first, build the full new content, and confirm with the user before overwriting anything that is not scratch or output.
5. **Text only.** The read and write tools cannot handle binaries such as `.skill` zips. Edit the source folders as text; packaging happens elsewhere.

## Calling convention

```python
result = filesystem.list_directory(path="/Users/tim/Documents/Coding/proxmox-calliope")
print(result)
```

## Standard workflows

Get oriented: confirm scope, then take one tree and read what you spot in it.

```python
result = filesystem.list_allowed_directories()
tree = filesystem.directory_tree(path="/Users/tim/Documents/Coding/proxmox-calliope", excludePatterns=[".git", "node_modules"])
```

Find a file anywhere under a folder:

```python
result = filesystem.search_files(path="/Volumes/SSD/ai-tools", pattern="**/*.skill", excludePatterns=[".git"])
```

Read several files at once instead of looping:

```python
result = filesystem.read_multiple_files(paths=[
    "/Users/tim/Documents/Coding/proxmox-calliope/ansible/inventory/hosts.yml",
    "/Users/tim/Documents/Coding/proxmox-calliope/ansible/group_vars/all.yml",
])
```

Safe edit: dry-run first and show the diff.

```python
result = filesystem.edit_file(
    path="/Users/tim/Documents/Coding/proxmox-calliope/ansible/inventory/hosts.yml",
    edits=[{"oldText": "EXACT_EXISTING_TEXT", "newText": "REPLACEMENT"}],
    dryRun=True,
)
```

After the user confirms, repeat the same call with `dryRun=False`.

Overwrite or create a file (no undo): read it first if it exists, build the complete new content, confirm, then write.

```python
existing = filesystem.read_text_file(path="/path/to/file")
result = filesystem.write_file(path="/path/to/file", content="COMPLETE_NEW_CONTENT")
```

Move or rename:

```python
result = filesystem.move_file(source="/path/old.yml", destination="/path/new.yml")
```

## Tools

| Tool | When to use |
|---|---|
| `list_allowed_directories` | Confirm current scope |
| `directory_tree` | Recursive JSON tree; filter it yourself or use `search_files` with `**/` |
| `search_files` | Glob search relative to `path`; use `**/` to recurse (quirk 1) |
| `list_directory`, `list_directory_with_sizes` | Flat listing of one directory |
| `get_file_info` | Size, timestamps, permissions for one path |
| `read_text_file` | Preferred read, supports `head` and `tail` |
| `read_file` | Legacy alias of `read_text_file` |
| `read_multiple_files` | Batch read |
| `read_media_file` | Read an image or audio file |
| `edit_file` | Find-and-replace edit; `dryRun=True` first |
| `write_file` | Full overwrite or create; no undo |
| `create_directory` | Create a directory (idempotent) |
| `move_file` | Move or rename |
