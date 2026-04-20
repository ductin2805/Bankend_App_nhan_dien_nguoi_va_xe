from app.services.video_service import VideoProcessingService

# Dùng chung 1 instance để tránh load YOLO model nhiều lần.
video_processing_service = VideoProcessingService()
