import uvicorn

from streammark_shared.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "streammark_webserver.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        log_config=None,
    )


if __name__ == "__main__":
    main()
