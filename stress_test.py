"""Stress test for AgentBridge server — tries every way to leak or break things."""

import requests
import json

SERVER = "http://localhost:8000"
ADMIN_KEY = "test-secret-key-123"
WRONG_KEYS = ["", "wrong", "test-secret-key-124", "test-secret-key-123 ", "TEST-SECRET-KEY-123"]

passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name} — {detail}")

def admin_headers(key=ADMIN_KEY):
    return {"X-Admin-Key": key, "Content-Type": "application/json"}

def reader_headers():
    return {"Content-Type": "application/json"}


# Clean slate — unpublish everything from prior runs
for f in requests.get(f"{SERVER}/files").json().get("files", []):
    requests.post(f"{SERVER}/admin/unpublish", json={"path": f}, headers=admin_headers())
requests.post(f"{SERVER}/admin/clear-feedback", headers=admin_headers())

# ============================================================
print("\n=== 1. AUTH ENFORCEMENT ===")
# ============================================================

# Every admin endpoint with no key / wrong keys
admin_endpoints = [
    ("POST", "/admin/publish", {"path": "hack.txt", "content": "pwned"}),
    ("POST", "/admin/unpublish", {"path": "hack.txt"}),
    ("POST", "/admin/clear-feedback", None),
]

for method, path, body in admin_endpoints:
    for key_label, key in [("no key", ""), *[(f"wrong key '{k}'", k) for k in WRONG_KEYS]]:
        headers = {"Content-Type": "application/json"}
        if key:
            headers["X-Admin-Key"] = key
        if method == "POST":
            r = requests.post(f"{SERVER}{path}", json=body, headers=headers)
        else:
            r = requests.get(f"{SERVER}{path}", headers=headers)
        test(f"{path} with {key_label}", r.status_code == 403, f"got {r.status_code}: {r.text[:100]}")


# ============================================================
print("\n=== 2. PUBLISH/READ ISOLATION ===")
# ============================================================

# Publish 2 files with valid key
r = requests.post(f"{SERVER}/admin/publish", json={"path": "public/app.py", "content": "print('hello')"}, headers=admin_headers())
test("Publish public/app.py", r.status_code == 200)

r = requests.post(f"{SERVER}/admin/publish", json={"path": "src/utils.py", "content": "def add(a,b): return a+b"}, headers=admin_headers())
test("Publish src/utils.py", r.status_code == 200)

# Reader can list and read published files
r = requests.get(f"{SERVER}/files")
files = r.json()["files"]
test("Reader sees exactly 2 files", len(files) == 2, f"got {files}")

r = requests.get(f"{SERVER}/files/public/app.py")
test("Reader can read published file", r.status_code == 200 and "print('hello')" in r.json()["content"])

# Reader CANNOT read unpublished paths
unpublished_paths = [
    ".env", ".git/config", "private/secrets.json", "C:/Windows/System32/config/SAM",
    "../../../etc/passwd", "..\\..\\..\\Windows\\System32\\config\\SAM",
    "%2e%2e/%2e%2e/etc/passwd", "....//....//etc/passwd",
    "private/secrets.json\x00.txt",  # null byte injection
    "public/app.py/../../../etc/passwd",  # traversal after valid prefix
]
for p in unpublished_paths:
    r = requests.get(f"{SERVER}/files/{p}")
    test(f"Reader denied: {repr(p)[:50]}", r.status_code == 404, f"got {r.status_code}: {r.text[:80]}")


# ============================================================
print("\n=== 3. PATH TRAVERSAL & INJECTION ===")
# ============================================================

# Try publishing with traversal paths (should succeed as admin, but only as key-value)
# Paths that escape root should be rejected
escape_paths = ["../../etc/passwd", "..\\..\\Windows\\System32"]
for p in escape_paths:
    r = requests.post(f"{SERVER}/admin/publish", json={"path": p, "content": "evil"}, headers=admin_headers())
    test(f"Admin rejects escaping path '{p}'", r.status_code == 422)

# Paths with .. that resolve within root should normalize
r = requests.post(f"{SERVER}/admin/publish", json={"path": "public/../private/secrets.json", "content": "evil"}, headers=admin_headers())
test("Admin normalizes 'public/../private/secrets.json'", r.status_code == 200)
r2 = requests.get(f"{SERVER}/files/private/secrets.json")
test("Normalized path readable as 'private/secrets.json'", r2.status_code == 200 and r2.json()["content"] == "evil")
requests.post(f"{SERVER}/admin/unpublish", json={"path": "private/secrets.json"}, headers=admin_headers())

# Verify traversal paths don't expose actual filesystem
r = requests.get(f"{SERVER}/files/../../etc/passwd")
test("Traversal doesn't reach filesystem", r.status_code == 404)


# ============================================================
print("\n=== 4. FEEDBACK CHANNEL ===")
# ============================================================

# Non-local can submit feedback on published files
r = requests.post(f"{SERVER}/feedback", json={"path": "public/app.py", "comments": "looks good"}, headers=reader_headers())
test("Submit feedback on published file", r.status_code == 200)

# Non-local can read feedback
r = requests.get(f"{SERVER}/feedback")
test("Reader can read feedback", r.status_code == 200 and len(r.json()["feedback"]) > 0)

# Non-local CANNOT submit feedback on unpublished files
r = requests.post(f"{SERVER}/feedback", json={"path": "nonexistent/file.py", "comments": "hi"}, headers=reader_headers())
test("Cannot submit feedback on unpublished file", r.status_code == 404)

# Non-local CANNOT clear feedback
r = requests.post(f"{SERVER}/admin/clear-feedback", headers=reader_headers())
test("Reader cannot clear feedback (no key)", r.status_code == 403)


# ============================================================
print("\n=== 5. OPENAPI / DISCOVERY ===")
# ============================================================

r = requests.get(f"{SERVER}/openapi.json")
schema = r.json()
paths = list(schema.get("paths", {}).keys())
test("OpenAPI hides /admin/publish", "/admin/publish" not in paths, f"exposed: {paths}")
test("OpenAPI hides /admin/unpublish", "/admin/unpublish" not in paths, f"exposed: {paths}")
test("OpenAPI hides /admin/clear-feedback", "/admin/clear-feedback" not in paths, f"exposed: {paths}")
test("OpenAPI shows /files", "/files" in paths)
test("OpenAPI shows /feedback", "/feedback" in paths)


# ============================================================
print("\n=== 6. EDGE CASES ===")
# ============================================================

# Empty path
r = requests.post(f"{SERVER}/admin/publish", json={"path": "", "content": "x"}, headers=admin_headers())
test("Reject empty path", r.status_code == 422)

r = requests.post(f"{SERVER}/admin/publish", json={"path": "   ", "content": "x"}, headers=admin_headers())
test("Reject whitespace-only path", r.status_code == 422)

# Very large content
big = "x" * (10 * 1024 * 1024)  # 10MB
r = requests.post(f"{SERVER}/admin/publish", json={"path": "big.txt", "content": big}, headers=admin_headers())
test("Handles large file publish", r.status_code == 200)
requests.post(f"{SERVER}/admin/unpublish", json={"path": "big.txt"}, headers=admin_headers())

# Duplicate publish overwrites
requests.post(f"{SERVER}/admin/publish", json={"path": "dup.txt", "content": "v1"}, headers=admin_headers())
requests.post(f"{SERVER}/admin/publish", json={"path": "dup.txt", "content": "v2"}, headers=admin_headers())
r = requests.get(f"{SERVER}/files/dup.txt")
test("Duplicate publish overwrites (latest wins)", r.json()["content"] == "v2")
requests.post(f"{SERVER}/admin/unpublish", json={"path": "dup.txt"}, headers=admin_headers())

# Unpublish nonexistent
r = requests.post(f"{SERVER}/admin/unpublish", json={"path": "nope.txt"}, headers=admin_headers())
test("Unpublish nonexistent returns 404", r.status_code == 404)

# Read after unpublish
requests.post(f"{SERVER}/admin/publish", json={"path": "temp.txt", "content": "hi"}, headers=admin_headers())
requests.post(f"{SERVER}/admin/unpublish", json={"path": "temp.txt"}, headers=admin_headers())
r = requests.get(f"{SERVER}/files/temp.txt")
test("File gone after unpublish", r.status_code == 404)


# ============================================================
print("\n=== 7. HTTP METHOD CONFUSION ===")
# ============================================================

# Try GET on POST-only endpoints
r = requests.get(f"{SERVER}/admin/publish")
test("GET /admin/publish rejected", r.status_code in [403, 405])

r = requests.get(f"{SERVER}/admin/unpublish")
test("GET /admin/unpublish rejected", r.status_code in [403, 405])

# Try POST on GET-only endpoints
r = requests.post(f"{SERVER}/files", json={})
test("POST /files rejected", r.status_code == 405)

# Try DELETE (not defined)
r = requests.delete(f"{SERVER}/files/public/app.py")
test("DELETE /files rejected", r.status_code == 405)

r = requests.delete(f"{SERVER}/admin/publish")
test("DELETE /admin/publish rejected", r.status_code in [403, 405])


# ============================================================
print(f"\n{'='*50}")
print(f"  RESULTS: {passed} passed, {failed} failed")
print(f"{'='*50}\n")
