import os

import uvicorn

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from app.api import create_app  # noqa: E402

app = create_app()


def main() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
