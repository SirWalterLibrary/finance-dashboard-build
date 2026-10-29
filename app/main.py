from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .db import init_db
from .routers import accounts as accounts_router
from .routers import auth as auth_router
from .routers import categories as categories_router
from .routers import imports as imports_router
from .routers import transactions as transactions_router


def create_app() -> FastAPI:
    init_db()
    app = FastAPI(title="Finance Dashboard")
    app.include_router(auth_router.router)
    app.include_router(accounts_router.router)
    app.include_router(categories_router.router)
    app.include_router(imports_router.router)
    app.include_router(transactions_router.router)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():  # mount LAST so /api routes win
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    return app


app = create_app()
