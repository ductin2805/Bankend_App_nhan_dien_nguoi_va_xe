"""Services package."""

from app.services.detection_service import DetectionService
from app.services.plate_service import PlateRecognitionService

__all__ = ["DetectionService", "PlateRecognitionService"]
