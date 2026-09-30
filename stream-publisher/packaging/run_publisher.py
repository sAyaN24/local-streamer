"""PyInstaller entry script for the standalone streammark-publish executable.
Kept separate from the installed console-script so PyInstaller has a plain
.py file to point at (see streammark_publisher.spec)."""

from streammark_publisher.ingest.autopublish import cli

if __name__ == "__main__":
    cli()
