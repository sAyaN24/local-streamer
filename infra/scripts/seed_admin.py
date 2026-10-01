"""One-shot setup step: creates the first admin account so there's an admin login to use
right after `docker compose up`, instead of nobody being able to reach /admin at all.

Runs as the compose 'seed-admin' service (see docker-compose.yml), stdlib-only so it can run
in a bare python:3.12-slim container with no dependency install step -- same approach as
seed_demo_room.py. Idempotent by default: the backend's /auth/setup-admin only ever creates
the first admin (409s once one exists), so re-running this on every `up` is safe and a no-op
after the first run -- UNLESS ADMIN_RESET=1 is set, in which case an existing admin's password
is reset to the (freshly generated, unless ADMIN_PASSWORD is pinned) one below instead of
leaving it untouched. ADMIN_RESET is deliberately not part of infra/.env's own defaults -- see
its own comment in docker-compose.yml for why: it's meant to be opted into only by an explicit,
manual `setup.sh` re-run, never by the unattended `docker compose up` every reboot triggers.

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
# .example, not .local: email-validator (used by the API's EmailStr fields) hard-rejects
# .local as an RFC 6762 mDNS special-use domain; .example is the one reserved-for-docs TLD
# it deliberately does not reject (see its SPECIAL_USE_DOMAIN_NAMES list).
EMAIL = os.environ.get("ADMIN_EMAIL", "admin@streammark.example")
NAME = os.environ.get("ADMIN_NAME", "Admin")
PASSWORD = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(12)
# Same secret the API itself signs session tokens with (see security.mint_session_token) --
# /auth/reset-admin-password accepts it in place of a session precisely because anyone who
# already has it could forge a valid admin session with it anyway. Read from this container's
# own environment (env_file: .env in docker-compose.yml), same as every other setting here.
SETUP_SECRET = os.environ.get("AUTH_JWT_SECRET", "")
RESET_REQUESTED = os.environ.get("ADMIN_RESET", "").strip().lower() in ("1", "true", "yes")


def request(method: str, path: str, body: dict, headers: dict | None = None) -> tuple[int, dict | None]:
    all_headers = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=json.dumps(body).encode(), headers=all_headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, (json.loads(raw) if raw else None)


def print_credentials(verb: str) -> None:
    print("=" * 60)
    print(f"Admin account {verb}. Save these credentials -- they are")
    print("only ever printed here, to this container's logs:")
    print(f"  email:    {EMAIL}")
    print(f"  password: {PASSWORD}")
    print("=" * 60)


def main() -> None:
    status, data = request("POST", "/auth/setup-admin", {"email": EMAIL, "password": PASSWORD, "name": NAME})
    if status == 201:
        print_credentials("created")
        return
    if status != 409:
        print(f"Admin setup failed: {status} {data}", file=sys.stderr)
        sys.exit(1)

    if not RESET_REQUESTED:
        print("An admin account already exists, nothing to do.")
        return

    print("An admin account already exists -- resetting its password (ADMIN_RESET=1)...")
    status, data = request(
        "POST",
        "/auth/reset-admin-password",
        {"email": EMAIL, "new_password": PASSWORD},
        headers={"X-Setup-Secret": SETUP_SECRET},
    )
    if status == 204:
        print_credentials("password reset")
    elif status == 404:
        print(f"No admin account found with email {EMAIL!r} -- it may have been created with a")
        print("different ADMIN_EMAIL, or manually via /admin. Not resetting anything.")
        sys.exit(1)
    else:
        print(f"Password reset failed: {status} {data}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
