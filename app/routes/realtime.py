from fastapi import APIRouter, UploadFile, Query
from fastapi.concurrency import run_in_threadpool
from app.services.video_processing_singleton import video_processing_service

router = APIRouter(tags=["realtime"])


@router.post("/recognize-video")
async def recognize_video(
    file: UploadFile,
    frame_skip: int = Query(30, ge=1, description="Số frame bỏ qua giữa mỗi lần xử lý"),
    max_frames: int = Query(5, ge=1, description="Số frame tối đa sẽ xử lý"),
):
    """Nhận diện xe và biển số từ video upload."""
    contents = await file.read()
    # Move CPU-heavy OpenCV/YOLO pipeline to a worker thread so
    # long video requests do not block the FastAPI event loop.
    result = await run_in_threadpool(
        video_processing_service.process_video_bytes,
        contents,
        frame_skip,
        max_frames,
    )
    return result
