---
name: obsidian-mcp
description: "Use when working with the user's Obsidian vault, including reading, creating, editing or searching notes, managing tasks, frontmatter, daily notes, links and backlinks, or vault conventions (area, project, wiki, log, research notes)."
---

# obsidian-mcp

One server, `obsidian`, reached through bifrost-gateway (see local-environment): `listToolFiles`, `readToolFile` on `servers/obsidian.pyi`, then `executeToolCode`. Read the stub once per session.

The server is the MCP endpoint built into the Obsidian **Local REST API** plugin (`http://127.0.0.1:27123/mcp/`, Bifrost client `obsidian`). It runs inside Obsidian, so Obsidian must be open on the Mac Studio. If the server is missing or unhealthy, check that first. Replaced the enhanced and semantic servers on 2026-10-06: there is no Dataview, Tasks-plugin, template, graph or fuzzy-edit tool any more. The patterns below cover those jobs.

## Tools

| Job | Tools |
|---|---|
| Read | `vault_read(path)` returns `content`, `frontmatter`, `tags`, `links`, `backlinks`, `stat`. With `targetType` + `target` it returns just that section as a string (or a frontmatter value). |
| Structure | `vault_get_document_map(path)` lists heading paths, block ids, frontmatter keys. Call before any targeted read or patch. |
| List | `vault_list(path)`; omit `path` for the vault root. |
| Search | `search_simple(query, contextLength)` fuzzy full text. `search_query(query)` JsonLogic over each note's `path`, `content`, `tags`, `frontmatter`, `stat`, `links`, `backlinks`, plus `glob` and `regexp` operators. |
| Edit | `vault_patch` (heading, block or frontmatter key; `append`, `prepend`, `replace`), `vault_append` (end of file), `vault_write` (create or **overwrite whole file**). |
| Files | `vault_move`, `vault_delete`. |
| App | `periodic_note_get_path(period)`, `active_file_get_path()`, `open_file(path)`, `tag_list()`, `command_list()`, `command_execute(commandId)`. |

## Gotchas (all observed 2026-10-06)

- **Heading targets are full paths from the H1**, joined with `::`. In `Wiki – AI – MCP Server Stack.md` the section is `Wiki – AI – MCP Server Stack::Maintenance`, not `Maintenance`. Copy them from `vault_get_document_map`.
- **Heading `append` breaks lists.** It inserts a blank line before the new content, so a task appended under a heading becomes a separate list. Use read, modify, replace instead (pattern below).
- **Heading `replace` drops the blank line after the heading** and before the next one unless you supply them. Send `"\n" + body.strip() + "\n\n"`.
- **Search covers everything**, including `Library/External Docs/` (cloned repos, with `node_modules`) and `Projects - Work/`. Exclude them in the query or filter the results.
- `vault_delete` returned no trash path. Treat it as permanent.
- `search_simple` returns `[{filename, score, matches:[{match, context}]}]`; `search_query` returns `[{filename, result}]`.
- `periodic_note_get_path("daily")` returns the path the note should have (`YYYY-MM-DD.md` at the vault root). The file may not exist yet; `vault_read` throws if it doesn't.

## Vault structure

```
Overview/        Area files (well-formed, excluded from housekeeping, do not restructure)
Projects/        Active projects (flat .md or folder per project)
Library/         Reference material, logs, research
Archive/         Completed work
Scratchpad/      Unorganised, never tidy
Obsidian/Templates/      Note templates
Library/External Docs/   Cloned git repos, READ ONLY, never modify
Projects - Work/ PDA-managed, out of scope, never touch (note: plain hyphen)
```

Full schema: `Projects/Obsidian/Architecture/Wiki – Obsidian Architecture.md`. Session context: `Projects/Obsidian/Architecture/Prompt – Obsidian Architecture Context.md`.

## Document types

| Prefix | Type | Tasks? | Notes |
|---|---|---|---|
| `Area –` | `area` | Yes | Lives in `Overview/` |
| `Project –` | `project` | Yes | Lives in `Projects/` |
| `Wiki –` | `wiki` | No | Reference only |
| `Research –` | `research` | Sometimes | `Projects/` or `Library/` |
| `Log –` | `log` | No | Most recent entry first |
| `Prompt –` | `meta` | No | |

Group label after the prefix: related notes in one Library folder share a second segment so they sort together, e.g. `Wiki – AI – MCP Server Stack`, `Wiki – AI – Local LLM Stack`, `Wiki – Maintenance – Lighting`.

Project folders: sub-documents carry `project: SLUG` frontmatter to link back to the parent. Task sections are headed `Tasks – <Name>`.

## Frontmatter

The Linter owns `date created`, `date modified` and key ordering. Never write these. Key order: `type`, `project`, `area`, `status`, `date created`, `date modified`. Note that `vault_patch` adds a new key at the end of the block, and the Linter reorders it later.

Project status values: `active | ongoing | complete | archive`.

Domain area slugs: `ai`, `diy-home`, `homelab`, `media`, `personal`, `meta`, `production`, `software`. AI notes (`area: ai`) live in `Library/AI/` and `Projects/AI/`; the area note is `Overview/Area – AI.md`.

## Rules of engagement

- **Read before editing.** Always. Never reconstruct from memory.
- **Confirm before applying** unless clearly mechanical (missing `status: active`, missing `---` between H2s). Always confirm before `vault_write` over an existing file, `vault_delete`, `vault_move` and `command_execute`.
- **Flag, don't fix** when inferring values from context (ambiguous `area:` or `project:` slug).
- **Checkboxes are for Tim's tasks only.** `- [ ]` marks something Tim needs to do himself, and it is what the area and overview queries pick up. Claude's own work lists (backlogs, steps to work through, things to check) are plain `-` bullets, struck through with `~~text~~` or deleted when done. If it is unclear whether an item is Tim's or Claude's, ask. Convention: Key Principles in `Wiki – Obsidian Architecture`.
- **Move and rename with `vault_move`** (tested 2026-10-06). The moved note keeps its ctime, mtime and frontmatter dates, and Obsidian updates links. Moving between folders with the same filename touches no other note, because wikilinks resolve by name. A rename rewrites the `[[links]]` in every note that points to it, which bumps those notes' mtime but not their frontmatter dates. It does not change the moved note's H1, so update that to the new name afterwards. Paths hard-coded in skills, prompts and other notes are not updated: search for the old path and fix them. Check the destination does not exist first; a destination ending in `/` keeps the filename. SSH is no longer needed for moves.
- **n8n workflows: never modify without explicit approval.** Read `Project – Obsidian Housekeeping Workflow.md` first.
- **No line starting with # inside a code fence** in anything you write. The housekeeping workflow has been turning those lines into `---` plus H2 headings and breaking the fence (observed 2026-10-06, cause inferred). Use trailing comments or prose.

## Patterns

Read a section:

```python
m = obsidian.vault_get_document_map(path=P)
sec = obsidian.vault_read(path=P, targetType="heading", target="Note Title::Section")
```

Edit text inside a section (replaces the old fuzzy edit). Check `OLD` is in `sec` before writing:

```python
sec = obsidian.vault_read(path=P, targetType="heading", target=T)
new = sec.replace(OLD, NEW)
result = obsidian.vault_patch(path=P, operation="replace", targetType="heading", target=T, content="\n" + new.strip() + "\n\n")
```

Add a task for Tim to a project (for Claude's own work items insert a plain `- TEXT` bullet instead and anchor on `startswith("- ")`). Task headings include a back-link, e.g. `Tasks – Project – n8n Workflow DEV [[Project – n8n Workflow DEV|↗️]]`, and sections end with `---`, so find the heading from the map and insert after the last task line:

```python
m = obsidian.vault_get_document_map(path=P)
T = [h for h in m["headings"] if "::Tasks –" in h][0]
sec = obsidian.vault_read(path=P, targetType="heading", target=T)
lines = sec.split("\n")
idx = [i for i, l in enumerate(lines) if l.strip().startswith("- [")]
at = idx[-1] + 1 if idx else 0
body = "\n".join(lines[:at] + ["- [ ] TEXT 📅 2026-10-10"] + lines[at:])
result = obsidian.vault_patch(path=P, operation="replace", targetType="heading", target=T, content="\n" + body.strip() + "\n\n")
```

Area notes keep tasks under `### Subsection` headings inside `## ✅ Area Tasks`; target the H3 (`Area – HomeLab::✅ Area Tasks::Proxmox`). Area and project notes also contain `dataview` and `tasks` code blocks: leave them alone.

Frontmatter (use `contentType="application/json"` for numbers, booleans and lists):

```python
result = obsidian.vault_patch(path=P, operation="replace", targetType="frontmatter", target="status", content="active")
result = obsidian.vault_patch(path=P, operation="replace", targetType="frontmatter", target="tags", content=["a", "b"], contentType="application/json", createTargetIfMissing=True)
```

Find notes (structured, replaces Dataview):

```python
skip = {"!": {"regexp": ["^(Library/External Docs|Projects - Work)/", {"var": "path"}]}}
active = obsidian.search_query(query={"and": [skip, {"==": [{"var": "frontmatter.type"}, "project"]}, {"==": [{"var": "frontmatter.status"}, "active"]}]})
in_area = obsidian.search_query(query={"and": [skip, {"==": [{"var": "frontmatter.area"}, "homelab"]}]})
in_folder = obsidian.search_query(query={"glob": ["Library/HomeLab/*", {"var": "path"}]})
recent = obsidian.search_query(query={"and": [skip, {">": [{"var": "stat.mtime"}, MS_EPOCH]}]})
```

The vault groups notes by `area:` and `project:` frontmatter and by folder, not by tags; `tag_list` is mostly noise from code snippets. Results include templates in `Obsidian/Templates/` that match too, so filter those out when counting. `stat.mtime` is milliseconds since epoch.

Open tasks (replaces the Tasks query): find files, then read and filter lines. This lists Tim's tasks only, because Claude's backlog items are plain bullets. Dates use Tasks emoji: 📅 due, ⏳ scheduled, 🛫 start, ✅ done.

```python
skip = {"!": {"regexp": ["^(Library/External Docs|Projects - Work|Archive|Obsidian)/", {"var": "path"}]}}
files = obsidian.search_query(query={"and": [skip, {"regexp": ["- \\[ \\] ", {"var": "content"}]}]})
def tasks(f):
    c = obsidian.vault_read(path=f["filename"])["content"]
    return [(f["filename"], l.strip()) for l in c.split("\n") if l.strip().startswith("- [ ] ")]
out = []
for f in files:
    out.extend(tasks(f))
result = out
```

Free-text search:

```python
hits = obsidian.search_simple(query="QUERY", contextLength=80)
result = [h for h in hits if not h["filename"].startswith("Library/External Docs/")]
```

Links and backlinks (one hop per read; repeat for more):

```python
n = obsidian.vault_read(path=P)
result = {"links": n["links"], "backlinks": n["backlinks"]}
```

New note from a template (check the target does not exist first):

```python
tpl = obsidian.vault_read(path="Obsidian/Templates/Template – Project.md")["content"]
exists = obsidian.search_query(query={"==": [{"var": "path"}, TARGET]})
```
Then fill the template text and `vault_write(path=TARGET, content=...)` only if `exists` is empty. Templater syntax in templates is not executed.

Daily note:

```python
p = obsidian.periodic_note_get_path(period="daily")["path"]
```
