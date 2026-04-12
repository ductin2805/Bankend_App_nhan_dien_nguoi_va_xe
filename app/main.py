"""FastAPI application factory."""

import os
import time
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from app.routes import routers
from app.services.history_service import history_service


def create_app() -> FastAPI:
    """Create và configure FastAPI app."""
    app = FastAPI(
        title="YOLOv8 Detection API",
        description="API cho object detection sử dụng YOLOv8 và plate recognition",
        version="1.0.0"
    )

    # Serve static files để xem lại ảnh lịch sử qua URL /runs/...
    os.makedirs("runs", exist_ok=True)
    app.mount("/runs", StaticFiles(directory="runs"), name="runs")
    
    # Middleware để log lịch sử
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log các API chính
        if request.url.path in ["/recognize-video", "/detect-plates", "/recognize-plate", "/detect"]:
            history_service.add_entry({
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "process_time": round(process_time, 3),
                "status_code": response.status_code,
                "user_agent": request.headers.get("user-agent", ""),
                "ip": request.client.host if request.client else ""
            })
        
        return response
    
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
