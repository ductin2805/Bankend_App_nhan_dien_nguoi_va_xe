"""
API Response Format Documentation
==================================

## Ghi chú công dụng response
- Các key JSON giữ nguyên để tương thích với frontend hiện tại; phần giá trị hiển thị, `message`, `error` và dữ liệu mẫu đã được Việt hoá.
- `POST /recognize-video`: Dùng để tổng hợp kết quả nhận diện theo video. `plates` dùng hiển thị danh sách biển số đã gộp; `results` dùng debug theo từng frame; `annotated_frame` dùng hiển thị ảnh đã vẽ box.
- `POST /recognize-plate`: Dùng OCR biển số từ ảnh cắt. `text` là kết quả chính; `confidence` để quyết định tin cậy; `details` để xem token OCR thô.
- `POST /detect-plates`: Dùng nhận diện xe trong ảnh và gắn biển số cho từng xe. `vehicles[].plate` là kết quả theo từng đối tượng.
- `POST /detect`: Dùng detect object tổng quát; bật `recognize_plates=true` để lấy thêm `plates` hợp lệ.
- `GET /history`: Dùng render màn lịch sử tổng quan có phân trang (`limit`, `offset`) kèm `stats`.
- `GET /history/{entry_id}`: Dùng mở chi tiết 1 hành động cụ thể trong lịch sử (drill-down).
- `GET /history/stats`: Dùng lấy số liệu tổng quan nhanh cho dashboard/tiêu đề màn hình.
- `GET /history/filter`: Dùng lọc danh sách lịch sử theo endpoint/type/method/keyword/thời gian để hỗ trợ tìm kiếm và tích chọn.
- `GET /history/endpoints`: Dùng lấy danh sách endpoint hợp lệ để render checkbox filter/xóa.
- `DELETE /history/endpoints`: Dùng xóa lịch sử theo nhóm endpoint được chọn.
- `DELETE /history/entries`: Dùng xóa trực tiếp các hành động đã tích chọn theo `id`.
- `DELETE /history/all`: Dùng dọn sạch toàn bộ lịch sử.
- `POST /face/register`: Dùng đăng ký hồ sơ khuôn mặt + thông tin người.
- `POST /face/recognize`: Dùng nhận diện khuôn mặt từ ảnh và trả thông tin người khớp.
- `GET /face/persons`: Dùng hiển thị danh bạ người đã đăng ký.
- `DELETE /face/person/{person_id}`: Dùng xóa một hồ sơ người khỏi danh bạ khuôn mặt.

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
    "frame_skip": 30,                     // Khoảng cách giữa các frame xử lý (default hiện tại)
    "max_frames": 50,                     // Giới hạn frame xử lý (default hiện tại)
    "frames_processed": 15                // Số frame có kết quả (có xe)
  },
  "plates": [
    {
      "plate": "67B2-84061",
      "class_name": "motorcycle",
      "confidence": 0.92,               // Độ tin cậy OCR trung bình cho biển số này
      "first_seen_frame": 0,
      "first_seen_time": 0.0,
      "last_seen_frame": 20,
      "last_seen_time": 0.8,
      "count": 3
    },
    {
      "plate": "61A-66666",
      "class_name": "car",
      "confidence": 0.88,
      "first_seen_frame": 10,
      "first_seen_time": 0.4,
      "last_seen_frame": 30,
      "last_seen_time": 1.2,
      "count": 2
    }
  ],
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
        "detected": true,
        "error": null
      }
    },
    ...
  ]
}


## 4. POST /detect
Detect object trong ảnh (có thể bật nhận diện biển số qua `recognize_plates=true`).

### Response format:
{
  "detections": [
    {
      "class": 2,
      "confidence": 0.95,
      "xyxy": [100.5, 200.3, 300.2, 400.8]
    }
  ],
  "image": "iVBORw0KGgoAAAANS...",
  "plates": [
    {
      "text": "61A-66666",
      "confidence": 0.927,
      "is_valid": true
    }
  ]
}


## 5. GET /history
Lấy lịch sử thao tác của app.

### Response format:
{
  "history": [
    {
      "id": "1712721600123",
      "timestamp": 1712721600.123,
      "type": "video_processing",
      "summary": {
        "total_frames": 150,
        "processed_frames": 20,
        "unique_plates": 3,
        "total_detections": 45,
        "processing_time": 2.456
      },
      "representative_image_path": "/runs/history_frames/1712721600123_xxx.jpg",
      "plates_found": ["67B2-84061", "61A-66666", "29B-12345"],
      "full_result": {
        "video_info": {"total_frames": 150, "fps": 25.0, "width": 1920, "height": 1080, "duration": 6.0},
        "processing_info": {"processed_frames": 20, "frame_skip": 30, "max_frames": 50, "frames_processed": 15},
        "plates": [...],
        "results": [...]
      }
    },
    {
      "id": "1712721601456",
      "timestamp": 1712721601.456,
      "method": "POST",
      "path": "/recognize-video",
      "query_params": {
        "frame_skip": "30",
        "max_frames": "50"
      },
      "process_time": 2.456,
      "status_code": 200,
      "user_agent": "PostmanRuntime/7.32.3",
      "ip": "127.0.0.1"
    },
    ...
  ],
  "stats": {
    "total_entries": 150,
    "oldest_timestamp": 1712718000.0,
    "newest_timestamp": 1712721600.123
  },
  "limit": 50,
  "offset": 0
}


## 6. GET /history/{entry_id}
Lấy chi tiết đầy đủ của một entry lịch sử.

### Response format:
{
  "id": "1712721600123",
  "timestamp": 1712721600.123,
  "type": "video_processing",
  "summary": {...},
  "plates_found": [...],
  "full_result": {
    "video_info": {...},
    "processing_info": {...},
    "plates": [...],
    "results": [
      {
        "frame_index": 0,
        "timestamp": 0.0,
        "vehicles": [...],
        "annotated_frame_path": "/runs/history_frames/1712721600123_xxx.jpg"
      }
    ]
  }
}

Ghi chú: trong lịch sử, `annotated_frame` (base64) được tối ưu thành `annotated_frame_path` để tránh payload quá lớn.
Mỗi entry có thể có thêm `representative_image_path` để hiển thị ảnh đại diện cho endpoint.
Ví dụ entry `/detect` sẽ có `type: "object_detection"` và `representative_image_path` trỏ tới ảnh annotate của request đó.
Bạn có thể mở trực tiếp ảnh qua URL: `http://<host>:<port>/runs/history_frames/<file>.jpg`.


## 7. GET /history/stats
Lấy thống kê lịch sử.

### Response format:
{
  "total_entries": 150,
  "oldest_timestamp": 1712718000.0,
  "newest_timestamp": 1712721600.123
}


## 8. GET /history/filter
Lọc lịch sử theo bộ lọc để hiển thị danh sách tích chọn.

### Query params:
- `endpoint`: Ví dụ `/detect-plates`
- `action_type`: Ví dụ `video_processing`
- `method`: Ví dụ `post`
- `keyword`: Từ khóa/ký tự để tìm theo biển số, id, endpoint, type
- `start_time`: Mốc thời gian bắt đầu (unix timestamp)
- `end_time`: Mốc thời gian kết thúc (unix timestamp)
- `limit`: Mặc định 50
- `offset`: Mặc định 0

### Response format:
{
  "applied_filters": {
    "endpoint": "/detect-plates",
    "action_type": "image_detection",
    "method": "post",
    "keyword": "59F2",
    "start_time": 1712721000.0,
    "end_time": 1712723000.0
  },
  "available_filter_values": {
    "endpoints": ["/detect", "/detect-plates", "/recognize-plate", "/recognize-video"],
    "action_types": ["image_detection", "object_detection", "plate_recognition", "video_processing"],
    "methods": ["post"]
  },
  "history": [
    {
      "id": "1712721600123",
      "type": "video_processing",
      "summary": {...}
    }
  ],
  "count": 1,
  "limit": 50,
  "offset": 0
}


## 9. GET /history/endpoints
Lấy danh sách endpoint có trong lịch sử (để hiển thị checkbox lựa chọn xoá).

### Response format:
{
  "endpoints": [
    "/detect",
    "/detect-plates",
    "/recognize-plate",
    "/recognize-video"
  ],
  "count": 4
}


## 10. DELETE /history/endpoints
Xóa lịch sử theo danh sách endpoint đã chọn (checkbox).

### Request body:
{
  "endpoints": ["/detect", "/recognize-video"]
}

### Response format:
{
  "message": "Đã xóa lịch sử theo các endpoint đã chọn",
  "endpoints": ["/detect", "/recognize-video"],
  "deleted_count": 12
}


## 11. DELETE /history/entries
Xóa trực tiếp theo danh sách hành động đã tích chọn (theo `id`).

### Request body:
{
  "ids": ["1712721600123", "1712721601456"]
}

### Response format:
{
  "message": "Đã xóa các mục lịch sử đã chọn",
  "ids": ["1712721600123", "1712721601456"],
  "deleted_count": 12
}


## 12. DELETE /history/all
Xóa toàn bộ lịch sử.

### Response format:
{
  "message": "Đã xóa toàn bộ lịch sử",
  "deleted_count": 125
}


## 13. POST /face/register
Đăng ký khuôn mặt và thông tin người.

### Request form-data:
- `file`: ảnh khuôn mặt
- `name`: tên người
- `person_code`: mã nhân sự (optional)
- `department`: phòng ban (optional)
- `role`: chức vụ (optional)
- `phone`: số điện thoại (optional)
- `address`: địa chỉ (optional)
- `age`: tuổi (optional)
- `date_of_birth`: ngày sinh (optional)
- `cccd`: số CCCD (optional)

### Response format:
{
  "person_id": "c2f6d4d8-ef20-4c7f-b146-59d27d769f17",
  "name": "Nguyễn Văn A",
  "person_code": "NV001",
  "registered": true,
  "bbox": [120, 80, 280, 300],
  "samples": 4,
  "annotated_image": "iVBORw0KGgoAAAANS..."
}


## 14. POST /face/recognize
Nhận diện khuôn mặt từ ảnh và trả thông tin người.

### Query params:
- `threshold`: ngưỡng nhận diện (mặc định 0.55)

### Response format:
{
  "total_faces": 1,
  "faces": [
    {
      "bbox": [120, 80, 280, 300],
      "is_known": true,
      "match_score": 0.9132,
      "person": {
        "person_id": "c2f6d4d8-ef20-4c7f-b146-59d27d769f17",
        "name": "Nguyễn Văn A",
        "person_code": "NV001",
        "info": {
          "department": "Công nghệ thông tin",
          "role": "Lập trình viên",
          "phone": "0901234567",
          "address": "123 Lê Lợi, Quận 1, TP.HCM",
          "age": "31",
          "date_of_birth": "1995-06-12",
          "cccd": "079095001234"
        }
      }
    }
  ],
  "annotated_image": "iVBORw0KGgoAAAANS...",
  "threshold": 0.55
}


## 15. GET /face/persons
Lấy danh sách người đã đăng ký khuôn mặt.

### Response format:
{
  "total_persons": 1,
  "persons": [
    {
      "person_id": "c2f6d4d8-ef20-4c7f-b146-59d27d769f17",
      "name": "Nguyễn Văn A",
      "person_code": "NV001",
      "info": {
        "department": "Công nghệ thông tin",
        "role": "Lập trình viên",
        "phone": "0901234567",
        "address": "123 Lê Lợi, Quận 1, TP.HCM",
        "age": "31",
        "date_of_birth": "1995-06-12",
        "cccd": "079095001234"
      },
      "created_at": 1712721600.123
    }
  ]
}


## 16. DELETE /face/person/{person_id}
Xóa một người khỏi danh bạ khuôn mặt.

### Response format:
{
  "message": "Đã xóa người khỏi danh bạ",
  "person_id": "c2f6d4d8-ef20-4c7f-b146-59d27d769f17"
}
"""
