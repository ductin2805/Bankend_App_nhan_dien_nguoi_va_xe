from fastapi import APIRouter, UploadFile, Query
from app.services.video_service import VideoProcessingService

router = APIRouter(tags=["realtime"])
video_service = VideoProcessingService()


@router.post("/recognize-video")
async def recognize_video(
    file: UploadFile,
    frame_skip: int = Query(30, ge=1, description="Số frame bỏ qua giữa mỗi lần xử lý"),
    max_frames: int = Query(50, ge=1, description="Số frame tối đa sẽ xử lý")
):
    """Nhận diện xe và biển số từ video upload."""
    contents = await file.read()
    result = video_service.process_video_bytes(contents, frame_skip=frame_skip, max_frames=max_frames)
    return result
