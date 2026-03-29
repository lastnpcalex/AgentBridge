import os
import posixpath
import secrets
from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, field_validator
from datetime import datetime, timezone

# Admin key: set via env var or auto-generate on startup
ADMIN_KEY = os.environ.get("AGENTBRIDGE_ADMIN_KEY", secrets.token_hex(32))

app = FastAPI(title="AgentBridge Server")

# In-memory store
published_files: dict[str, dict] = {}
feedback_store: list[dict] = []


class PublishRequest(BaseModel):
    path: str
    content: str

    @field_validator("path")
    @classmethod
    def clean_path(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("path must not be empty")
        # Normalize to forward slashes, collapse .., strip leading slashes
        v = posixpath.normpath(v.replace("\\", "/")).lstrip("/")
        if v.startswith(".."):
            raise ValueError("path must not escape root")
        return v


class UnpublishRequest(BaseModel):
    path: str


class FeedbackRequest(BaseModel):
    path: str
    comments: str


def verify_admin_key(x_admin_key: str = Header(default="")):
    if not x_admin_key or not secrets.compare_digest(x_admin_key, ADMIN_KEY):
        raise HTTPException(403, "Forbidden")


# --- Admin endpoints (local agent only, key-protected) ---

@app.post("/admin/publish", dependencies=[Depends(verify_admin_key)])
def publish_file(req: PublishRequest):
    published_files[req.path] = {
        "content": req.content,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"status": "published", "path": req.path}


@app.post("/admin/unpublish", dependencies=[Depends(verify_admin_key)])
def unpublish_file(req: UnpublishRequest):
    if req.path not in published_files:
        raise HTTPException(404, "File not published")
    del published_files[req.path]
    return {"status": "unpublished", "path": req.path}


@app.post("/admin/clear-feedback", dependencies=[Depends(verify_admin_key)])
def clear_feedback():
    feedback_store.clear()
    return {"status": "cleared"}


# --- Reader endpoints (non-local agent, no auth needed) ---

@app.get("/files")
def list_files():
    return {"files": list(published_files.keys())}


@app.get("/files/{path:path}")
def read_file(path: str):
    if path not in published_files:
        raise HTTPException(404, "File not available")
    return {"path": path, "content": published_files[path]["content"]}


@app.get("/feedback")
def get_feedback():
    return {"feedback": feedback_store}


@app.post("/feedback")
def submit_feedback(req: FeedbackRequest):
    if req.path not in published_files:
        raise HTTPException(404, "File not available")
    feedback_store.append({
        "path": req.path,
        "comments": req.comments,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"status": "received"}


# --- Strip admin routes from public OpenAPI schema ---

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version="1.0.0",
        routes=app.routes,
    )
    public_paths = {p: v for p, v in schema.get("paths", {}).items() if not p.startswith("/admin")}
    schema["paths"] = public_paths
    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi


@app.on_event("startup")
def print_admin_key():
    print(f"\n  ADMIN KEY: {ADMIN_KEY}\n")
    print("  Pass this as X-Admin-Key header for /admin/* endpoints.\n")
