"""
Hướng dẫn tích hợp Flutter với API
===================================

## I. Chuẩn bị phía Server

1. Kiểm tra server đang chạy:
   - Terminal: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
   - Test: `http://localhost:8000/health` -> {status: ok}

2. Đảm bảo dependencies đã cài:
   - EasyOCR, ultralytics, opencv-python, fastapi, uvicorn
   - Game plan: pip install -r requirements.txt

## II. Chuẩn bị phía Flutter

1. Tạo Flutter project:
   `flutter create plate_recognition_app`

2. Thêm dependencies vào pubspec.yaml:
   ```yaml
   dependencies:
     flutter:
       sdk: flutter
     http: ^1.1.0
     dio: ^5.0.0
     image_picker: ^1.0.0
     cached_network_image: ^3.3.0
     intl: ^0.19.0
   ```

3. Chạy:
   `flutter pub get`

## III. Code Flutter chính

### 1. HTTP Client (lib/services/api_client.dart)
- Copy từ FLUTTER_INTEGRATION_EXAMPLE.dart
- Thay `API_URL = "http://10.0.2.2:8000"` (nếu emulator)
- Hoặc `API_URL = "http://localhost:8000"` (nếu physical device + same network)

### 2. Model classes (lib/models/plate_model.dart)
```dart
class PlateResult {
  final String text;
  final double confidence;
  final List<dynamic> details;

  PlateResult({
    required this.text,
    required this.confidence,
    this.details = const [],
  });

  factory PlateResult.fromJson(Map<String, dynamic> json) {
    return PlateResult(
      text: json['text'] ?? '',
      confidence: (json['confidence'] ?? 0.0).toDouble(),
      details: json['details'] ?? [],
    );
  }
}

class VehicleDetection {
  final String className;
  final double confidence;
  final List<double> bbox;
  final PlateResult plate;

  VehicleDetection({
    required this.className,
    required this.confidence,
    required this.bbox,
    required this.plate,
  });

  factory VehicleDetection.fromJson(Map<String, dynamic> json) {
    return VehicleDetection(
      className: json['class_name'] ?? 'unknown',
      confidence: (json['confidence'] ?? 0.0).toDouble(),
      bbox: List<double>.from(json['bbox'] ?? []),
      plate: PlateResult.fromJson(json['plate'] ?? {}),
    );
  }
}

class VideoResult {
  final Map<String, dynamic> videoInfo;
  final Map<String, dynamic> processingInfo;
  final List<FrameResult> results;

  VideoResult({
    required this.videoInfo,
    required this.processingInfo,
    required this.results,
  });

  factory VideoResult.fromJson(Map<String, dynamic> json) {
    var resultsList = (json['results'] as List? ?? [])
        .map((r) => FrameResult.fromJson(r))
        .toList();
    
    return VideoResult(
      videoInfo: json['video_info'] ?? {},
      processingInfo: json['processing_info'] ?? {},
      results: resultsList,
    );
  }
}

class FrameResult {
  final int frameIndex;
  final double timestamp;
  final List<VehicleDetection> vehicles;
  final String annotatedFrame;

  FrameResult({
    required this.frameIndex,
    required this.timestamp,
    required this.vehicles,
    required this.annotatedFrame,
  });

  factory FrameResult.fromJson(Map<String, dynamic> json) {
    var vehicleList = (json['vehicles'] as List? ?? [])
        .map((v) => VehicleDetection.fromJson(v))
        .toList();
    
    return FrameResult(
      frameIndex: json['frame_index'] ?? 0,
      timestamp: (json['timestamp'] ?? 0.0).toDouble(),
      vehicles: vehicleList,
      annotatedFrame: json['annotated_frame'] ?? '',
    );
  }
}
```

### 3. UI Screen (lib/screens/plate_recognition_screen.dart)
```dart
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'dart:convert';  // For base64Decode
import 'dart:io';
import '../services/api_client.dart';
import '../models/plate_model.dart';

class PlateRecognitionScreen extends StatefulWidget {
  @override
  State<PlateRecognitionScreen> createState() => _PlateRecognitionScreenState();
}

class _PlateRecognitionScreenState extends State<PlateRecognitionScreen> {
  final PlateRecognitionClient _apiClient = PlateRecognitionClient();
  final ImagePicker _imagePicker = ImagePicker();
  
  File? _selectedImage;
  bool _isLoading = false;
  PlateResult? _plateResult;
  DetectPlatesResult? _detectResult;

  Future<void> _pickImage() async {
    final XFile? image = await _imagePicker.pickImage(source: ImageSource.gallery);
    if (image != null) {
      setState(() => _selectedImage = File(image.path));
    }
  }

  Future<void> _recognizePlate() async {
    if (_selectedImage == null) return;
    
    setState(() => _isLoading = true);
    try {
      final result = await _apiClient.recognizePlate(_selectedImage!);
      setState(() {
        _plateResult = PlateResult.fromJson(result);
        _detectResult = null;
      });
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Lỗi: $e')),
      );
    } finally {
      setState(() => _isLoading = false);
    }
  }

  // Video processing
  File? _selectedVideo;
  VideoResult? _videoResult;

  Future<void> _pickVideo() async {
    final XFile? video = await _imagePicker.pickVideo(source: ImageSource.gallery);
    if (video != null) {
      setState(() => _selectedVideo = File(video.path));
    }
  }

  Future<void> _processVideo() async {
    if (_selectedVideo == null) return;
    
    setState(() => _isLoading = true);
    try {
      final result = await _apiClient.recognizeVideo(_selectedVideo!);
      setState(() {
        _videoResult = VideoResult.fromJson(result);
        _plateResult = null;
        _detectResult = null;
      });
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Lỗi: $e')),
      );
    } finally {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Nhận diện Biển Số'),
        elevation: 0,
      ),
      body: SingleChildScrollView(
        child: Padding(
          padding: EdgeInsets.all(16),
          child: Column(
            children: [
              // Image preview
              if (_selectedImage != null)
                Container(
                  width: double.infinity,
                  height: 300,
                  decoration: BoxDecoration(
                    border: Border.all(color: Colors.grey),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Image.file(_selectedImage!, fit: BoxFit.cover),
                )
              else
                Container(
                  width: double.infinity,
                  height: 300,
                  decoration: BoxDecoration(
                    color: Colors.grey[200],
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(Icons.image, size: 80, color: Colors.grey[400]),
                ),
              
              SizedBox(height: 16),
              
              // Pick image button
              ElevatedButton.icon(
                onPressed: _pickImage,
                icon: Icon(Icons.photo),
                label: Text('Chọn ảnh'),
              ),
              
              SizedBox(height: 16),
              
              // Action buttons
              Row(
                children: [
                  Expanded(
                    child: ElevatedButton(
                      onPressed: _isLoading ? null : _recognizePlate,
                      child: _isLoading
                          ? SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Text('Nhận diện biển'),
                    ),
                  ),
                  SizedBox(width: 8),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: _isLoading ? null : _detectPlates,
                      child: Text('Detect xe'),
                    ),
                  ),
                ],
              ),
              
              SizedBox(height: 24),
              
              // Results
              if (_plateResult != null)
                Card(
                  child: Padding(
                    padding: EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Kết quả:',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        SizedBox(height: 8),
                        Text(
                          'Biển số: ${_plateResult!.text}',
                          style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                        ),
                        SizedBox(height: 8),
                        Text(
                          'Độ tin cậy: ${(_plateResult!.confidence * 100).toStringAsFixed(1)}%',
                          style: TextStyle(color: Colors.grey[600]),
                        ),
                      ],
                    ),
                  ),
                ),
              
              // Video processing button
              if (_selectedVideo != null)
                Padding(
                  padding: EdgeInsets.only(bottom: 16),
                  child: ElevatedButton(
                    onPressed: _isLoading ? null : _processVideo,
                    child: Text('Xử lý video'),
                  ),
                ),
              
              SizedBox(height: 24),
              
              // Video results
              if (_videoResult != null)
                Card(
                  child: Padding(
                    padding: EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Kết quả video:',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        SizedBox(height: 8),
                        Text('Video: ${_videoResult!.videoInfo['total_frames']} frames, ${_videoResult!.videoInfo['duration']}s'),
                        Text('Đã xử lý: ${_videoResult!.processingInfo['frames_processed']} frames'),
                        SizedBox(height: 12),
                        ..._videoResult!.results.map((frame) => Padding(
                          padding: EdgeInsets.only(bottom: 16),
                          child: Container(
                            padding: EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              border: Border.all(color: Colors.grey[300]!),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text('Frame ${frame.frameIndex} (${frame.timestamp}s):'),
                                if (frame.annotatedFrame.isNotEmpty)
                                  Container(
                                    height: 200,
                                    margin: EdgeInsets.only(top: 8),
                                    decoration: BoxDecoration(
                                      border: Border.all(color: Colors.grey[300]!),
                                    ),
                                    child: Image.memory(
                                      base64Decode(frame.annotatedFrame),
                                      fit: BoxFit.cover,
                                    ),
                                  ),
                                ...frame.vehicles.map((v) => Padding(
                                  padding: EdgeInsets.only(top: 8),
                                  child: Text('${v.className}: ${v.plate.text}'),
                                )),
                              ],
                            ),
                          ),
                        )),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
```

## IV. IP Address cho emulator/device

- **Android Emulator**: `http://10.0.2.2:8000`
- **iOS Simulator**: `http://localhost:8000`
- **Physical Device (cùng WiFi)**: `http://<computer_ip>:8000`
  - Tìm IP: `ipconfig` (Windows) hoặc `ifconfig` (Mac/Linux)

## V. Testing

1. Kiểm tra health:
   ```bash
   curl http://localhost:8000/health
   # Response: {"status":"ok"}
   ```

2. Test API với Postman:
   - POST http://localhost:8000/recognize-plate
   - File upload: form-data, key="file"

3. Flutter test:
   - Hot reload sau khi chỉnh code
   - Kiểm tra logs: `flutter logs`

## VI. Troubleshooting

- **Connection refused**: Server không chạy, kiểm tra `uvicorn`
- **CORS error**: Thêm CORS vào FastAPI:
  ```python
  from fastapi.middleware.cors import CORSMiddleware
  app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
  )
  ```
- **Timeout**: Tăng request timeout trong Flutter client
- **Large files**: Nén video trước khi gửi

"""
