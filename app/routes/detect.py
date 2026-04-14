"""API routes cho detection endpoint."""

import os
import time
import base64
import uuid
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

        # Log summary cho lịch sử với ảnh đại diện
        from app.services.history_service import history_service
        representative_image_path = ""
        history_result = {
            "detections": result.get("detections", []),
            "plates": result.get("plates", [])
        }

        image_b64 = result.get("image", "")
        if image_b64:
            history_results_dir = os.path.join("runs", "history_frames")
            os.makedirs(history_results_dir, exist_ok=True)
            file_name = f"{int(time.time() * 1000)}_{uuid.uuid4().hex}.jpg"
            file_path = os.path.join(history_results_dir, file_name)
            try:
                with open(file_path, "wb") as f:
                    f.write(base64.b64decode(image_b64))
                representative_image_path = file_path.replace("\\", "/")
                history_result["image_path"] = representative_image_path
            except Exception:
                history_result["image_path"] = ""

        history_service.add_entry({
            "type": "object_detection",
            "method": "POST",
            "path": "/detect",
            "summary": {
                "detections": len(result.get("detections", [])),
                "plates_detected": len(result.get("plates", [])),
                "recognize_plates": recognize_plates
            },
            "representative_image_path": representative_image_path
        }, full_result=history_result)
        
        print("RESULT:", result.get("detections"))
        
        return result
        
    except Exception as e:
        print(f"🔥 ERROR: {e}")
        return {"error": str(e)}
