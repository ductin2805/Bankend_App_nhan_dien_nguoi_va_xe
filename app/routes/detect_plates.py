"""API routes cho plate detection & recognition endpoint."""

import os
import time
import base64
import uuid
from fastapi import APIRouter, UploadFile
from app.services.detection_service import DetectionService
from app.utils.image_utils import load_image_from_bytes

router = APIRouter(tags=["plate-detection"])

# Khởi tạo detection service
detection_service = DetectionService()

# Lazy load plate service
_plate_service = None


def get_plate_service():
    """Lazy load plate service."""
    global _plate_service
    if _plate_service is None:
        from app.services.plate_service import PlateRecognitionService
        _plate_service = PlateRecognitionService(lang='vi')
    return _plate_service


@router.post("/detect-plates")
async def detect_plates(file: UploadFile):
    """
    Detect xe và nhận dạng tất cả biển số trong ảnh.
    
    Args:
        file: Uploaded image file (ảnh chứa xe)
        
    Returns:
        JSON với list xe detected + biển số của từng xe
        
    Response example:
    {
        "image": "base64...",
        "total_vehicles": 3,
        "vehicles": [
            {
                "class": 2,
                "class_name": "car",
                "confidence": 0.95,
                "bbox": [100, 200, 300, 400],
                "plate": {
                    "text": "29B01786",
                    "confidence": 0.98,
                    "detected": true
                }
            },
            ...
        ]
    }
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
        
        # YOLO detection
        from ultralytics import YOLO
        model = YOLO("yolov8n.pt")
        results = model(img)
        
        # Class names mapping
        class_names = {
            0: "person",
            1: "bicycle",
            2: "car",
            3: "motorcycle",
            4: "airplane",
            5: "bus",
            6: "train",
            7: "truck",
            8: "boat"
        }
        
        # Extract detections and recognize plates
        vehicles = []
        
        for r in results:
            if r.boxes is None:
                continue
            
            for box in r.boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                xyxy = box.xyxy[0].tolist()
                
                # Chỉ process xe (car, truck, bus, motorcycle, bicycle)
                vehicle_classes = [2, 3, 5, 7]  # car, motorcycle, bus, truck
                
                if class_id in vehicle_classes:
                    # Try to recognize plate
                    plate_result = plate_service.recognize_plate_from_coordinates(img, xyxy)
                    
                    plate_detected = bool(plate_result.get('text'))
                    
                    vehicles.append({
                        "class": class_id,
                        "class_name": class_names.get(class_id, "unknown"),
                        "confidence": round(confidence, 4),
                        "bbox": [round(v, 2) for v in xyxy],
                        "plate": {
                            "text": plate_result.get('text', ''),
                            "confidence": plate_result.get('confidence', 0.0),
                            "detected": plate_detected,
                            "error": plate_result.get('error')
                        }
                    })
        
        # Annotate image
        annotated = results[0].plot()
        
        # Encode to base64
        from app.utils.image_utils import encode_image_to_base64
        img_base64 = encode_image_to_base64(annotated)
        
        result = {
            "image": img_base64,
            "total_vehicles": len(vehicles),
            "vehicles": vehicles
        }
        
        # Log summary cho lịch sử
        from app.services.history_service import history_service
        plates_found = [v["plate"]["text"] for v in vehicles if v["plate"]["detected"]]

        representative_image_path = ""
        history_result = {
            "total_vehicles": len(vehicles),
            "vehicles": vehicles
        }

        if img_base64:
            history_results_dir = os.path.join("runs", "history_frames")
            os.makedirs(history_results_dir, exist_ok=True)
            file_name = f"{int(time.time() * 1000)}_{uuid.uuid4().hex}.jpg"
            file_path = os.path.join(history_results_dir, file_name)
            try:
                with open(file_path, "wb") as f:
                    f.write(base64.b64decode(img_base64))
                representative_image_path = file_path.replace("\\", "/")
                history_result["image_path"] = representative_image_path
            except Exception:
                history_result["image_path"] = ""

        history_service.add_entry({
            "type": "image_detection",
            "summary": {
                "total_vehicles": len(vehicles),
                "plates_detected": len(plates_found),
                "plates_found": plates_found
            },
            "representative_image_path": representative_image_path
        }, full_result=history_result)
        
        return result
        
    except Exception as e:
        print(f"🔥 ERROR trong /detect-plates: {e}")
        return {"error": str(e)}
