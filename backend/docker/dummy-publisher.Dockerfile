# Dev-only image for scripts/dummy_publisher.py -- see docker-compose.yml's 'dummy-publisher'
# service (opt-in via the 'demo' profile). Loops a local video file into a LiveKit room as a
# visible publisher, exercising the viewer/annotation/pupil-tracking flow without needing
# capture-card hardware attached.
FROM python:3.12-slim

WORKDIR /app

# opencv-python's wheel imports these X11/GL shared libs at runtime even for headless,
# non-GUI use -- python:3.12-slim doesn't ship them by default (unlike api.Dockerfile's
# base, this image actually exercises cv2's decode path, so it needs them).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libxcb1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

COPY scripts/dummy_publisher.py ./scripts/dummy_publisher.py

ENTRYPOINT ["python", "scripts/dummy_publisher.py"]
CMD ["--room", "demo-room", "--video", "/video/sample.mp4"]
