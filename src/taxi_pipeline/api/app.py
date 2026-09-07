"""FastAPI application factory."""

from fastapi import FastAPI

from taxi_pipeline.api.routes import analytics, health, runs, sources


def create_app() -> FastAPI:
    app = FastAPI(
        title="NYC TLC Data Pipeline API",
        description="Read-only operational metadata and aggregated warehouse analytics.",
        version="0.1.0",
    )
    app.include_router(health.router)
    app.include_router(sources.router)
    app.include_router(runs.router)
    app.include_router(analytics.router)
    return app


app = create_app()
