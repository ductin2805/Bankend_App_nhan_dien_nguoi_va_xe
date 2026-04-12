"""API routes cho nhận diện khuôn mặt."""

import base64
import os
import time
import uuid

from fastapi import APIRouter, UploadFile, Form, Query

from app.services.face_service import FaceRecognitionService
from app.services.history_service import history_service
from app.utils.image_utils import load_image_from_bytes

router = APIRouter(tags=["face"])
face_service = FaceRecognitionService()


def _save_base64_image_to_history(img_b64: str) -> str:
    """Lưu ảnh base64 thành file để history không bị phình payload."""
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


@router.post("/face/register")
async def register_face(
    file: UploadFile,
    name: str = Form(...),
    person_code: str = Form(""),
    department: str = Form(""),
    role: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    age: str = Form(""),
    date_of_birth: str = Form(""),
    cccd: str = Form(""),
):
    """Đăng ký khuôn mặt và thông tin người."""
    try:
        contents = await file.read()
        img = load_image_from_bytes(contents)
        if img is None:
            return {"error": "Decode ảnh lỗi"}

        info = {
            "department": department,
            "role": role,
            "phone": phone,
            "address": address,
            "age": age,
            "date_of_birth": date_of_birth,
            "cccd": cccd,
        }
        result = face_service.register_person(img, name=name, person_code=person_code, info=info)

        if not result.get("error"):
            image_path = _save_base64_image_to_history(result.get("annotated_image", ""))
            history_result = {
                "person_id": result.get("person_id", ""),
                "name": result.get("name", ""),
                "person_code": result.get("person_code", ""),
                "registered": result.get("registered", False),
                "bbox": result.get("bbox", []),
                "samples": result.get("samples", 0),
                "image_path": image_path,
            }

            history_service.add_entry(
                {
                    "type": "face_registration",
                    "method": "POST",
                    "path": "/face/register",
                    "summary": {
                        "name": result.get("name", ""),
                        "person_code": result.get("person_code", ""),
                        "registered": result.get("registered", False),
                    },
                    "representative_image_path": image_path,
                },
                full_result=history_result,
            )
        return result
    except Exception as e:
        return {"error": str(e)}


@router.post("/face/recognize")
async def recognize_face(
    file: UploadFile,
    threshold: float = Query(0.55, ge=0.0, le=1.0, description="Ngưỡng nhận diện khuôn mặt"),
):
    """Nhận diện khuôn mặt từ ảnh và trả thông tin người."""
    try:
        contents = await file.read()
        img = load_image_from_bytes(contents)
        if img is None:
            return {"error": "Decode ảnh lỗi"}

        result = face_service.recognize(img, threshold=threshold)

        if not result.get("error"):
            faces = result.get("faces", [])
            best_face = faces[0] if isinstance(faces, list) and faces else {}
            image_path = _save_base64_image_to_history(result.get("annotated_image", ""))
            history_result = {
                "total_faces": result.get("total_faces", 0),
                "faces": faces,
                "threshold": result.get("threshold", threshold),
                "image_path": image_path,
            }

            history_service.add_entry(
                {
                    "type": "face_recognition",
                    "method": "POST",
                    "path": "/face/recognize",
                    "summary": {
                        "total_faces": result.get("total_faces", 0),
                        "is_known": best_face.get("is_known", False),
                        "match_score": best_face.get("match_score", 0.0),
                        "person_name": ((best_face.get("person") or {}).get("name", "") if isinstance(best_face, dict) else ""),
                    },
                    "representative_image_path": image_path,
                },
                full_result=history_result,
            )

        return result
    except Exception as e:
        return {"error": str(e)}


@router.get("/face/persons")
async def list_faces():
    """Lấy danh sách người đã đăng ký khuôn mặt."""
    return {
        "total_persons": len(face_service.list_persons()),
        "persons": face_service.list_persons(),
    }


@router.delete("/face/person/{person_id}")
async def delete_face_person(person_id: str):
    """Xóa một người khỏi danh bạ khuôn mặt."""
    deleted = face_service.delete_person(person_id)
    if not deleted:
        return {"error": "Person not found"}
    return {"message": "Deleted person", "person_id": person_id}
