"""
API Response Format Documentation
==================================

## Ghi chú công dụng response
- API hiện yêu cầu 2 header để xác thực theo máy: `X-Machine-Id` và `X-Machine-Key`.
- **Danh bạ khuôn mặt là private theo máy**: `GET /face/persons` chỉ trả danh sách person mà chính máy đó đã đăng ký.
- **Nhận diện là public theo toàn hệ thống**: `POST /face/recognize` sẽ quét và so khớp với toàn bộ person của tất cả máy.
- Chỉ máy đăng ký person mới được phép chỉnh sửa hoặc xóa person đó.
- History và dữ liệu lịch sử vẫn được scope riêng theo máy.
- Biến môi trường `MACHINE_ACCESS_KEYS` dùng để cấu hình mapping JSON giữa `machine_id` và secret, ví dụ: `{"camera-01":"key-abc","camera-02":"key-def"}`.
- Nếu chưa cấu hình `MACHINE_ACCESS_KEYS`, server tự fallback scope theo IP client để tránh trả 503 trong môi trường nội bộ/dev.
- `POST /recognize-video`: Dùng để tổng hợp kết quả nhận diện theo video. `plates` dùng hiển thị danh sách biển số đã gộp; `results` dùng debug theo từng frame; `annotated_frame` dùng hiển thị ảnh đã vẽ box.
- `POST /recognize-plate`: Dùng OCR biển số từ ảnh cắt. `text` là kết quả chính; `confidence` để quyết định tin cậy; `details` để xem token OCR thô.
- `POST /detect-plates`: Dùng nhận diện xe trong ảnh và gắn biển số cho từng xe. `vehicles[].plate` là kết quả theo từng đối tượng.
- Hệ thống đã hỗ trợ tra cứu chủ sở hữu biển số từ danh bạ khuôn mặt theo cơ chế public (cross-machine). Field trả về là `owner` trong các API plate/video.
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
- Các JSON response dưới đây giữ nguyên key cũ để Flutter không bị vỡ; chỉ bổ sung thêm field chi tiết để render UI và debug dễ hơn.

## Cấu trúc dữ liệu chung
- `summary`: khối dữ liệu tóm tắt để hiển thị trên card/list.
- `full_result`: dữ liệu đầy đủ để mở chi tiết màn hình drill-down.
- `representative_image_path`: ảnh đại diện lưu trên server, mở qua static URL.
- Khi fetch trực tiếp ảnh đại diện, client cũng phải gửi cùng header xác thực máy như các API khác.
- `annotated_frame_path`: ảnh frame đã annotate trong video history.
- `embedding_backend`: backend face đang dùng, hiện là `arcface` hoặc `hog`.

## 1. POST /recognize-video
Nhận diện xe và biển số từ video upload.

### Response format:
{
  "video_info": {
    "total_frames": 248,
    "fps": 29.98,
    "width": 480,
    "height": 848,
    "duration": 8.27
  },
  "processing_info": {
    "processed_frames": 9,
    "frame_skip": 30,
    "max_frames": 50,
    "frames_processed": 5
  },
  "plates": [
    {
      "plate": "67B210406",
      "class_name": "motorcycle",
      "first_seen_frame": 0,
      "first_seen_time": 0,
      "last_seen_frame": 0,
      "last_seen_time": 0,
      "count": 1,
      "confidence": 0.4972,
      "owner": {
        "found": false,
        "person_id": "",
        "name": "",
        "person_code": "",
        "info": {},
        "owner_machine_id": "",
        "plate": "67B2-10406",
        "match_type": "none"
      }
    },
    {
      "plate": "77Z020406",
      "class_name": "motorcycle",
      "first_seen_frame": 30,
      "first_seen_time": 1,
      "last_seen_frame": 30,
      "last_seen_time": 1,
      "count": 1,
      "confidence": 0.3973,
      "owner": {
        "found": false,
        "person_id": "",
        "name": "",
        "person_code": "",
        "info": {},
        "owner_machine_id": "",
        "plate": "77Z0-20406",
        "match_type": "none"
      }
    },
    {
      "plate": "67B204061",
      "class_name": "motorcycle",
      "first_seen_frame": 120,
      "first_seen_time": 4,
      "last_seen_frame": 120,
      "last_seen_time": 4,
      "count": 1,
      "confidence": 0.7539,
      "owner": {
        "found": true,
        "person_id": "821cd195-2217-4023-bbbe-13240fd4420d",
        "name": "Nguyễn Thảo Quyên",
        "person_code": "",
        "info": {
          "department": "",
          "role": "",
          "phone": "",
          "address": "",
          "age": "",
          "date_of_birth": "",
          "cccd": "",
          "plate_number": "67B2-84061",
          "vehicle_plates": ""
        },
        "owner_machine_id": "192.168.1.11",
        "plate": "67B2-84061",
        "match_type": "fuzzy_plate"
      }
    }
  ],
  "results": [
    {
      "frame_index": 0,
      "timestamp": 0,
      "vehicles": [
        {
          "class_id": 3,
          "class_name": "motorcycle",
          "confidence": 0.6403,
          "bbox": [
            48.84,
            165.8,
            456.44,
            725.31
          ],
          "plate": {
            "text": "67B210406",
            "confidence": 0.4972,
            "is_valid": true,
            "details": [
              {
                "text": "67-82",
                "conf": 0.6142
              },
              {
                "text": "104061",
                "conf": 0.3801
              }
            ],
            "owner": {
              "found": false,
              "person_id": "",
              "name": "",
              "person_code": "",
              "info": {},
              "owner_machine_id": "",
              "plate": "67B2-10406",
              "match_type": "none"
            }
          }
        }
      ],
      "annotated_frame": "iVBORw0KGgoAAAANS..."  // Base64 của frame đã annotate
    },
    ...
  ]
}

### Ý nghĩa các field chính:
- `video_info`: thông tin đầu vào của video.
- `processing_info`: thông tin xử lý video theo frame.
- `plates`: danh sách biển số đã gộp theo video; mỗi phần tử là một biển số duy nhất.
- `plates[].owner`: thông tin chủ sở hữu của biển số (public cross-machine) nếu tìm thấy mapping.
- `results`: danh sách frame có kết quả; mỗi frame chứa `vehicles` và ảnh đã annotate.
- `vehicles[].class_id`: id class YOLO.
- `vehicles[].class_name`: tên class để hiển thị.
- `vehicles[].confidence`: độ tin cậy phát hiện xe.
- `vehicles[].bbox`: tọa độ box `[x1, y1, x2, y2]`.
- `vehicles[].plate.text`: biển số OCR đã chuẩn hóa.
- `vehicles[].plate.confidence`: confidence OCR của biển số.
- `vehicles[].plate.owner`: thông tin chủ sở hữu tra cứu từ danh bạ khuôn mặt (public cross-machine).
- `vehicles[].plate.details`: từng token OCR để debug.

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
  "owner": {
    "found": true,
    "person_id": "c2f6d4d8-ef20-4c7f-b146-59d27d769f17",
    "name": "Nguyễn Văn A",
    "person_code": "NV001",
    "info": {
      "department": "Công nghệ thông tin"
    },
    "owner_machine_id": "camera-01",
    "plate": "61A-66666",
    "match_type": "exact_plate"
  },
  "details": [
    {"text": "61A", "conf": 0.995},      // Chi tiết từng token
    {"text": "66666", "conf": 0.859}
  ]
}

### Ý nghĩa các field chính:
- `text`: biển số OCR đã chuẩn hóa.
- `confidence`: độ tin cậy tổng của kết quả OCR.
- `owner`: thông tin chủ sở hữu nếu tìm thấy trong danh bạ khuôn mặt.
- `details`: các token OCR thô và confidence từng token.
- Quy tắc format ưu tiên: nếu OCR tách được 2 dòng theo dạng `67B2` + `84061` thì trả `67B2-84061` (moto); nếu chỉ có dạng 1 dòng car thì trả `67B-84061`.

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
      "class": 3,
      "class_name": "motorcycle",
      "confidence": 0.4988,
      "bbox": [
        300.59,
        156.47,
        705.67,
        1149.21
      ],
      "plate": {
        "text": "67B28406",
        "confidence": 0.8013,
        "detected": true,
        "error": null,
        "owner": {
          "found": true,
          "person_id": "821cd195-2217-4023-bbbe-13240fd4420d",
          "name": "Nguyễn Thảo Quyên",
          "person_code": "",
          "info": {
            "department": "",
            "role": "",
            "phone": "",
            "address": "",
            "age": "",
            "date_of_birth": "",
            "cccd": "",
            "plate_number": "67B2-84061",
            "vehicle_plates": ""
          },
          "owner_machine_id": "192.168.1.11",
          "plate": "67B2-84061",
          "match_type": "fuzzy_plate"
        }
      }
    }
  ]
}

### Ý nghĩa các field chính:
- `image`: ảnh annotate dạng base64.
- `total_vehicles`: tổng số xe phát hiện trong ảnh.
- `vehicles[]`: danh sách từng xe, mỗi xe chứa class, confidence, bbox và `plate`.
- `vehicles[].plate.detected`: cho biết có nhận diện được biển số hay không.
- `vehicles[].plate.error`: lỗi OCR nếu không đọc được biển số.
- `vehicles[].plate.owner`: thông tin chủ sở hữu (nếu có mapping biển số trong danh bạ).


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

### Ý nghĩa các field chính:
- `detections`: danh sách object detect thô từ YOLO.
- `image`: ảnh annotate base64.
- `plates`: danh sách biển số hợp lệ được OCR từ các object đã nhận diện.
- `plates[].is_valid`: cho biết biển số đã qua kiểm tra định dạng.


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

  ### Ý nghĩa các field chính:
  - `history`: danh sách lịch sử trả về theo thứ tự mới nhất trước.
  - `stats`: thống kê tổng số entry, timestamp cũ nhất và mới nhất.
  - `limit`, `offset`: tham số phân trang trả lại để Flutter giữ trạng thái list.


## 6. GET /history/{entry_id}
Lấy chi tiết đầy đủ của một entry lịch sử.

### Response format:
{
  "id": "1712721600123",
  "timestamp": 1712721600.123,
  "type": "video_processing",
  "method": "POST",
  "path": "/recognize-video",
  "summary": {...},
  "representative_image_path": "/runs/history_frames/1712721600123_xxx.jpg",
  "plates_found": [...],
  "full_result": {
    "video_info": {
      "total_frames": 150,
      "fps": 25.0,
      "width": 1920,
      "height": 1080,
      "duration": 6.0
    },
    "processing_info": {
      "processed_frames": 20,
      "frame_skip": 30,
      "max_frames": 50,
      "frames_processed": 15
    },
    "plates": [
      {
        "plate": "67B2-84061",
        "class_name": "motorcycle",
        "confidence": 0.92,
        "owner": {
          "found": true,
          "person_id": "c2f6d4d8-ef20-4c7f-b146-59d27d769f17",
          "name": "Nguyễn Văn A",
          "person_code": "NV001",
          "info": {
            "department": "Công nghệ thông tin"
          },
          "owner_machine_id": "camera-01",
          "plate": "67B2-84061",
          "match_type": "exact_plate"
        },
        "first_seen_frame": 0,
        "first_seen_time": 0.0,
        "last_seen_frame": 20,
        "last_seen_time": 0.8,
        "count": 3
      }
    ],
    "results": [
      {
        "frame_index": 0,
        "timestamp": 0.0,
        "vehicles": [
          {
            "class_id": 2,
            "class_name": "car",
            "confidence": 0.95,
            "bbox": [100.5, 200.3, 300.2, 400.8],
            "plate": {
              "text": "61A-66666",
              "confidence": 0.927,
              "owner": {
                "found": true,
                "person_id": "c2f6d4d8-ef20-4c7f-b146-59d27d769f17",
                "name": "Nguyễn Văn A",
                "person_code": "NV001",
                "info": {
                  "department": "Công nghệ thông tin"
                },
                "owner_machine_id": "camera-01",
                "plate": "61A-66666",
                "match_type": "exact_plate"
              },
              "details": [
                {"text": "61A", "conf": 0.995},
                {"text": "66666", "conf": 0.859}
              ]
            }
          }
        ],
        "annotated_frame_path": "/runs/history_frames/1712721600123_xxx.jpg"
      }
    ]
  }
}

### Ví dụ theo loại entry

#### 6.1. Video `/recognize-video`
```json
{
  "id": "1712721600123",
  "timestamp": 1712721600.123,
  "type": "video_processing",
  "method": "POST",
  "path": "/recognize-video",
  "summary": {
    "total_frames": 150,
    "processed_frames": 20,
    "unique_plates": 3,
    "total_detections": 45,
    "processing_time": 2.456
  },
  "representative_image_path": "/runs/history_frames/1712721600123_xxx.jpg",
  "plates_found": ["67B2-84061", "61A-66666"],
  "full_result": {
    "video_info": {
      "total_frames": 150,
      "fps": 25.0,
      "width": 1920,
      "height": 1080,
      "duration": 6.0
    },
    "processing_info": {
      "processed_frames": 20,
      "frame_skip": 30,
      "max_frames": 50,
      "frames_processed": 15
    },
    "plates": [
      {
        "plate": "67B284061",
        "class_name": "motorcycle",
        "confidence": 0.92,
        "owner": {
          "found": true,
          "person_id": "821cd195-2217-4023-bbbe-13240fd4420d",
          "name": "Nguyễn Thảo Quyên",
          "person_code": "",
          "info": {
            "department": "",
            "role": "",
            "phone": "",
            "address": "",
            "age": "",
            "date_of_birth": "",
            "cccd": "",
            "plate_number": "67B2-84061",
            "vehicle_plates": ""
          },
          "owner_machine_id": "192.168.1.11",
          "plate": "67B2-84061",
          "match_type": "fuzzy_plate"
        },
        "first_seen_frame": 0,
        "first_seen_time": 0.0,
        "last_seen_frame": 20,
        "last_seen_time": 0.8,
        "count": 3
      }
    ],
    "results": [
      {
        "frame_index": 0,
        "timestamp": 0.0,
        "vehicles": [
          {
            "class_id": 2,
            "class_name": "car",
            "confidence": 0.95,
            "bbox": [100.5, 200.3, 300.2, 400.8],
            "plate": {
              "text": "61A66666",
              "confidence": 0.927,
              "is_valid": true,
              "owner": {
                "found": true,
                "person_id": "c2f6d4d8-ef20-4c7f-b146-59d27d769f17",
                "name": "Nguyễn Văn A",
                "person_code": "NV001",
                "info": {
                  "department": "Công nghệ thông tin"
                },
                "owner_machine_id": "camera-01",
                "plate": "61A-66666",
                "match_type": "exact_plate"
              },
              "details": [
                {"text": "61A", "conf": 0.995},
                {"text": "66666", "conf": 0.859}
              ]
            }
          }
        ],
        "annotated_frame_path": "/runs/history_frames/1712721600123_xxx.jpg"
      }
    ]
  }
}
```

#### 6.2. Ảnh detect xe `/detect-plates`
```json
{
  "id": "1712721600456",
  "timestamp": 1712721600.456,
  "type": "image_detection",
  "method": "POST",
  "path": "/detect-plates",
  "summary": {
    "total_vehicles": 3,
    "plates_detected": 2,
    "plates_found": ["29B-01786", "61A-66666"]
  },
  "representative_image_path": "/runs/history_frames/1712721600456_xxx.jpg",
  "full_result": {
    "total_vehicles": 3,
    "vehicles": [
      {
        "class": 2,
        "class_name": "car",
        "confidence": 0.95,
        "bbox": [100, 200, 300, 400],
        "plate": {
          "text": "29B01786",
          "confidence": 0.98,
          "detected": true,
          "error": null,
          "owner": {
            "found": true,
            "person_id": "c2f6d4d8-ef20-4c7f-b146-59d27d769f17",
            "name": "Nguyễn Văn A",
            "person_code": "NV001",
            "info": {
              "department": "Công nghệ thông tin"
            },
            "owner_machine_id": "camera-01",
            "plate": "29B-01786",
            "match_type": "exact_plate"
          }
        }
      }
    ],
    "image_path": "/runs/history_frames/1712721600456_xxx.jpg"
  }
}
```

#### 6.3. OCR biển số `/recognize-plate`
```json
{
  "id": "1712721600789",
  "timestamp": 1712721600.789,
  "type": "plate_recognition",
  "method": "POST",
  "path": "/recognize-plate",
  "summary": {
    "plate_text": "61A66666",
    "confidence": 0.927,
    "is_valid": true,
    "owner_found": true
  },
  "full_result": {
    "text": "61A66666",
    "confidence": 0.927,
    "owner": {
      "found": true,
      "person_id": "c2f6d4d8-ef20-4c7f-b146-59d27d769f17",
      "name": "Nguyễn Văn A",
      "person_code": "NV001",
      "info": {
        "department": "Công nghệ thông tin"
      },
      "owner_machine_id": "camera-01",
      "plate": "61A-66666",
      "match_type": "exact_plate"
    },
    "details": [
      {"text": "61A", "conf": 0.995},
      {"text": "66666", "conf": 0.859}
    ]
  }
}
```

#### 6.4. Detect object `/detect`
```json
{
  "id": "1712721600999",
  "timestamp": 1712721600.999,
  "type": "object_detection",
  "method": "POST",
  "path": "/detect",
  "summary": {
    "detections": 5,
    "plates_detected": 1,
    "recognize_plates": true
  },
  "representative_image_path": "/runs/history_frames/1712721600999_xxx.jpg",
  "full_result": {
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
}
```

  #### 6.5. Khuôn mặt `/face/recognize`
  ```json
  {
    "id": "1712721601111",
    "timestamp": 1712721601.111,
    "type": "face_recognition",
    "method": "POST",
    "path": "/face/recognize",
    "summary": {
      "total_faces": 1,
      "is_known": true,
      "match_score": 0.9132,
      "person_name": "Nguyễn Văn A"
    },
    "representative_image_path": "/runs/history_frames/1712721601111_xxx.jpg",
    "full_result": {
      "total_faces": 1,
      "total_matches": 2,
      "top_match_limit": 3,
      "faces": [
        {
          "bbox": [120, 80, 280, 300],
          "is_known": true,
          "match_score": 0.9132,
          "top_match_count": 2,
          "top_matches": [
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
              "owner_machine_id": "camera-01",
              "match_score": 0.9132,
              "is_known": true
            },
            {
              "person_id": "8fd3b1f4-b2c7-4a4e-9b5a-9f2c7f1a9a10",
              "name": "Trần Văn B",
              "person_code": "NV002",
              "info": {},
              "owner_machine_id": "camera-02",
              "match_score": 0.8421,
              "is_known": true
            }
          ],
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
            },
            "owner_machine_id": "camera-01"
          }
        }
      ],
      "threshold": 0.55,
      "image_path": "/runs/history_frames/1712721601111_xxx.jpg"
    }
  }
  ```

#### 6.6. Đăng ký khuôn mặt `/face/register`
### Request (POST)

API này nhận `multipart/form-data` (không nhận raw `application/json` vì có upload ảnh).

#### Form-data gửi lên:
- `file` (bắt buộc): ảnh khuôn mặt.
- `name` (bắt buộc): tên người.
- `person_code` (optional): mã nhân sự.
- `department` (optional): phòng ban.
- `role` (optional): chức vụ.
- `phone` (optional): số điện thoại.
- `address` (optional): địa chỉ.
- `age` (optional): tuổi.
- `date_of_birth` (optional): ngày sinh.
- `cccd` (optional): số CCCD.

#### JSON map tương đương (để frontend model dữ liệu):
```json
{
  "name": "Nguyễn Văn A",
  "person_code": "NV001",
  "department": "Công nghệ thông tin",
  "role": "Lập trình viên",
  "phone": "0901234567",
  "address": "123 Lê Lợi, Quận 1, TP.HCM",
  "age": "31",
  "date_of_birth": "1995-06-12",
  "cccd": "079095001234"
}
```

Lưu ý: JSON trên chỉ là map field logic; khi gọi API thực tế vẫn phải gửi dạng `multipart/form-data` để kèm `file`.

### Response history (`GET /history/{entry_id}`)
```json
{
  "id": "1712721601222",
  "timestamp": 1712721601.222,
  "type": "face_registration",
  "method": "POST",
  "path": "/face/register",
  "summary": {
    "name": "Nguyễn Văn A",
    "person_code": "NV001",
    "registered": true
  },
  "representative_image_path": "/runs/history_frames/1712721601222_xxx.jpg",
  "full_result": {
    "person_id": "c2f6d4d8-ef20-4c7f-b146-59d27d769f17",
    "name": "Nguyễn Văn A",
    "person_code": "NV001",
    "registered": true,
    "bbox": [120, 80, 280, 300],
    "samples": 4,
    "image_path": "/runs/history_frames/1712721601222_xxx.jpg"
  }
}
```

### Ý nghĩa field chính cho entry 6.6:
- `summary.name`: tên hiển thị nhanh trên list lịch sử.
- `summary.person_code`: mã nhân sự hiển thị nhanh.
- `summary.registered`: trạng thái đăng ký thành công/thất bại.
- `representative_image_path`: ảnh đại diện đã lưu trong `runs/history_frames`.
- `full_result.person_id`: id duy nhất của người đã lưu trong face DB.
- `full_result.bbox`: tọa độ khuôn mặt dùng khi đăng ký `[x1, y1, x2, y2]`.
- `full_result.samples`: số vector/embedding đã lưu cho người này.
- `full_result.image_path`: ảnh đã annotate dùng cho màn chi tiết lịch sử.

### Ý nghĩa các field chính:
- `id`: id duy nhất của entry lịch sử.
- `timestamp`: thời điểm tạo entry.
- `type`: loại hành động, ví dụ `video_processing`, `image_detection`, `face_recognition`.
- `method`: HTTP method của request đã tạo history.
- `path`: endpoint gốc đã gọi.
- `summary`: dữ liệu ngắn gọn để hiển thị ở list.
- `representative_image_path`: ảnh đại diện của entry.
- `plates_found`: danh sách biển số đã được chuẩn hóa.
- `full_result`: dữ liệu đầy đủ chi tiết.
- Nếu là face thì `full_result.faces[]` chứa kết quả nhận diện, còn video thì có `video_info`, `processing_info`, `plates`, `results`.

Ghi chú: `GET /history/{entry_id}` trả về toàn bộ metadata của entry, bao gồm `method`, `path`, `representative_image_path`, `summary` và `full_result`.
Trong `full_result`, `annotated_frame` (base64) đã được tối ưu thành `annotated_frame_path` để tránh payload quá lớn.
Mỗi `results[]` vẫn giữ đầy đủ `vehicles[]` và `plate` chi tiết để frontend có thể drill-down.
Các entry do middleware ghi log cũng có `summary` và `full_result` chứa metadata của request như `method`, `path`, `query_params`, `process_time`, `status_code`, `user_agent`, `ip`.
Với entry của face, `full_result` sẽ chứa `faces[]`, `threshold` và `image_path` thay cho `video_info/processing_info`.
Bạn có thể mở trực tiếp ảnh qua URL: `http://<host>:<port>/runs/history_frames/<file>.jpg`.


## 7. GET /history/stats
Lấy thống kê lịch sử.

### Response format:
{
  "total_entries": 150,
  "oldest_timestamp": 1712718000.0,
  "newest_timestamp": 1712721600.123
}

### Ý nghĩa các field chính:
- `total_entries`: tổng số entry trong lịch sử.
- `oldest_timestamp`: thời điểm entry cũ nhất.
- `newest_timestamp`: thời điểm entry mới nhất.

### Ý nghĩa các field chính cho `GET /history/{entry_id}`:
- `method`, `path`: thông tin request đã tạo history.
- `summary`: dữ liệu ngắn gọn để hiển thị ở list lịch sử.
- `representative_image_path`: ảnh đại diện của entry.
- `full_result`: dữ liệu đầy đủ chi tiết.
- Với face thì `full_result.faces[]` chứa kết quả nhận diện, còn video thì có `video_info`, `processing_info`, `plates`, `results`.


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

### Ý nghĩa các field chính:
- `applied_filters`: bộ lọc đang được áp dụng.
- `available_filter_values`: các giá trị gợi ý để render checkbox/filter chip.
- `history`: danh sách entry đã lọc.
- `count`: số lượng entry sau lọc.


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

### Ý nghĩa các field chính:
- `endpoints`: danh sách endpoint đang có trong lịch sử.
- `count`: số lượng endpoint khác nhau.


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

### Ý nghĩa các field chính:
- `message`: thông báo thao tác.
- `endpoints`: danh sách endpoint đã chọn để xóa.
- `deleted_count`: số entry bị xóa thực tế.


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

### Ý nghĩa các field chính:
- `ids`: danh sách id đã tích chọn.
- `deleted_count`: số entry bị xóa.


## 12. DELETE /history/all
Xóa toàn bộ lịch sử.

### Response format:
{
  "message": "Đã xóa toàn bộ lịch sử",
  "deleted_count": 125
}

### Ý nghĩa các field chính:
- `deleted_count`: số lượng entry bị xóa hết.


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
- `plate_number`: biển số chính của người (optional)
- `vehicle_plates`: danh sách biển số bổ sung, ngăn cách bằng dấu `,` hoặc `;` (optional)

### Response format:
{
  "person_id": "c2f6d4d8-ef20-4c7f-b146-59d27d769f17",
  "name": "Nguyễn Văn A",
  "person_code": "NV001",
  "registered": true,
  "bbox": [120, 80, 280, 300],
  "samples": 4,
  "embedding_backend": "arcface",
  "annotated_image": "iVBORw0KGgoAAAANS..."
}

### Ý nghĩa các field chính:
- `person_id`: id duy nhất của người đã đăng ký.
- `name`: tên hiển thị.
- `person_code`: mã nhân sự.
- `registered`: đăng ký thành công hay không.
- `bbox`: khung mặt được dùng khi đăng ký.
- `samples`: số embedding/samples đã lưu.
- `embedding_backend`: backend trích đặc trưng hiện tại.
- `annotated_image`: ảnh đã vẽ box khuôn mặt.
- **Ownership**: Person này sẽ được gắn với `owner_machine_id = <current_machine_id>`, chỉ máy hiện tại mới được sửa/xóa và cũng chỉ máy hiện tại mới thấy person này trong `GET /face/persons`.


## 14. POST /face/recognize
Nhận diện khuôn mặt từ ảnh và trả thông tin người.

**Nhận diện dùng toàn bộ danh bạ hệ thống**: tất cả máy đều có thể nhận diện từ toàn bộ person đã đăng ký trên hệ thống.

### Query params:
- `threshold`: ngưỡng nhận diện (mặc định 0.55)

### Response format:
{
  "total_faces": 1,
  "total_matches": 2,
  "top_match_limit": 3,
  "embedding_backend": "arcface",
  "faces": [
    {
      "bbox": [120, 80, 280, 300],
      "is_known": true,
      "match_score": 0.9132,
      "top_match_count": 2,
      "top_matches": [
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
          "owner_machine_id": "camera-01",
          "match_score": 0.9132,
          "is_known": true
        },
        {
          "person_id": "8fd3b1f4-b2c7-4a4e-9b5a-9f2c7f1a9a10",
          "name": "Trần Văn B",
          "person_code": "NV002",
          "info": {},
          "owner_machine_id": "camera-02",
          "match_score": 0.8421,
          "is_known": true
        },
        {
          "person_id": "1b9e8f6d-0f2c-4b7f-8a2d-7c7a1d2e3f44",
          "name": "Lê Thị C",
          "person_code": "NV003",
          "info": {},
          "owner_machine_id": "camera-03",
          "match_score": 0.7814,
          "is_known": true
        }
      ],
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

### Ý nghĩa các field chính:
- `total_faces`: tổng số khuôn mặt phát hiện được trong ảnh.
- `total_matches`: tổng số candidate match được trả về trong tất cả `faces[]`.
- `top_match_limit`: số lượng tối đa match cho mỗi khuôn mặt (hiện là 3).
- `embedding_backend`: backend face đang dùng.
- `faces[].bbox`: tọa độ khuôn mặt.
- `faces[].is_known`: khuôn mặt có match với danh bạ hay không.
- `faces[].match_score`: điểm khớp.
- `faces[].person`: thông tin người khớp, gồm cả `info` chi tiết, bao gồm cả owner_machine_id nên bạn có thể biết person này do máy nào đăng ký.
- `faces[].top_match_count`: số lượng phần tử thực tế trong `faces[].top_matches`.
- `faces[].top_matches`: danh sách tối đa 3 person có điểm khớp cao nhất, đã sắp xếp giảm dần theo `match_score`.
- `annotated_image`: ảnh kết quả có vẽ bbox và hiển thị đầy đủ tên theo thứ hạng (top 1 -> top 3) cho mỗi khuôn mặt.
- `threshold`: ngưỡng nhận diện đang dùng.


## 15. GET /face/persons
Lấy danh sách người đã đăng ký khuôn mặt của máy hiện tại.

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
      "registration_image_path": "/runs/history_frames/1712721601222_xxx.jpg",
      "created_at": 1712721600.123,
      "owner_machine_id": "camera-01",
      "is_owner": true
    }
  ]
}

### Ý nghĩa các field chính:
- `total_persons`: tổng số người do máy hiện tại đăng ký.
- `persons[]`: danh sách người thuộc máy hiện tại, mỗi người có `person_id`, `name`, `person_code`, `info`, `registration_image_path`, `created_at`, `owner_machine_id` và `is_owner`.
- `registration_image_path`: đường dẫn ảnh đã dùng khi đăng ký để frontend hiển thị avatar/preview.
- `owner_machine_id`: máy nào đã đăng ký person này.
- `is_owner`: luôn `true` cho các item trả về ở endpoint này.
- **Quyền chỉnh sửa/xóa**: Chỉ máy với `is_owner=true` mới được phép cập nhật hoặc xóa person.


## 16. PUT /face/person/{person_id}
Cập nhật thông tin người đã đăng ký khuôn mặt.

**Chỉ người dùng (máy) đã đăng ký person này mới được phép cập nhật.** Nếu máy khác cố gắng cập nhật, sẽ nhận error `Không có quyền sửa hồ sơ này. Chỉ máy đăng ký mới được phép chỉnh sửa.`

### Request form-data:
- `file` (optional): ảnh đăng ký mới (nếu upload ảnh mới thì server tự cập nhật `registration_image_path`).
- `name` (optional): tên người.
- `person_code` (optional): mã nhân sự.
- `department` (optional): phòng ban.
- `role` (optional): chức vụ.
- `phone` (optional): số điện thoại.
- `address` (optional): địa chỉ.
- `age` (optional): tuổi.
- `date_of_birth` (optional): ngày sinh.
- `cccd` (optional): số CCCD.
- `plate_number` (optional): biển số chính.
- `vehicle_plates` (optional): danh sách biển số bổ sung, ngăn cách bằng dấu `,` hoặc `;`.
- `registration_image_path` (optional): đường dẫn ảnh có sẵn nếu không upload file mới.

Lưu ý: endpoint này nhận `multipart/form-data`.

### Response format (success):
```json
{
  "message": "Updated person",
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
    },
    "registration_image_path": "/runs/history_frames/1712721601222_xxx.jpg",
    "created_at": 1712721600.123
  }
}
```

### Response format (permission denied):
```json
{
  "error": "Không có quyền sửa hồ sơ này. Chỉ máy đăng ký mới được phép chỉnh sửa."
}
```

### Ý nghĩa các field chính:
- `name`, `person_code`: thông tin nhận dạng hiển thị trong danh bạ.
- `department`, `role`, `phone`, `address`, `age`, `date_of_birth`, `cccd`: dữ liệu trong `info` của người.
- `registration_image_path`: ảnh đại diện/ảnh đăng ký nếu muốn đổi lại.
- Các field không gửi lên sẽ giữ nguyên giá trị cũ.
- Nếu không phải owner, sẽ nhận lỗi permission.


## 17. DELETE /face/person/{person_id}
Xóa một người khỏi danh bạ khuôn mặt.

**Chỉ người dùng (máy) đã đăng ký person này mới được phép xóa.** Nếu máy khác cố gắng xóa, sẽ nhận error `Không có quyền xóa hồ sơ này. Chỉ máy đăng ký mới được phép xóa.`

### Response format (success):
{
  "message": "Deleted person",
  "person_id": "c2f6d4d8-ef20-4c7f-b146-59d27d769f17"
}

### Response format (permission denied):
{
  "error": "Không có quyền xóa hồ sơ này. Chỉ máy đăng ký mới được phép xóa."
}

### Response format (not found):
{
  "error": "Person not found"
}

### Ý nghĩa các field chính:
- `person_id`: id của người vừa xóa.
- Nếu không phải owner hoặc person không tồn tại, sẽ nhận error.

## Tóm tắt nhanh dữ liệu trả về trong lịch sử
- `GET /history`: trả danh sách entry; mỗi entry có `id`, `timestamp`, `type`, `summary`, `representative_image_path` và có thể có `method`, `path`, `plates_found`, `full_result`.
- `GET /history/{entry_id}`: trả toàn bộ chi tiết 1 entry; với video có `video_info`, `processing_info`, `plates`, `results`; với face có `faces`, `threshold`, `image_path`; với request log có `method`, `path`, `query_params`, `process_time`, `status_code`, `user_agent`, `ip`.
- `GET /history/filter`: trả `applied_filters`, `available_filter_values`, `history`, `count`, `limit`, `offset`.
- `GET /history/endpoints`: trả `endpoints` và `count`.
- `DELETE /history/endpoints`: trả `message`, `endpoints`, `deleted_count`.
- `DELETE /history/entries`: trả `message`, `ids`, `deleted_count`.
- `DELETE /history/all`: trả `message`, `deleted_count`.
"""
