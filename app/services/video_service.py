import os
import tempfile
import cv2
import base64
from ultralytics import YOLO
from app.config import MODEL_PATH
from app.services.plate_service import PlateRecognitionService


class VideoProcessingService:
    """Service xử lý video để nhận diện xe và biển số theo frame."""

    def __init__(self, model_path: str = MODEL_PATH):
        self.model = YOLO(model_path)
        self.plate_service = PlateRecognitionService(lang='vi')
        self.vehicle_classes = [2, 3, 5, 7]  # car, motorcycle, bus, truck

    def process_video_bytes(self, video_bytes: bytes, frame_skip: int = 10, max_frames: int = 20) -> dict:
        """Xử lý video upload và trả về kết quả nhận diện theo frame."""
        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                tmp_file.write(video_bytes)
                tmp_file.flush()
                temp_path = tmp_file.name

            cap = cv2.VideoCapture(temp_path)
            if not cap.isOpened():
                return {
                    "error": "Không mở được video."
                }

            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            frame_idx = 0
            processed_frames = 0
            results = []

            while processed_frames < max_frames and cap.isOpened():
                grabbed, frame = cap.read()
                if not grabbed:
                    break

                if frame_idx % frame_skip == 0:
                    detection = self._process_frame(frame)
                    if detection["vehicles"]:
                        results.append({
                            "frame_index": frame_idx,
                            "timestamp": round(frame_idx / fps, 2),
                            "vehicles": detection["vehicles"],
                            "annotated_frame": detection["annotated_frame"]
                        })
                    processed_frames += 1

                frame_idx += 1

            cap.release()

            return {
                "video_info": {
                    "total_frames": total_frames,
                    "fps": round(fps, 2),
                    "width": width,
                    "height": height,
                    "duration": round(total_frames / fps, 2)
                },
                "processing_info": {
                    "processed_frames": processed_frames,
                    "frame_skip": frame_skip,
                    "max_frames": max_frames,
                    "frames_processed": len(results)
                },
                "results": results
            }

        except Exception as e:
            return {
                "error": str(e)
            }

        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

    def _process_frame(self, frame: any) -> dict:
        """Detect xe và nhận diện biển số trên một frame."""
        results = self.model(frame)
        vehicles = []

        for r in results:
            if r.boxes is None:
                continue

            for box in r.boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                xyxy = [float(v) for v in box.xyxy[0].tolist()]

                if class_id in self.vehicle_classes:
                    plate_result = self.plate_service.recognize_plate_from_coordinates(frame, xyxy)
                    vehicles.append({
                        "class_id": class_id,
                        "class_name": self._get_class_name(class_id),
                        "confidence": round(confidence, 4),
                        "bbox": [round(v, 2) for v in xyxy],
                        "plate": plate_result
                    })

        # Annotate frame
        annotated = results[0].plot()
        _, buffer = cv2.imencode('.jpg', annotated)
        annotated_base64 = base64.b64encode(buffer).decode()

        return {
            "vehicles": vehicles,
            "annotated_frame": annotated_base64
        }

    def _get_class_name(self, class_id: int) -> str:
        """Map class ID to class name."""
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
        return class_names.get(class_id, "unknown")

