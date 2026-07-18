"""Manual debug CLI: prints a publisher JWT for a room.

Deliberately not exposed over HTTP -- see common/tokens.py module docstring for
why publish-capable tokens must never be handed out to arbitrary LAN callers.
Intended for an operator with direct filesystem/env access to the host running
the ingest service, e.g. to manually test `room.connect()` from a REPL.
"""

import argparse

from streammark.common.config import get_settings
from streammark.common.tokens import mint_publisher_token


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="streammark-mint-token",
        description=__doc__,
    )
    parser.add_argument("--room", required=True, help="Room name to mint a publisher token for")
    parser.add_argument("--identity", default="ingest", help="Publisher participant identity")
    return parser


def cli(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    settings = get_settings()
    token = mint_publisher_token(settings, args.room, args.identity)
    print(token)


if __name__ == "__main__":
    cli()
