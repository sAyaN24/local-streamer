# streammark-webserver

FastAPI room/auth/token service for StreamMark: user accounts, room lifecycle
(create/go-live/end), and minting LiveKit viewer/broadcaster tokens, backed by
MongoDB. Also ships two DB-backed CLI tools:

- `streammark-logger-bot` — joins a room as a hidden, data-only participant
  and persists every annotation event to MongoDB.
- `streammark-mint-token` — prints a raw publisher JWT for a room (debug use).

Normally run via Docker through [`infra/`](../infra); see the root
[README](../README.md) for the full stack. To run natively:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ../shared -e ".[dev]"
streammark-api
```

Requires `infra/.env` (copy from `infra/.env.example`) to be readable from the
current working directory, or the equivalent environment variables set
directly — see `streammark_shared.config.Settings`.
