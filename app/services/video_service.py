import os
import tempfile
import time
import cv2
import base64
import uuid
from collections import defaultdict, deque
from ultralytics import YOLO
from app.config import MODEL_PATH
import numpy as np
from app.services.plate_service import PlateRecognitionService
from app.services.history_service import history_service
from app.services.owner_service import owner_lookup_service
from app.services.machine_context import get_current_machine_id
from app.services.face_service import FaceRecognitionService


class VideoProcessingService:
    """Service xử lý video để nhận diện xe và biển số theo frame."""

    def __init__(self, model_path: str = MODEL_PATH):
        self.model = YOLO(model_path)
        self.plate_service = PlateRecognitionService(lang='vi')
        self.face_service = FaceRecognitionService()
        self.vehicle_classes = [2, 3, 5, 7]  # car, motorcycle, bus, truck
        self.live_plate_history = defaultdict(lambda: deque(maxlen=12))

    def process_video_bytes(
        self,
        video_bytes: bytes,
        frame_skip: int = 30,
        max_frames: int = 50,
    ) -> dict:
        """Xử lý video upload và trả về kết quả nhận diện theo frame."""
        start_time = time.time()
        temp_path = None
        print(f"[recognize-video] start frame_skip={frame_skip}, max_frames={max_frames}")

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
            duration = round(total_frames / fps, 2) if fps else 0.0

            # Chỉ xử lý các frame mẫu thay vì đọc tuần tự toàn bộ video.
            # Điều này làm thời gian xử lý tỉ lệ với số frame thật sự đem đi infer.
            sample_indices = list(range(0, max(1, total_frames), max(1, frame_skip)))
            if max_frames > 0:
                sample_indices = sample_indices[:max_frames]

            processed_frames = 0
            results = []
            plates_map = {}
            plates_order = []

            for frame_idx in sample_indices:
                if not cap.isOpened():
                    break

                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                grabbed, frame = cap.read()
                if not grabbed:
                    continue

                detection = self._process_frame(
                    frame,
                    require_valid_plate=True,
                    detect_conf=0.25,
                    detect_imgsz=640,
                    include_plate_candidates=False,
                    apply_preprocess=False,
                    include_annotated_frame=True,
                )
                print(
                    f"[recognize-video] sampled_frame={frame_idx}, "
                    f"vehicles={len(detection.get('vehicles', []))}, "
                    f"processed={processed_frames + 1}/{len(sample_indices)}"
                )
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
                    "duration": duration
                },
                "processing_info": {
                    "processed_frames": processed_frames,
                    "frame_skip": frame_skip,
                    "max_frames": max_frames,
                    "sampled_frames": len(sample_indices),
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

            print(
                f"[recognize-video] done elapsed={round(time.time() - start_time, 3)}s, "
                f"frames_with_detection={len(results)}, unique_plates={len(plates)}"
            )

            return result

        except Exception as e:
            print(f"[recognize-video] error: {e}")
            return {
                "error": str(e)
            }

        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

    def process_live_frame_bytes(
        self,
        image_bytes: bytes,
        include_annotated: bool = True,
        save_history: bool = True,
        history_only_when_detected: bool = True,
        detect_conf: float = 0.2,
        detect_imgsz: int = 960,
        include_candidates: bool = True,
        detect_faces: bool = True,
        face_threshold: float = 0.55,
        include_face_annotated: bool = False,
        save_history_image: bool = True,
    ) -> dict:
        """Xử lý 1 frame ảnh từ camera realtime và trả kết quả ngay."""
        start_time = time.time()
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                return {"error": "Decode ảnh lỗi"}

            detection = self._process_frame(
                frame,
                require_valid_plate=False,
                detect_conf=detect_conf,
                detect_imgsz=detect_imgsz,
                include_plate_candidates=include_candidates,
                include_annotated_frame=bool(include_annotated or save_history_image),
            )

            faces = []
            known_faces = 0
            face_annotated_frame = ""
            face_error = ""
            if detect_faces:
                face_result = self.face_service.recognize(frame, threshold=float(face_threshold))
                if face_result.get("error"):
                    face_error = str(face_result.get("error"))
                else:
                    faces = face_result.get("faces", []) if isinstance(face_result.get("faces"), list) else []
                    known_faces = sum(1 for item in faces if isinstance(item, dict) and item.get("is_known"))
                    face_annotated_frame = str(face_result.get("annotated_image", "") or "")

            vehicles = detection.get("vehicles", [])
            plates_found = []
            for vehicle in vehicles:
                plate_data = vehicle.get("plate") or {}
                plate_text = (plate_data.get("text") or "").strip()
                if plate_text and plate_data.get("is_valid"):
                    plates_found.append(plate_text)

            unique_plates = list(dict.fromkeys(plates_found))
            machine_id = (get_current_machine_id() or "default").strip() or "default"
            self._update_live_plate_history(machine_id, unique_plates)
            stable_plates = self._get_stable_plates(machine_id, min_hits=2)
            processing_time_ms = round((time.time() - start_time) * 1000, 2)

            has_face_detection = len(faces) > 0
            should_save_history = save_history and (
                (not history_only_when_detected) or len(unique_plates) > 0 or has_face_detection
            )

            representative_image_path = ""
            if should_save_history and save_history_image:
                # Nếu có mặt thì ưu tiên lưu ảnh annotate mặt để tra cứu lịch sử.
                history_b64 = face_annotated_frame if has_face_detection else detection.get("annotated_frame", "")
                representative_image_path = self._save_base64_image_to_history(history_b64)

            history_entry_id = ""
            if should_save_history:
                history_entry_id = history_service.add_entry({
                    "type": "live_camera_frame",
                    "method": "POST",
                    "path": "/recognize-live-frame",
                    "summary": {
                        "total_vehicles": len(vehicles),
                        "total_plates": len(unique_plates),
                        "plates_found": unique_plates,
                        "stable_plates": stable_plates,
                        "total_faces": len(faces),
                        "known_faces": known_faces,
                        "processing_time_ms": processing_time_ms,
                    },
                    "plates_found": unique_plates,
                    "representative_image_path": representative_image_path,
                }, full_result={
                    "source": "live_camera",
                    "summary": {
                        "total_vehicles": len(vehicles),
                        "total_plates": len(unique_plates),
                        "plates_found": unique_plates,
                        "stable_plates": stable_plates,
                        "total_faces": len(faces),
                        "known_faces": known_faces,
                        "processing_time_ms": processing_time_ms,
                    },
                    "vehicles": vehicles,
                    "faces": faces,
                    "face_error": face_error,
                    "annotated_frame_path": representative_image_path,
                })

            response = {
                "source": "live_camera",
                "timestamp": time.time(),
                "summary": {
                    "total_vehicles": len(vehicles),
                    "total_plates": len(unique_plates),
                    "plates_found": unique_plates,
                    "stable_plates": stable_plates,
                    "total_faces": len(faces),
                    "known_faces": known_faces,
                    "processing_time_ms": processing_time_ms,
                },
                "vehicles": vehicles,
                "faces": faces,
                "history": {
                    "storage": "common_history",
                    "saved": bool(history_entry_id),
                    "entry_id": history_entry_id,
                    "representative_image_path": representative_image_path,
                },
            }

            if include_annotated:
                response["annotated_frame"] = detection.get("annotated_frame", "")
            if include_face_annotated and detect_faces and face_annotated_frame:
                response["face_annotated_frame"] = face_annotated_frame
            if face_error:
                response["face_error"] = face_error

            print(
                f"[recognize-live-frame] vehicles={len(vehicles)}, plates={len(unique_plates)}, "
                f"faces={len(faces)}, saved_history={bool(history_entry_id)}, "
                f"elapsed_ms={processing_time_ms}"
            )

            return response
        except Exception as e:
            print(f"[recognize-live-frame] error: {e}")
            return {"error": str(e)}

    def _process_frame_with_options(
        self,
        frame: any,
        require_valid_plate: bool = True,
        detect_conf: float = 0.25,
        detect_imgsz: int = 960,
        include_plate_candidates: bool = False,
        apply_preprocess: bool = True,
        include_annotated_frame: bool = True,
    ) -> dict:
        """Detect xe và nhận diện biển số với tham số tuning cho realtime."""
        # Preprocessing: Tăng contrast để nhận diện biển số tốt hơn
        processed_frame = self._preprocess_frame(frame) if apply_preprocess else frame
        tuned_conf = min(0.8, max(0.05, float(detect_conf)))
        tuned_imgsz = min(1280, max(320, int(detect_imgsz)))
        results = self.model(processed_frame, conf=tuned_conf, imgsz=tuned_imgsz, classes=self.vehicle_classes, verbose=False)
        vehicles = []

        for r in results:
            if r.boxes is None:
                continue

            for box in r.boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                xyxy = [float(v) for v in box.xyxy[0].tolist()]

                if class_id in self.vehicle_classes:
                    plate_result = self.plate_service.recognize_plate_from_coordinates(processed_frame, xyxy)
                    if not include_plate_candidates and isinstance(plate_result, dict):
                        plate_result.pop("candidates", None)
                    plate_result["owner"] = owner_lookup_service.find_owner_by_plate(plate_result.get("text", ""))
                    if require_valid_plate and not plate_result.get("is_valid"):
                        continue

                    vehicles.append({
                        "class_id": class_id,
                        "class_name": self._get_class_name(class_id),
                        "confidence": round(confidence, 4),
                        "bbox": [round(v, 2) for v in xyxy],
                        "plate": plate_result
                    })

        # Chỉ encode annotated khi thực sự cần để giảm tải CPU/response size.
        annotated_base64 = ""
        if include_annotated_frame and vehicles:
            if results:
                annotated = results[0].plot()
            else:
                annotated = processed_frame
            _, buffer = cv2.imencode('.jpg', annotated)
            annotated_base64 = base64.b64encode(buffer).decode()

        return {
            "vehicles": vehicles,
            "annotated_frame": annotated_base64
        }

    def _process_frame(self, frame: any, require_valid_plate: bool = True, detect_conf: float = 0.25, detect_imgsz: int = 960, include_plate_candidates: bool = False, apply_preprocess: bool = True, include_annotated_frame: bool = True) -> dict:
        """Backward-compatible wrapper cho xử lý frame."""
        return self._process_frame_with_options(
            frame,
            require_valid_plate=require_valid_plate,
            detect_conf=detect_conf,
            detect_imgsz=detect_imgsz,
            include_plate_candidates=include_plate_candidates,
            apply_preprocess=apply_preprocess,
            include_annotated_frame=include_annotated_frame,
        )

    def _update_live_plate_history(self, machine_id: str, plates: list[str]) -> None:
        """Lưu lịch sử biển số gần nhất để ổn định kết quả realtime."""
        history = self.live_plate_history[machine_id]
        history.append(list(dict.fromkeys(plates)))

    def _get_stable_plates(self, machine_id: str, min_hits: int = 2) -> list[str]:
        """Trả về biển số xuất hiện lặp lại qua nhiều frame gần nhất."""
        history = self.live_plate_history.get(machine_id)
        if not history:
            return []

        counts = {}
        for frame_plates in history:
            for plate in frame_plates:
                counts[plate] = counts.get(plate, 0) + 1

        stable = [plate for plate, hits in counts.items() if hits >= max(1, int(min_hits))]
        stable.sort(key=lambda plate: counts[plate], reverse=True)
        return stable

    def _save_base64_image_to_history(self, img_b64: str) -> str:
        """Lưu ảnh base64 thành file để gắn vào lịch sử."""
        if not img_b64:
            return ""

        history_results_dir = os.path.join("runs", "history_frames")
        os.makedirs(history_results_dir, exist_ok=True)
        file_name = f"{int(time.time() * 1000)}_{uuid.uuid4().hex}.jpg"
        file_path = os.path.join(history_results_dir, file_name)
        try:
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(img_b64))
            return file_path.replace("\\", "/")
        except Exception:
            return ""

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


    def _preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Preprocessing ảnh để tăng khả năng detect biển số.
        - CLAHE: Tăng contrast cục bộ
        - Brightness adjustment: Tăng độ sáng nếu cần
        """
        try:
            # Chuyển sang LAB color space để tăng contrast L channel
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l_channel = lab[:, :, 0]
            
            # Áp dụng CLAHE (Contrast Limited Adaptive Histogram Equalization)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced_l = clahe.apply(l_channel)
            
            # Kết hợp lại LAB image
            lab[:, :, 0] = enhanced_l
            enhanced_frame = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            
            # Optional: Thêm chút brightness nếu hình quá tối
            brightness_value = np.mean(enhanced_frame)
            if brightness_value < 90:
                enhanced_frame = cv2.convertScaleAbs(enhanced_frame, alpha=1.1, beta=15)
            
            return enhanced_frame
        except Exception as e:
            print(f"Preprocessing error: {e}")
            return frame

