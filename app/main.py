"""FastAPI application factory."""

from fastapi import FastAPI
from app.routes import routers


def create_app() -> FastAPI:
    """Create và configure FastAPI app."""
    app = FastAPI(
        title="YOLOv8 Detection API",
        description="API cho object detection sử dụng YOLOv8 và plate recognition",
        version="1.0.0"
    )
    
    # Include all routers
    for router in routers:
        app.include_router(router)
    
    # Health check endpoints
    @app.get("/")
    async def root():
        return {"msg": "Server OK"}
    
    @app.get("/health")
    async def health():
        return {"status": "ok"}
    
    return app


app = create_app()
