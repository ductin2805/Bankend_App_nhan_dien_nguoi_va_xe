"""API routes cho plate recognition endpoint."""

from fastapi import APIRouter, UploadFile
from app.utils.image_utils import load_image_from_bytes

router = APIRouter(tags=["plate"])

# Lazy load plate service
_plate_service = None


def get_plate_service():
    """Lazy load plate service."""
    global _plate_service
    if _plate_service is None:
        from app.services.plate_service import PlateRecognitionService
        _plate_service = PlateRecognitionService(lang='vi')
    return _plate_service


@router.post("/recognize-plate")
async def recognize_plate(file: UploadFile):
    """
    Nhận dạng text từ ảnh biển số.
    
    Args:
        file: Uploaded image file (ảnh biển số)
        
    Returns:
        JSON với text nhận dạng được và confidence
    """
    try:
        # Load plate service
        plate_service = get_plate_service()
        
        # Read file
        contents = await file.read()
        
        # Load image
        img = load_image_from_bytes(contents)
        
        print("IMG OK:", img is not None)
        
        if img is None:
            return {"error": "Decode ảnh lỗi"}
        
        # Recognize plate
        result = plate_service.recognize_plate(img)
        
        print("PLATE RESULT:", result)
        
        return result
        
    except Exception as e:
        print(f"🔥 ERROR trong /recognize-plate: {e}")
        return {"error": str(e)}
