"""Thin CLI wrapper around streammark_publisher.ingest.device_detect, kept for
start_capture.sh (which invokes this file directly by path). See that module
for the actual detection logic."""

from streammark_publisher.ingest.device_detect import main

if __name__ == "__main__":
    main()
