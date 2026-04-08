"""
Test video processing endpoint
"""
import requests
import json

def test_video_endpoint():
    # Test với file video mẫu (nếu có)
    video_path = "test_video.mp4"  # Thay bằng path video thật
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': f}
            params = {'frame_skip': 10, 'max_frames': 5}
            
            response = requests.post(
                'http://localhost:8000/recognize-video',
                files=files,
                params=params
            )
            
            if response.status_code == 200:
                result = response.json()
                print("Video processing result:")
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(f"Error: {response.status_code}")
                print(response.text)
                
    except FileNotFoundError:
        print(f"Video file not found: {video_path}")
        print("Create a test video file or use curl:")
        print("curl -X POST 'http://localhost:8000/recognize-video?frame_skip=10&max_frames=5' -F 'file=@test_video.mp4'")

if __name__ == "__main__":
    test_video_endpoint()
