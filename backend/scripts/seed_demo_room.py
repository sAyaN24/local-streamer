"""One-shot dev seed: creates a demo host account and a live 'demo-room' so `docker compose
up` gives you something to look at immediately, instead of an empty dashboard.

Runs as the compose 'seed' service (see docker-compose.yml), stdlib-only so it can run in a
bare python:3.12-slim container with no dependency install step. Idempotent: falls back to
login on a 409 (account exists), and treats a 409 on room creation (room exists) as success.
"""

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = f"http://localhost:{os.environ.get('API_PORT', '8000')}"
EMAIL = "demo@streammark.example"
PASSWORD = "demo12345"
NAME = "Demo Host"
ROOM_ID = "demo-room"
ROOM_TITLE = "Demo Room"


def post(path: str, body: dict, token: str | None = None) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def main() -> None:
    status, data = post("/auth/signup", {"email": EMAIL, "password": PASSWORD, "name": NAME})
    if status == 409:
        print("Demo account already exists, logging in instead...")
        status, data = post("/auth/login", {"email": EMAIL, "password": PASSWORD})
    if status not in (200, 201):
        print(f"Auth failed: {status} {data}", file=sys.stderr)
        sys.exit(1)
    token = data["token"]
    print(f"Authenticated as {EMAIL}")

    status, data = post("/rooms", {"id": ROOM_ID, "title": ROOM_TITLE, "go_live": True}, token=token)
    if status == 409:
        print(f"Room '{ROOM_ID}' already exists, nothing to do.")
    elif status == 201:
        print(f"Created and started room '{ROOM_ID}'.")
    else:
        print(f"Room creation failed: {status} {data}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
