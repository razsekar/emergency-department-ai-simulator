"""Composition root: the single FastAPI application that wires all modules together."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.platform import health
from app.platform.config import get_settings
from app.platform.errors import install_error_handlers


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    app = FastAPI(
        title=settings.app_name,
        description="Educational operational simulation. Synthetic data only.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    install_error_handlers(app)
    app.include_router(health.router)
    _include_module_routers(app)
    return app


def _include_module_routers(app: FastAPI) -> None:
    """Auto-register `app.modules.<name>.api.router:router` for every module that defines one."""
    import importlib
    import pkgutil

    import app.modules as modules_pkg

    for mod in pkgutil.iter_modules(modules_pkg.__path__):
        try:
            router_mod = importlib.import_module(f"app.modules.{mod.name}.api.router")
        except ModuleNotFoundError as exc:
            if exc.name == f"app.modules.{mod.name}.api.router":
                continue
            raise
        app.include_router(router_mod.router)


app = create_app()
