# ai-tools

Personal AI tooling on the Mac Studio SSD (`/Volumes/SSD/ai-tools`). This repo tracks only the original work. Large and third-party material lives alongside it, untracked.

## Layout

- `config/`: client configs (Claude, Gemini, LM Studio), `omlx`, and `skills/`
- `mcp-servers/bifrost-admin/`: source for the Bifrost admin MCP server
- `apps/`: third-party apps such as ComfyUI and open-webui (untracked)
- `models/`: local model weights (untracked)
- `mcp-servers/` (everything except `bifrost-admin/`): other servers, untracked

## How tracking works

`.gitignore` is a whitelist. It ignores everything at the top level, then re-allows only the folders listed in it. A new folder stays untracked until you add it to `.gitignore` on purpose.

## Setup notes

- `bifrost-admin/.venv` is not tracked. Recreate it on each machine from `requirements.txt`.
- Bifrost reads `BIFROST_ADMIN_USER` and `BIFROST_ADMIN_PASSWORD` from its environment. Don't commit credentials.
- The SSD must be mounted for the filesystem and Bifrost admin servers to work.
