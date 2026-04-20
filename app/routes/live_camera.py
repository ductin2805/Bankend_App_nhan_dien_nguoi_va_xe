from fastapi import APIRouter, UploadFile, Query
from fastapi.concurrency import run_in_threadpool
from app.services.video_processing_singleton import video_processing_service

router = APIRouter(tags=["live-camera"])


@router.get("/recognize-live-frame/options")
async def get_live_camera_options():
    """Trả về dải thông số gợi ý để Flutter render setting cho live camera."""
    return {
        "live_camera": {
            "resolution_preset": {
                "default": "high",
                "options": ["medium", "high", "veryHigh"],
                "recommended": ["high", "veryHigh"],
                "notes": "Ưu tiên high/veryHigh để biển số đủ nét"
            },
            "fps": {
                "min": 8,
                "max": 24,
                "default": 15,
                "recommended": [12, 15, 20],
                "notes": "FPS cao hơn tăng tải CPU/network"
            },
            "jpeg_quality": {
                "min": 70,
                "max": 95,
                "default": 85,
                "recommended": [80, 85, 90],
                "notes": "Không nên dưới 75 để tránh mờ biển số"
            },
            "zoom": {
                "min": 1.0,
                "max": 3.0,
                "default": 1.4,
                "recommended": [1.2, 1.4, 1.8],
                "notes": "Zoom vừa phải giúp biển số lớn hơn nhưng tránh rung"
            },
            "exposure_offset": {
                "min": -1.5,
                "max": 1.5,
                "default": 0.0,
                "recommended": [-0.3, 0.0, 0.3],
                "notes": "Tăng nhẹ khi thiếu sáng, giảm khi bị chói"
            }
        },
        "live_query": {
            "include_annotated": {
                "default": True,
                "notes": "Trả ảnh annotate để Flutter preview"
            },
            "save_history": {
                "default": True,
                "notes": "Lưu lịch sử cho frame live"
            },
            "history_only_when_detected": {
                "default": True,
                "notes": "Chỉ lưu khi có biển số hoặc mặt detect được"
            },
            "detect_conf": {
                "min": 0.05,
                "max": 0.8,
                "default": 0.25,
                "recommended": [0.2, 0.25, 0.3]
            },
            "detect_imgsz": {
                "min": 320,
                "max": 1280,
                "default": 640,
                "recommended": [640, 768, 960]
            },
            "include_candidates": {
                "default": True,
                "notes": "Trả thêm candidate OCR theo nhiều ROI"
            },
            "detect_faces": {
                "default": True,
                "notes": "Bật nhận diện khuôn mặt cho live frame"
            },
            "face_threshold": {
                "min": 0.0,
                "max": 1.0,
                "default": 0.55,
                "recommended": [0.5, 0.55, 0.6]
            },
            "include_face_annotated": {
                "default": False,
                "notes": "Chỉ trả ảnh annotate mặt khi cần debug"
            },
            "save_history_image": {
                "default": True,
                "notes": "Lưu ảnh đại diện vào runs/history_frames"
            }
        },
        "presets": {
            "balanced": {
                "flutter": {
                    "resolution_preset": "high",
                    "fps": 15,
                    "jpeg_quality": 85,
                    "zoom": 1.4,
                    "exposure_offset": 0.0
                },
                "backend": {
                    "detect_conf": 0.2,
                    "detect_imgsz": 960,
                    "face_threshold": 0.55
                }
            },
            "accuracy_first": {
                "flutter": {
                    "resolution_preset": "veryHigh",
                    "fps": 12,
                    "jpeg_quality": 90,
                    "zoom": 1.6,
                    "exposure_offset": 0.1
                },
                "backend": {
                    "detect_conf": 0.15,
                    "detect_imgsz": 1024,
                    "face_threshold": 0.5
                }
            },
            "performance_first": {
                "flutter": {
                    "resolution_preset": "high",
                    "fps": 20,
                    "jpeg_quality": 80,
                    "zoom": 1.2,
                    "exposure_offset": 0.0
                },
                "backend": {
                    "detect_conf": 0.25,
                    "detect_imgsz": 768,
                    "face_threshold": 0.6
                }
            },
            "low_light": {
                "flutter": {
                    "resolution_preset": "veryHigh",
                    "fps": 10,
                    "jpeg_quality": 90,
                    "zoom": 1.3,
                    "exposure_offset": 0.3
                },
                "backend": {
                    "detect_conf": 0.15,
                    "detect_imgsz": 1024,
                    "face_threshold": 0.5
                }
            }
        }
    }


@router.post("/recognize-live-frame")
async def recognize_live_frame(
    file: UploadFile,
    include_annotated: bool = Query(True, description="Trả ảnh frame đã annotate (base64)"),
    save_history: bool = Query(True, description="Có lưu vào lịch sử chung hay không"),
    history_only_when_detected: bool = Query(True, description="Chỉ lưu lịch sử khi có biển số"),
    detect_conf: float = Query(0.25, ge=0.05, le=0.8, description="Ngưỡng confidence detect xe cho realtime"),
    detect_imgsz: int = Query(640, ge=320, le=1280, description="Kích thước input YOLO khi infer realtime"),
    include_candidates: bool = Query(True, description="Trả danh sách candidate OCR theo nhiều ROI"),
    detect_faces: bool = Query(True, description="Bật nhận diện khuôn mặt trong frame live"),
    face_threshold: float = Query(0.55, ge=0.0, le=1.0, description="Ngưỡng nhận diện khuôn mặt"),
    include_face_annotated: bool = Query(False, description="Trả thêm ảnh annotate khuôn mặt (base64)"),
    save_history_image: bool = Query(True, description="Lưu ảnh đại diện vào history_frames"),
):
    """Nhận diện biển số từ 1 frame ảnh gửi lên từ camera realtime."""
    contents = await file.read()
    return await run_in_threadpool(
        video_processing_service.process_live_frame_bytes,
        contents,
        include_annotated,
        save_history,
        history_only_when_detected,
        detect_conf,
        detect_imgsz,
        include_candidates,
        detect_faces,
        face_threshold,
        include_face_annotated,
        save_history_image,
    )
