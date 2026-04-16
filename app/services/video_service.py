import os
import tempfile
import time
import cv2
import base64
import uuid
from ultralytics import YOLO
from app.config import MODEL_PATH
from app.services.plate_service import PlateRecognitionService
from app.services.history_service import history_service
from app.services.owner_service import owner_lookup_service


class VideoProcessingService:
    """Service xử lý video để nhận diện xe và biển số theo frame."""

    def __init__(self, model_path: str = MODEL_PATH):
        self.model = YOLO(model_path)
        self.plate_service = PlateRecognitionService(lang='vi')
        self.vehicle_classes = [2, 3, 5, 7]  # car, motorcycle, bus, truck

    def process_video_bytes(self, video_bytes: bytes, frame_skip: int = 10, max_frames: int = 20) -> dict:
        """Xử lý video upload và trả về kết quả nhận diện theo frame."""
        start_time = time.time()
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
            plates_map = {}
            plates_order = []

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
                        for vehicle in detection["vehicles"]:
                            plate_data = vehicle["plate"]
                            plate_text = plate_data.get("text")
                            ocr_confidence = plate_data.get("confidence", 0.0)
                            current_bbox = vehicle["bbox"]
                            if plate_text:
                                if plate_text not in plates_map:
                                    plates_map[plate_text] = {
                                        "plate": plate_text,
                                        "class_name": vehicle.get("class_name"),
                                        "first_seen_frame": frame_idx,
                                        "first_seen_time": round(frame_idx / fps, 2),
                                        "last_seen_frame": frame_idx,
                                        "last_seen_time": round(frame_idx / fps, 2),
                                        "count": 1,
                                        "confidence_sum": ocr_confidence,
                                        "confidence": round(ocr_confidence, 4),
                                        "last_bbox": current_bbox,
                                        "owner": plate_data.get("owner"),
                                    }
                                    plates_order.append(plate_text)
                                else:
                                    # Tính khoảng cách vị trí
                                    last_bbox = plates_map[plate_text]["last_bbox"]
                                    last_center = ((last_bbox[0] + last_bbox[2]) / 2, (last_bbox[1] + last_bbox[3]) / 2)
                                    current_center = ((current_bbox[0] + current_bbox[2]) / 2, (current_bbox[1] + current_bbox[3]) / 2)
                                    distance = ((last_center[0] - current_center[0]) ** 2 + (last_center[1] - current_center[1]) ** 2) ** 0.5
                                    
                                    # Chỉ update nếu confidence OCR cao hoặc vị trí thay đổi đáng kể
                                    if ocr_confidence > 0.8 or distance > 50:
                                        plates_map[plate_text]["last_seen_frame"] = frame_idx
                                        plates_map[plate_text]["last_seen_time"] = round(frame_idx / fps, 2)
                                        plates_map[plate_text]["count"] += 1
                                        plates_map[plate_text]["confidence_sum"] += ocr_confidence
                                        plates_map[plate_text]["confidence"] = round(
                                            plates_map[plate_text]["confidence_sum"] / plates_map[plate_text]["count"],
                                            4
                                        )
                                        plates_map[plate_text]["last_bbox"] = current_bbox
                                        if not (plates_map[plate_text].get("owner") or {}).get("found"):
                                            plates_map[plate_text]["owner"] = plate_data.get("owner")
                    processed_frames += 1

                frame_idx += 1

            cap.release()

            plates = []
            for plate_text in plates_order:
                plate_entry = plates_map[plate_text].copy()
                plate_entry.pop("confidence_sum", None)
                plate_entry.pop("last_bbox", None)
                plates.append(plate_entry)

            result = {
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
                "plates": plates,
                "results": results
            }

            history_result, representative_image_path = self._build_history_result(result)

            # Log summary cho lịch sử
            history_service.add_entry({
                "type": "video_processing",
                "method": "POST",
                "path": "/recognize-video",
                "summary": {
                    "total_frames": total_frames,
                    "processed_frames": processed_frames,
                    "unique_plates": len(plates),
                    "total_detections": sum(len(r["vehicles"]) for r in results),
                    "processing_time": round(time.time() - start_time, 3)
                },
                "plates_found": [p["plate"] for p in plates],
                "representative_image_path": representative_image_path
            }, full_result=history_result)

            return result

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
                    plate_result["owner"] = owner_lookup_service.find_owner_by_plate(plate_result.get("text", ""))
                    if plate_result.get("is_valid"):
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

    def _build_history_result(self, result: dict) -> tuple[dict, str]:
        """Tạo payload lịch sử nhẹ bằng cách lưu ảnh annotate ra file và chỉ giữ path."""
        history_results_dir = os.path.join("runs", "history_frames")
        os.makedirs(history_results_dir, exist_ok=True)

        compact_results = []
        representative_image_path = ""
        for item in result.get("results", []):
            compact_item = {
                "frame_index": item.get("frame_index"),
                "timestamp": item.get("timestamp"),
                "vehicles": item.get("vehicles", [])
            }

            annotated_b64 = item.get("annotated_frame")
            if annotated_b64:
                file_name = f"{int(time.time() * 1000)}_{uuid.uuid4().hex}.jpg"
                file_path = os.path.join(history_results_dir, file_name)
                try:
                    with open(file_path, "wb") as f:
                        f.write(base64.b64decode(annotated_b64))
                    normalized_path = file_path.replace("\\", "/")
                    compact_item["annotated_frame_path"] = normalized_path
                    if not representative_image_path:
                        representative_image_path = normalized_path
                except Exception:
                    compact_item["annotated_frame_path"] = ""

            compact_results.append(compact_item)

        return {
            "video_info": result.get("video_info", {}),
            "processing_info": result.get("processing_info", {}),
            "plates": result.get("plates", []),
            "results": compact_results
        }, representative_image_path

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

