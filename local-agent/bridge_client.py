"""Thin client for the local agent to manage the AgentBridge server."""

import os
import requests

SERVER = os.environ.get("AGENTBRIDGE_URL", "http://localhost:8000")
ADMIN_KEY = os.environ.get("AGENTBRIDGE_ADMIN_KEY", "")


def _admin_headers():
    return {"X-Admin-Key": ADMIN_KEY}


def publish(path: str, content: str):
    r = requests.post(f"{SERVER}/admin/publish", json={"path": path, "content": content}, headers=_admin_headers())
    r.raise_for_status()
    return r.json()


def unpublish(path: str):
    r = requests.post(f"{SERVER}/admin/unpublish", json={"path": path}, headers=_admin_headers())
    r.raise_for_status()
    return r.json()


def get_feedback():
    r = requests.get(f"{SERVER}/feedback")
    r.raise_for_status()
    return r.json()


def clear_feedback():
    r = requests.post(f"{SERVER}/admin/clear-feedback", headers=_admin_headers())
    r.raise_for_status()
    return r.json()


def list_published():
    r = requests.get(f"{SERVER}/files")
    r.raise_for_status()
    return r.json()
