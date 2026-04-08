// Flutter Integration Guide
// 
// Cài đặt dependencies trong pubspec.yaml:
// dependencies:
//   http: ^1.1.0
//   image_picker: ^1.0.0
//   dio: ^5.0.0

import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:io';

const String API_URL = "http://localhost:8000";

class PlateRecognitionClient {
  // 1. Recognize plate từ ảnh biển số
  Future<Map<String, dynamic>> recognizePlate(File imageFile) async {
    try {
      var request = http.MultipartRequest(
        'POST',
        Uri.parse('$API_URL/recognize-plate'),
      );
      
      request.files.add(
        await http.MultipartFile.fromPath('file', imageFile.path),
      );
      
      var response = await request.send();
      var responseBody = await response.stream.bytesToString();
      
      return json.decode(responseBody);
      // Response:
      // {
      //   "text": "61A-66666",
      //   "confidence": 0.927,
      //   "details": [...]
      // }
    } catch (e) {
      return {"error": e.toString()};
    }
  }

  // 2. Detect plates từ ảnh xe
  Future<Map<String, dynamic>> detectPlates(File imageFile) async {
    try {
      var request = http.MultipartRequest(
        'POST',
        Uri.parse('$API_URL/detect-plates'),
      );
      
      request.files.add(
        await http.MultipartFile.fromPath('file', imageFile.path),
      );
      
      var response = await request.send();
      var responseBody = await response.stream.bytesToString();
      
      return json.decode(responseBody);
      // Response:
      // {
      //   "image": "base64...",
      //   "total_vehicles": 3,
      //   "vehicles": [
      //     {
      //       "class_name": "car",
      //       "confidence": 0.95,
      //       "plate": {
      //         "text": "29B-01786",
      //         "detected": true
      //       }
      //     }
      //   ]
      // }
    } catch (e) {
      return {"error": e.toString()};
    }
  }

  // 3. Recognize video (upload file video)
  Future<Map<String, dynamic>> recognizeVideo(
    File videoFile, {
    int frameSkip = 10,
    int maxFrames = 20,
  }) async {
    try {
      var request = http.MultipartRequest(
        'POST',
        Uri.parse('$API_URL/recognize-video?frame_skip=$frameSkip&max_frames=$maxFrames'),
      );
      
      request.files.add(
        await http.MultipartFile.fromPath('file', videoFile.path),
      );
      
      var response = await request.send();
      var responseBody = await response.stream.bytesToString();
      
      return json.decode(responseBody);
      // Response:
      // {
      //   "video_info": {
      //     "total_frames": 150,
      //     "fps": 25.0,
      //     "width": 1920,
      //     "height": 1080,
      //     "duration": 6.0
      //   },
      //   "processing_info": {
      //     "processed_frames": 20,
      //     "frame_skip": 10,
      //     "max_frames": 20,
      //     "frames_processed": 15
      //   },
      //   "results": [
      //     {
      //       "frame_index": 0,
      //       "timestamp": 0.0,
      //       "vehicles": [
      //         {
      //           "class_id": 2,
      //           "class_name": "car",
      //           "bbox": [...],
      //           "plate": {
      //             "text": "61A-66666",
      //             "confidence": 0.927
      //           }
      //         }
      //       ],
      //       "annotated_frame": "base64..."
      //     }
      //   ]
      // }
    } catch (e) {
      return {"error": e.toString()};
    }
  }

  // 4. Health check
  Future<bool> checkHealth() async {
    try {
      var response = await http.get(Uri.parse('$API_URL/health'));
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }
}

// === USAGE EXAMPLE ===

void main() async {
  final client = PlateRecognitionClient();
  
  // Check server
  bool isHealthy = await client.checkHealth();
  print("Server healthy: $isHealthy");
  
  // Recognize plate
  // File imageFile = File('/path/to/plate.jpg');
  // var result = await client.recognizePlate(imageFile);
  // print(result);
  // Output: {text: 61A-66666, confidence: 0.927, ...}
  
  // Detect plates in car image
  // File carImage = File('/path/to/car.jpg');
  // var detections = await client.detectPlates(carImage);
  // print(detections["total_vehicles"]); // 1
  // print(detections["vehicles"][0]["plate"]["text"]); // 29B-01786
  
  // Process video
  // File videoFile = File('/path/to/traffic.mp4');
  // var videoResult = await client.recognizeVideo(videoFile);
  // print(videoResult["processed_frames"]); // 20
}
