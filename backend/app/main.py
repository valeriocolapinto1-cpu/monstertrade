from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.broker import router as broker_router
from app.api.orders import router as orders_router
from app.api.routes import router
from app.api.security import api_key_middleware
from app.api.trading import router as trading_router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    production = settings.environment == "production"
    # In produzione niente documentazione interattiva pubblica.
    app = FastAPI(
        title="MonsterTrade API",
        version="0.1.0",
        docs_url=None if production else "/docs",
        redoc_url=None,
        openapi_url=None if production else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.middleware("http")(api_key_middleware)
    app.include_router(router)
    app.include_router(trading_router)
    app.include_router(broker_router)
    app.include_router(orders_router)
    return app


app = create_app()
