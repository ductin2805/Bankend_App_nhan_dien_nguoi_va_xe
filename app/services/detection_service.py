"""Service cho object detection."""

from ultralytics import YOLO
import numpy as np
import cv2
from app.config import MODEL_PATH
from app.utils.image_utils import encode_image_to_base64


class DetectionService:
    """Service xử lý detection với YOLO model."""
    
    def __init__(self, model_path: str = MODEL_PATH):
        """
        Khởi tạo DetectionService.
        
        Args:
            model_path: Đường dẫn đến YOLO model
        """
        self.model = YOLO(model_path)
        self.plate_service = None
    
    def set_plate_service(self, plate_service):
        """Set plate recognition service."""
        self.plate_service = plate_service
    
    def detect_objects(self, image: np.ndarray, recognize_plates: bool = False) -> dict:
        """
        Detect objects trong ảnh.
        
        Args:
            image: cv2 image array
            recognize_plates: Có nhận dạng biển số hay không
            
        Returns:
            Dict chứa detections và annotated image (base64)
        """
        # Run detection
        results = self.model(image)
        
        # Extract detections
        detections = self._extract_detections(results)
        
        # Recognize plates nếu có
        if recognize_plates and self.plate_service:
            detections = self._recognize_plates(image, detections)
        
        # Annotate image
        annotated = results[0].plot()
        
        # Encode to base64
        img_base64 = encode_image_to_base64(annotated)
        
        return {
            "detections": detections,
            "image": img_base64
        }
    
    def _recognize_plates(self, image: np.ndarray, detections: list) -> list:
        """
        Recognize plates từ detected objects.
        
        Args:
            image: Original cv2 image
            detections: List of detections
            
        Returns:
            Detections với plate text (nếu có)
        """
        for detection in detections:
            # Có thể setup class IDs cho plate (ví dụ: 0 = person, 2 = car, etc.)
            # Thêm plate recognition vào mỗi detection nếu cần
            detection['plate_text'] = None
        
        return detections
    
    @staticmethod
    def _extract_detections(results) -> list:
        """
        Extract detection information từ YOLO results.
        
        Args:
            results: YOLO detection results
            
        Returns:
            List of detections với class, confidence, và coordinates
        """
        detections = []
        
        for r in results:
            if r.boxes is None:
                continue
            
            for box in r.boxes:
                detections.append({
                    "class": int(box.cls[0]),
                    "confidence": float(box.conf[0]),
                    "xyxy": box.xyxy[0].tolist()
                })
        
        return detections
