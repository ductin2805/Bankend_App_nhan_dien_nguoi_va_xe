"""Utility functions cho xử lý ảnh."""

import numpy as np
import cv2
import base64


def load_image_from_bytes(file_contents: bytes):
    """
    Load ảnh từ bytes.
    
    Args:
        file_contents: Nội dung file dưới dạng bytes
        
    Returns:
        cv2 image array hoặc None nếu lỗi
    """
    nparr = np.frombuffer(file_contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img


def encode_image_to_base64(image: np.ndarray, format: str = '.jpg') -> str:
    """
    Encode ảnh thành base64 string.
    
    Args:
        image: cv2 image array
        format: Định dạng file ('.jpg', '.png', ...)
        
    Returns:
        Base64 encoded string
        
    Raises:
        Exception: Nếu không encode được
    """
    success, buffer = cv2.imencode(format, image)
    
    if not success:
        raise Exception("Lỗi encode ảnh")
    
    img_base64 = base64.b64encode(buffer).decode()
    return img_base64
