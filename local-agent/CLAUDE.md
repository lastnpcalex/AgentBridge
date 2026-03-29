# Local Agent

You are the local agent in an AgentBridge setup.

## Your capabilities
- Full access to the local filesystem
- Admin access to the AgentBridge server (publish, unpublish, clear feedback)
- Read feedback submitted by the non-local agent

## Setup
```bash
pip install -e .
export AGENTBRIDGE_URL=http://localhost:8000
export AGENTBRIDGE_ADMIN_KEY=<your-key>
```

## Workflow
1. Start the server: `cd ../server && uvicorn main:app --port 8000`
2. Publish files the non-local agent needs to review
3. Check feedback periodically
4. Act on feedback with your full local access
5. Unpublish files when done

## Rules
- Never publish files from private/, .env, .git/, or anything with secrets
- Only publish what's relevant to the current task
- Always check feedback before starting a new publish cycle
