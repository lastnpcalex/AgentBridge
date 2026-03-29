# AgentBridge

A lightweight server that lets a local AI agent share specific files with a non-local AI agent, without exposing the full filesystem.

## Architecture

```
Local Agent          Server              Non-Local Agent
(full FS access)     (stores copies)     (server-only access)
     │                   │                      │
     ├─ publish ────────►│                      │
     ├─ unpublish ──────►│                      │
     │                   │◄──── list_files ─────┤
     │                   │◄──── read_file ──────┤
     │                   │◄──── get/post feedback ┤
     ├─ get_feedback ───►│                      │
     ├─ clear_feedback ─►│                      │
```

## Repos

| Component | Repo | Who runs it |
|-----------|------|-------------|
| Server | `server/` (this repo) | You, on a machine both agents can reach |
| Local Agent | `local-agent/` (this repo) | You, on your local machine |
| Non-Local Agent | [agentbridge-reader](https://github.com/lastnpcalex/agentbridge-reader) | The non-local Claude, anywhere |

The non-local agent gets its own repo so it never sees admin code, server internals, or local agent logic.

## Quick Start

### 1. Start the server

```bash
cd server
pip install -r requirements.txt
export AGENTBRIDGE_ADMIN_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
echo "Save this key: $AGENTBRIDGE_ADMIN_KEY"
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 2. Run the local agent

```bash
cd local-agent
pip install -r requirements.txt
export AGENTBRIDGE_URL=http://localhost:8000
export AGENTBRIDGE_ADMIN_KEY=<key-from-step-1>
```

Then point your local Claude at `local-agent/` as its working directory.

### 3. Run the non-local agent

On a separate machine or sandbox:

```bash
git clone https://github.com/lastnpcalex/agentbridge-reader.git
cd agentbridge-reader
pip install -r requirements.txt
export AGENTBRIDGE_URL=http://<server-address>:8000
```

Then point the non-local Claude at `agentbridge-reader/` as its working directory. It only has read access + feedback.

## Security

- Admin endpoints (publish/unpublish/clear) require `X-Admin-Key` header
- Admin routes are hidden from OpenAPI `/docs`
- Path traversal is blocked (normalized + root-escape rejected)
- Server stores in-memory copies only — no filesystem passthrough
- Non-local agent repo contains zero admin code or server internals
- Feedback is a shared channel, readable by both agents
