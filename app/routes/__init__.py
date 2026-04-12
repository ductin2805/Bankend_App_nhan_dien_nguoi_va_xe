"""Routes package."""

from app.routes.detect import router as detect_router
from app.routes.plate import router as plate_router
from app.routes.detect_plates import router as detect_plates_router
from app.routes.realtime import router as realtime_router
from app.routes.history import router as history_router
from app.routes.face import router as face_router

# Combine all routers
routers = [detect_router, plate_router, detect_plates_router, realtime_router, history_router, face_router]

__all__ = ["routers"]
