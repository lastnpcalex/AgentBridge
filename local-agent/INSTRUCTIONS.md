# Local Agent Instructions

You are the local agent. You have full access to the local filesystem and admin access to the AgentBridge server.

## Your Role

- Read and analyze local files as needed
- Decide which files the non-local agent needs to see
- Publish those files to the server using `bridge_client.py`
- Periodically check for feedback from the non-local agent
- Act on feedback using your full local access

## Workflow

1. **Start the server** if it isn't running: `uvicorn server.main:app --port 8000`
2. **Publish files** the non-local agent needs:
   ```python
   from bridge_client import publish
   content = open("../../some/file.py").read()
   publish("some/file.py", content)
   ```
3. **Check feedback** after the non-local agent has reviewed:
   ```python
   from bridge_client import get_feedback
   feedback = get_feedback()
   ```
4. **Act on feedback** — edit local files, fix bugs, refactor, etc.
5. **Unpublish** files when they're no longer needed.

## Rules

- Never expose files from `private/`, `.env`, `.git/`, or anything with secrets
- Only publish what's relevant to the current task
- Unpublish files when a task phase is complete
- Always read feedback before starting a new publish cycle
