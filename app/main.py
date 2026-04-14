"""FastAPI application factory."""

import os
import time
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.config import get_machine_access_keys, is_public_path
from app.services.machine_context import get_current_machine_id, reset_current_machine_id, set_current_machine_id
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

        machine_token = None
        try:
            if not is_public_path(request.url.path):
                machine_id = request.headers.get("x-machine-id", "").strip()
                machine_key = request.headers.get("x-machine-key", "").strip()
                machine_access_keys = get_machine_access_keys()

                if not machine_access_keys:
                    # Fallback mode: chưa cấu hình key thì scope theo IP client
                    # để mỗi máy chỉ đọc/ghi dữ liệu của chính IP đó.
                    machine_id = request.client.host if request.client else "default"
                    machine_token = set_current_machine_id(machine_id)
                    request.state.machine_id = machine_id
                    response = await call_next(request)
                    return response

                expected_key = machine_access_keys.get(machine_id)
                if not machine_id or not machine_key or expected_key != machine_key:
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Invalid machine credentials"},
                    )

                machine_token = set_current_machine_id(machine_id)
                request.state.machine_id = machine_id
            else:
                request.state.machine_id = get_current_machine_id()
        
            # Process request
            response = await call_next(request)
            process_time = time.time() - start_time
        
            # Log các API chính
            if request.url.path in ["/recognize-video", "/detect-plates", "/recognize-plate", "/detect"]:
                request_meta = {
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": dict(request.query_params),
                    "process_time": round(process_time, 3),
                    "status_code": response.status_code,
                    "user_agent": request.headers.get("user-agent", ""),
                    "ip": request.client.host if request.client else "",
                }
                history_service.add_entry(
                    {
                        "method": request.method,
                        "path": request.url.path,
                        "query_params": dict(request.query_params),
                        "process_time": round(process_time, 3),
                        "status_code": response.status_code,
                        "user_agent": request.headers.get("user-agent", ""),
                        "ip": request.client.host if request.client else "",
                        "summary": {
                            "method": request.method,
                            "path": request.url.path,
                            "status_code": response.status_code,
                            "process_time": round(process_time, 3),
                        },
                    },
                    full_result=request_meta,
                )

            return response
        finally:
            if machine_token is not None:
                reset_current_machine_id(machine_token)
    
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
