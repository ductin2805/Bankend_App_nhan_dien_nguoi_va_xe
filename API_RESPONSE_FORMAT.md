"""
API Response Format Documentation
==================================

## 1. POST /recognize-video
Nhận diện xe và biển số từ video upload.

### Response format:
{
  "video_info": {
    "total_frames": 150,                  // Tổng số frame trong video
    "fps": 25.0,                          // Frame per second
    "width": 1920,                        // Chiều rộng video
    "height": 1080,                       // Chiều cao video
    "duration": 6.0                       // Thời lượng video (giây)
  },
  "processing_info": {
    "processed_frames": 20,               // Số frame đã xử lý
    "frame_skip": 10,                     // Khoảng cách giữa các frame xử lý
    "max_frames": 20,                     // Giới hạn frame xử lý
    "frames_processed": 15                // Số frame có kết quả (có xe)
  },
  "results": [
    {
      "frame_index": 0,                   // Index của frame trong video
      "timestamp": 0.0,                   // Thời gian (giây) trong video
      "vehicles": [
        {
          "class_id": 2,                  // 0=person, 2=car, 3=motorcycle, 5=bus, 7=truck
          "class_name": "car",            // Tên class
          "confidence": 0.95,             // Độ tin cậy phát hiện (0-1)
          "bbox": [100.5, 200.3, 300.2, 400.8],  // [x1, y1, x2, y2] toạ độ
          "plate": {
            "text": "61A-66666",          // Kết quả nhận diện biển số
            "confidence": 0.927,          // Độ tin cậy OCR
            "details": [
              {"text": "61A", "conf": 0.995},
              {"text": "66666", "conf": 0.859}
            ]
          }
        }
      ],
      "annotated_frame": "iVBORw0KGgoAAAANS..."  // Base64 của frame đã annotate
    },
    ...
  ]
}

### Hoặc nếu lỗi:
{
  "error": "Không mở được video."
}


## 2. POST /recognize-plate
Nhận diện text từ ảnh biển số.

### Response format:
{
  "text": "61A-66666",                     // Kết quả nhận diện
  "confidence": 0.927,                   // Độ tin cậy (0-1)
  "details": [
    {"text": "61A", "conf": 0.995},      // Chi tiết từng token
    {"text": "66666", "conf": 0.859}
  ]
}

### Hoặc nếu lỗi:
{
  "error": "Decode ảnh lỗi"
}


## 3. POST /detect-plates
Detect xe trong ảnh và nhận diện biển số của từng xe.

### Response format:
{
  "image": "iVBORw0KGgoAAAANS...",       // Base64 encoded annotated image
  "total_vehicles": 3,                   // Số xe phát hiện
  "vehicles": [
    {
      "class": 2,                        // Class ID (2=car, 3=motorcycle, etc.)
      "class_name": "car",               // Tên class
      "confidence": 0.95,                // Độ tin cậy phát hiện
      "bbox": [100, 200, 300, 400],      // [x1, y1, x2, y2]
      "plate": {
        "text": "29B-01786",
        "confidence": 0.98,
        "detected": true
      }
    },
    ...
  ]
}


## 4. POST /detect
Basic object detection (vehicles only).

### Response format:
{
  "detections": [
    {
      "class": 2,
      "confidence": 0.95,
      "xyxy": [100, 200, 300, 400]
    }
  ],
  "image": "iVBORw0KGgoAAAANS..."  // Base64 image
}
"""
