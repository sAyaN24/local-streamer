"""One-shot setup step: creates the first admin account so there's an admin login to use
right after `docker compose up`, instead of nobody being able to reach /admin at all.

Runs as the compose 'seed-admin' service (see docker-compose.yml), stdlib-only so it can run
in a bare python:3.12-slim container with no dependency install step -- same approach as
seed_demo_room.py. Idempotent: the backend's /auth/setup-admin only ever creates the first
admin (409s once one exists), so re-running this on every `up` is safe and a no-op after the
first run.

ADMIN_EMAIL / ADMIN_NAME / ADMIN_PASSWORD can be set in infra/.env to pick the credentials
yourself; otherwise a random password is generated here. Either way, the email and password
are printed to this container's logs (`docker compose logs seed-admin`) since this is the
only place they're ever shown in full -- the backend only ever stores a bcrypt hash.
"""

import json
import os
import secrets
import sys
import urllib.error
import urllib.request

BASE_URL = f"http://localhost:{os.environ.get('API_PORT', '8000')}"
EMAIL = os.environ.get("ADMIN_EMAIL", "admin@streammark.local")
NAME = os.environ.get("ADMIN_NAME", "Admin")
PASSWORD = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(12)


def post(path: str, body: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def main() -> None:
    status, data = post(
        "/auth/setup-admin", {"email": EMAIL, "password": PASSWORD, "name": NAME}
    )
    if status == 201:
        print("=" * 60)
        print("Admin account created. Save these credentials -- they are")
        print("only ever printed here, to this container's logs:")
        print(f"  email:    {EMAIL}")
        print(f"  password: {PASSWORD}")
        print("=" * 60)
    elif status == 409:
        print("An admin account already exists, nothing to do.")
    else:
        print(f"Admin setup failed: {status} {data}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
