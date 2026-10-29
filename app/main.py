from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .db import init_db


def create_app() -> FastAPI:
    init_db()
    app = FastAPI(title="Finance Dashboard")

    @app.get("/api/health")
    def health():
        return {"ok": True}

    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():  # mount LAST so /api routes win
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    return app


app = create_app()
