"""API routes cho detection endpoint."""

from fastapi import APIRouter, UploadFile, Query
from app.services.detection_service import DetectionService
from app.utils.image_utils import load_image_from_bytes

router = APIRouter(tags=["detection"])

# Khởi tạo detection service
detection_service = DetectionService()

# Lazy load plate service (chỉ import khi cần)
_plate_service = None


def get_plate_service():
    """Lazy load plate service."""
    global _plate_service
    if _plate_service is None:
        from app.services.plate_service import PlateRecognitionService
        _plate_service = PlateRecognitionService(lang='vi')
        detection_service.set_plate_service(_plate_service)
    return _plate_service


@router.post("/detect")
async def detect(file: UploadFile, recognize_plates: bool = Query(False)):
    """
    Detect objects trong uploaded image.
    
    Args:
        file: Uploaded image file
        recognize_plates: Có nhận dạng biển số hay không (default: False)
        
    Returns:
        JSON với detections và annotated image (base64)
    """
    try:
        # Read file contents
        contents = await file.read()
        
        # Load image from bytes
        img = load_image_from_bytes(contents)
        
        print("IMG OK:", img is not None)
        
        if img is None:
            return {"error": "Decode ảnh lỗi"}
        
        # Load plate service nếu cần
        if recognize_plates:
            get_plate_service()
        
        # Perform detection
        result = detection_service.detect_objects(img, recognize_plates=recognize_plates)
        
        print("RESULT:", result.get("detections"))
        
        return result
        
    except Exception as e:
        print(f"🔥 ERROR: {e}")
        return {"error": str(e)}
