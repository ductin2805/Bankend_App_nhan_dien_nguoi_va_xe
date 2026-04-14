"""Service nhận diện khuôn mặt và quản lý danh bạ khuôn mặt."""

import json
import os
import time
import uuid
from typing import Any

import cv2
import numpy as np
from skimage.feature import hog

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover - fallback when Pillow is unavailable
    Image = None
    ImageDraw = None
    ImageFont = None

from app.utils.image_utils import encode_image_to_base64
from app.services.machine_context import get_current_machine_id


class FaceRecognitionService:
    """Service đăng ký và nhận diện khuôn mặt theo ảnh."""

    def __init__(self, db_path: str = "runs/face_db.json"):
        self.db_path = db_path
        self.data = {"persons": []}
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.embedding_backend = "hog"
        self.face_analyzer = None
        os.makedirs("runs", exist_ok=True)
        self._init_embedding_backend()
        self._load_db()

    def _init_embedding_backend(self) -> None:
        """Ưu tiên ArcFace (InsightFace), fallback về HOG khi thiếu dependency/model."""
        try:
            from insightface.app import FaceAnalysis

            self.face_analyzer = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
            self.face_analyzer.prepare(ctx_id=0, det_size=(640, 640))
            self.embedding_backend = "arcface"
        except Exception:
            self.face_analyzer = None
            self.embedding_backend = "hog"

    def _load_db(self) -> None:
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {"persons": []}

    def _save_db(self) -> None:
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _face_descriptor(face_bgr: np.ndarray) -> list[float]:
        # Descriptor robust hơn raw pixel: CLAHE + HOG
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (96, 96), interpolation=cv2.INTER_AREA)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        feat = hog(
            gray,
            orientations=9,
            pixels_per_cell=(8, 8),
            cells_per_block=(2, 2),
            block_norm="L2-Hys",
            feature_vector=True,
        ).astype(np.float32)

        norm = np.linalg.norm(feat)
        if norm > 0:
            feat = feat / norm
        return feat.tolist()

    @staticmethod
    def _augment_face_samples(face_bgr: np.ndarray) -> list[np.ndarray]:
        samples = [face_bgr]

        # Mirror sample
        samples.append(cv2.flip(face_bgr, 1))

        # Brightness variants
        for alpha, beta in [(1.08, 10), (0.92, -10)]:
            adj = cv2.convertScaleAbs(face_bgr, alpha=alpha, beta=beta)
            samples.append(adj)

        return samples

    def _detect_faces(self, image: np.ndarray) -> list[tuple[int, int, int, int]]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
        return [(int(x), int(y), int(w), int(h)) for x, y, w, h in faces]

    @staticmethod
    def _to_bbox_xyxy(x: int, y: int, w: int, h: int, width: int, height: int) -> list[int]:
        x1 = max(0, int(x))
        y1 = max(0, int(y))
        x2 = min(width - 1, int(x + w))
        y2 = min(height - 1, int(y + h))
        return [x1, y1, x2, y2]

    def _extract_face_candidates(self, image: np.ndarray) -> list[dict[str, Any]]:
        """Chuẩn hóa đầu ra detect+embedding để các pipeline phía trên dùng chung."""
        h, w = image.shape[:2]

        if self.embedding_backend == "arcface" and self.face_analyzer is not None:
            try:
                faces = self.face_analyzer.get(image)
                candidates: list[dict[str, Any]] = []
                for face in faces:
                    bbox = face.bbox.astype(np.int32).tolist() if getattr(face, "bbox", None) is not None else []
                    emb = getattr(face, "normed_embedding", None)
                    if len(bbox) != 4 or emb is None:
                        continue
                    x1, y1, x2, y2 = bbox
                    x1 = max(0, min(int(x1), w - 1))
                    y1 = max(0, min(int(y1), h - 1))
                    x2 = max(0, min(int(x2), w - 1))
                    y2 = max(0, min(int(y2), h - 1))
                    if x2 <= x1 or y2 <= y1:
                        continue
                    candidates.append(
                        {
                            "bbox": [x1, y1, x2, y2],
                            "descriptor": np.asarray(emb, dtype=np.float32).tolist(),
                            "area": (x2 - x1) * (y2 - y1),
                        }
                    )
                return candidates
            except Exception:
                self.embedding_backend = "hog"

        # Fallback HOG pipeline
        candidates = []
        faces = self._detect_faces(image)
        for x, y, fw, fh in faces:
            x1, y1, x2, y2 = self._to_bbox_xyxy(x, y, fw, fh, w, h)
            crop = image[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            descriptor = self._face_descriptor(crop)
            candidates.append(
                {
                    "bbox": [x1, y1, x2, y2],
                    "descriptor": descriptor,
                    "area": (x2 - x1) * (y2 - y1),
                    "crop": crop,
                }
            )
        return candidates

    @staticmethod
    def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        a = np.array(vec1, dtype=np.float32)
        b = np.array(vec2, dtype=np.float32)
        if a.shape != b.shape:
            return 0.0
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)

    @staticmethod
    def _draw_text_with_unicode(
        image: np.ndarray,
        text: str,
        org: tuple[int, int],
        color: tuple[int, int, int],
        font_size: int = 20,
    ) -> None:
        if Image is None or ImageDraw is None or ImageFont is None:
            cv2.putText(
                image,
                text,
                org,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
                lineType=cv2.LINE_AA,
            )
            return

        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_image)
        draw = ImageDraw.Draw(pil_image)

        font = None
        font_candidates = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/tahoma.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "arial.ttf",
            "tahoma.ttf",
            "segoeui.ttf",
        ]
        for font_path in font_candidates:
            try:
                font = ImageFont.truetype(font_path, size=font_size)
                break
            except Exception:
                continue

        if font is None:
            cv2.putText(
                image,
                text,
                org,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
                lineType=cv2.LINE_AA,
            )
            return

        # Convert BGR -> RGB for PIL drawing color.
        draw.text((org[0], org[1] - font_size), text, fill=(color[2], color[1], color[0]), font=font)
        updated = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        image[:, :] = updated

    def register_person(self, image: np.ndarray, name: str, person_code: str = "", info: dict[str, Any] | None = None, machine_id: str | None = None) -> dict:
        candidates = self._extract_face_candidates(image)
        if not candidates:
            return {"error": "Không phát hiện khuôn mặt."}

        best = max(candidates, key=lambda item: item.get("area", 0))
        x1, y1, x2, y2 = best["bbox"]

        if self.embedding_backend == "arcface":
            descriptors = [best["descriptor"]]
        else:
            face_crop = best.get("crop")
            if face_crop is None or face_crop.size == 0:
                face_crop = image[y1:y2, x1:x2]
            samples = self._augment_face_samples(face_crop)
            descriptors = [self._face_descriptor(sample) for sample in samples]

        person_id = str(uuid.uuid4())
        machine_scope = (machine_id or get_current_machine_id() or "default").strip() or "default"
        person = {
            "person_id": person_id,
            "machine_id": machine_scope,
            "name": name,
            "person_code": person_code,
            "info": info or {},
            "descriptors": descriptors,
            "created_at": time.time(),
        }

        self.data.setdefault("persons", []).append(person)
        self._save_db()

        annotated = image.copy()
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 200, 0), 2)
        self._draw_text_with_unicode(annotated, f"Registered: {name}", (x1, max(24, y1 - 10)), (0, 200, 0))

        return {
            "person_id": person_id,
            "name": name,
            "person_code": person_code,
            "registered": True,
            "bbox": [x1, y1, x2, y2],
            "samples": len(descriptors),
            "embedding_backend": self.embedding_backend,
            "annotated_image": encode_image_to_base64(annotated),
        }

    def recognize(self, image: np.ndarray, threshold: float = 0.55, machine_id: str | None = None) -> dict:
        face_candidates = self._extract_face_candidates(image)
        annotated = image.copy()
        candidate_results = []

        machine_scope = (machine_id or get_current_machine_id() or "default").strip() or "default"
        persons = [person for person in self.data.get("persons", []) if (person.get("machine_id") or "default") == machine_scope]

        for candidate in face_candidates:
            x1, y1, x2, y2 = candidate["bbox"]
            descriptor = candidate["descriptor"]

            best_person = None
            best_score = -1.0
            for person in persons:
                person_descs = person.get("descriptors") or []
                # Backward compatibility for old records
                if not person_descs and person.get("descriptor"):
                    person_descs = [person.get("descriptor")]
                if not person_descs:
                    continue

                scores = [self._cosine_similarity(descriptor, d) for d in person_descs]
                scores.sort(reverse=True)
                top_k = scores[: min(3, len(scores))]
                score = float(sum(top_k) / len(top_k)) if top_k else 0.0
                if score > best_score:
                    best_score = score
                    best_person = person

            is_known = bool(best_person and best_score >= threshold)
            label = "Unknown"
            person_info = None
            person_id = ""

            if is_known and best_person:
                person_id = best_person.get("person_id", "")
                label = best_person.get("name", "Unknown")
                person_info = {
                    "person_id": person_id,
                    "name": best_person.get("name", ""),
                    "person_code": best_person.get("person_code", ""),
                    "info": best_person.get("info", {}),
                }

            candidate_results.append(
                {
                    "bbox": [x1, y1, x2, y2],
                    "is_known": is_known,
                    "match_score": round(best_score, 4),
                    "label": label,
                    "person": person_info,
                }
            )

        best_result = None
        if candidate_results:
            best_result = max(candidate_results, key=lambda item: item.get("match_score", 0.0))
            bx1, by1, bx2, by2 = best_result["bbox"]
            color = (0, 200, 0) if best_result.get("is_known") else (0, 0, 255)
            cv2.rectangle(annotated, (bx1, by1), (bx2, by2), color, 2)
            self._draw_text_with_unicode(
                annotated,
                f"{best_result.get('label', 'Unknown')} ({best_result.get('match_score', 0.0):.2f})",
                (bx1, max(24, by1 - 10)),
                color,
            )
            best_result.pop("label", None)

        return {
            "total_faces": 1 if best_result else 0,
            "faces": [best_result] if best_result else [],
            "annotated_image": encode_image_to_base64(annotated),
            "threshold": threshold,
            "embedding_backend": self.embedding_backend,
        }

    def list_persons(self, machine_id: str | None = None) -> list[dict]:
        machine_scope = (machine_id or get_current_machine_id() or "default").strip() or "default"
        persons = []
        for person in self.data.get("persons", []):
            if (person.get("machine_id") or "default") != machine_scope:
                continue
            persons.append(
                {
                    "person_id": person.get("person_id"),
                    "name": person.get("name"),
                    "person_code": person.get("person_code"),
                    "info": person.get("info", {}),
                    "registration_image_path": person.get("registration_image_path", ""),
                    "created_at": person.get("created_at"),
                }
            )
        return persons

    def set_registration_image_path(self, person_id: str, image_path: str, machine_id: str | None = None) -> bool:
        machine_scope = (machine_id or get_current_machine_id() or "default").strip() or "default"
        persons = self.data.get("persons", [])
        for person in persons:
            if person.get("person_id") == person_id and (person.get("machine_id") or "default") == machine_scope:
                person["registration_image_path"] = image_path or ""
                self._save_db()
                return True
        return False

    def update_person(
        self,
        person_id: str,
        name: str | None = None,
        person_code: str | None = None,
        info: dict[str, Any] | None = None,
        registration_image_path: str | None = None,
        machine_id: str | None = None,
    ) -> dict:
        machine_scope = (machine_id or get_current_machine_id() or "default").strip() or "default"
        persons = self.data.get("persons", [])
        for person in persons:
            if person.get("person_id") != person_id or (person.get("machine_id") or "default") != machine_scope:
                continue

            if name is not None:
                person["name"] = name
            if person_code is not None:
                person["person_code"] = person_code
            if info is not None:
                current_info = person.get("info", {})
                current_info.update(info)
                person["info"] = current_info
            if registration_image_path is not None:
                person["registration_image_path"] = registration_image_path

            self._save_db()
            return {
                "person_id": person.get("person_id"),
                "name": person.get("name"),
                "person_code": person.get("person_code"),
                "info": person.get("info", {}),
                "registration_image_path": person.get("registration_image_path", ""),
                "created_at": person.get("created_at"),
            }

        return {"error": "Person not found"}

    def delete_person(self, person_id: str, machine_id: str | None = None) -> bool:
        machine_scope = (machine_id or get_current_machine_id() or "default").strip() or "default"
        persons = self.data.get("persons", [])
        new_persons = [p for p in persons if p.get("person_id") != person_id or (p.get("machine_id") or "default") != machine_scope]
        if len(new_persons) == len(persons):
            return False
        self.data["persons"] = new_persons
        self._save_db()
        return True
