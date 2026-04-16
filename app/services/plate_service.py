"""Service cho plate (biển số) recognition - EasyOCR với multi-line support."""

import re
import numpy as np
import cv2
from app.utils.plate_formatter import VietnamPlateFormatter


class PlateRecognitionService:
    """Service nhận dạng text từ biển số sử dụng EasyOCR (multi-line friendly)."""
    
    def __init__(self, lang: str = 'en'):
        """
        Khởi tạo PlateRecognitionService.
        
        Args:
            lang: Ngôn ngữ ('en' cho ký tự Latin trong biển số)
        """
        try:
            import easyocr
            self.reader = easyocr.Reader([lang], gpu=False)
        except ModuleNotFoundError:
            print("⚠️ EasyOCR chưa cài. Chạy: pip install easyocr")
            self.reader = None

    @staticmethod
    def _preprocess_plate_image(image: np.ndarray) -> np.ndarray:
        """
        Tiền xử lý tối ưu - cân bằng contrast vs detail preservation.
        
        Optimize: Dùng histogram equalization thay vì binary threshold
        (Binary threshold làm mất grayscale detail quan trọng cho OCR).
        """
        img = image.copy()
        if img is None or img.size == 0:
            return img

        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        h, w = img.shape[:2]
        if w > 0 and h > 0:
            # Upscale để OCR tốt hơn
            scale = max(1.0, 400 / float(w))
            if scale != 1.0:
                new_w = min(800, int(w * scale))
                new_h = min(800, int(h * scale))
                img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # Step 1: Denoise (keep details)
        img = cv2.bilateralFilter(img, 5, 50, 50)
        
        # Step 2: Histogram Equalization (contrast boost without losing detail)
        # CLAHE với clipLimit=1.0 (rất nhẹ) để giữ chi tiết
        clahe = cv2.createCLAHE(clipLimit=1.0, tileGridSize=(4, 4))
        img = clahe.apply(img)
        
        # Bỏ binary thresholding - nó làm mất grayscale information
        # EasyOCR hoạt động tốt hơn với grayscale image
        
        return img
    
    @staticmethod
    def _detect_text_lines(image: np.ndarray) -> list:
        """
        Detect horizontal text lines trong ảnh (cho multi-line plates).
        
        Returns:
            List of [y_start, y_end] tuples cho mỗi dòng phát hiện, hoặc [] nếu không phát hiện
        """
        if image is None or image.size == 0:
            return []
        
        h, w = image.shape[:2]
        
        # Tạo binary image để tìm text
        if len(image.shape) == 3 and image.shape[2] == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Threshold đơn giản
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        # Horizontal morphology để find lines
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (w // 4, 1))
        dilated = cv2.dilate(binary, kernel, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        line_ranges = []
        for contour in contours:
            x, y, cw, ch = cv2.boundingRect(contour)
            if ch > h * 0.1:  # Cao ít nhất 10% ảnh
                line_ranges.append((y, y + ch))
        
        if not line_ranges:
            return []
        
        # Sort by y position
        line_ranges.sort(key=lambda x: x[0])
        
        # Merge overlapping/nearby lines
        merged = []
        for y_start, y_end in line_ranges:
            if merged and y_start < merged[-1][1] + 5:  # Overlap hoặc quá gần
                merged[-1] = (merged[-1][0], max(merged[-1][1], y_end))
            else:
                merged.append((y_start, y_end))
        
        return merged
    
    def recognize_plate(self, image: np.ndarray, confidence_threshold: float = 0.3) -> dict:
        """
        Nhận dạng text từ ảnh biển số (hỗ trợ đa dòng với auto line detection).
        
        Args:
            image: cv2 image array
            confidence_threshold: Ngưỡng confidence tối thiểu
            
        Returns:
            Dict chứa detected text và confidence
        """
        try:
            if self.reader is None:
                return {
                    "text": "",
                    "confidence": 0.0,
                    "error": "EasyOCR chưa cài. Chạy: pip install easyocr"
                }

            processed = self._preprocess_plate_image(image)
            
            # Detect text lines (cho multi-line support)
            lines = self._detect_text_lines(image)
            
            all_texts = []
            all_confidences = []
            
            def _collect_results(ocr_results):
                texts = []
                confs = []
                for detection in ocr_results:
                    if len(detection) < 2:
                        continue
                    text = detection[1]
                    confidence = detection[2] if len(detection) > 2 else 0.95
                    confidence = min(1.0, max(0.0, float(confidence)))
                    if confidence >= confidence_threshold and text.strip():
                        texts.append(text)
                        confs.append(confidence)
                return texts, confs
            
            if lines and len(lines) > 1:
                # Multi-line detected - process each line separately
                for y_start, y_end in lines:
                    line_roi = processed[y_start:y_end, :]
                    if line_roi.size == 0:
                        continue
                    
                    results = self.reader.readtext(
                        line_roi,
                        allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-',
                        detail=1,
                        paragraph=False
                    )
                    texts, confs = _collect_results(results)
                    all_texts.extend(texts)
                    all_confidences.extend(confs)
            else:
                # Single line or line detection failed - use full image
                results = self.reader.readtext(
                    processed,
                    allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-',
                    detail=1,
                    paragraph=False
                )
                texts, confs = _collect_results(results)
                all_texts.extend(texts)
                all_confidences.extend(confs)

                # If we only found one line or short text, try bottom-half fallback
                if len(all_texts) <= 1:
                    h, w = processed.shape[:2]
                    bottom_roi = processed[int(h * 0.45):h, :]
                    if bottom_roi.size > 0:
                        results2 = self.reader.readtext(
                            bottom_roi,
                            allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-',
                            detail=1,
                            paragraph=False
                        )
                        texts2, confs2 = _collect_results(results2)
                        # Append only new bottom-line text if not already present
                        for text, conf in zip(texts2, confs2):
                            if text not in all_texts:
                                all_texts.append(text)
                                all_confidences.append(conf)
            
            # Parse results
            if not all_texts:
                return {
                    "text": "",
                    "confidence": 0.0
                }

            # Deduplicate similar OCR outputs and choose best valid plate candidate
            unique_texts = []
            seen_texts = set()
            for txt in all_texts:
                cleaned = VietnamPlateFormatter.clean_text(txt.upper())
                if cleaned and cleaned not in seen_texts:
                    seen_texts.add(cleaned)
                    unique_texts.append(cleaned)

            combined_text = "".join(unique_texts)
            final_text = ""

            # Ưu tiên ghép biển số 2 dòng kiểu moto: 67B2 + 84061 => 67B2-84061
            header_tokens = []
            number_tokens = []
            for token in unique_texts:
                token_clean = VietnamPlateFormatter.clean_text(token)
                if re.fullmatch(r"\d{2}[A-Z]\d", token_clean):
                    header_tokens.append(token_clean)
                elif re.fullmatch(r"\d{5}", token_clean):
                    number_tokens.append(token_clean)

            if header_tokens and number_tokens:
                two_line_candidate = f"{header_tokens[0]}-{number_tokens[0]}"
                if VietnamPlateFormatter.validate_format(two_line_candidate):
                    final_text = two_line_candidate

            # Fallback pipeline cũ để giữ tương thích
            if not final_text:
                formatted_candidate = VietnamPlateFormatter.format_plate(combined_text)
                if formatted_candidate and VietnamPlateFormatter.validate_format(formatted_candidate):
                    final_text = formatted_candidate
                else:
                    # Try each unique candidate individually
                    for candidate in unique_texts:
                        formatted = VietnamPlateFormatter.format_plate(candidate)
                        if formatted and VietnamPlateFormatter.validate_format(formatted):
                            final_text = formatted
                            break
                    # If still no valid result, try two-line join variants
                    if not final_text and len(unique_texts) > 1:
                        for i in range(len(unique_texts) - 1):
                            combo = unique_texts[i] + unique_texts[i + 1]
                            formatted = VietnamPlateFormatter.format_plate(combo)
                            if formatted and VietnamPlateFormatter.validate_format(formatted):
                                final_text = formatted
                                break
                    if not final_text:
                        final_text = re.sub(r'[^A-Z0-9\-]', '', combined_text)

            avg_confidence = sum(all_confidences) / len(all_confidences)
            is_valid = bool(final_text and VietnamPlateFormatter.validate_format(final_text))
            
            # Trả về text không gạch ngang để dễ so sánh
            text_no_dash = final_text.replace("-", "")
            
            return {
                "text": text_no_dash,
                "confidence": round(avg_confidence, 4),
                "is_valid": is_valid,
                "details": [{"text": txt.upper(), "conf": round(conf, 4)} 
                           for txt, conf in zip(all_texts, all_confidences)]
            }
        
        except Exception as e:
            print(f"Error in recognize_plate: {e}")
            return {
                "text": "",
                "confidence": 0.0,
                "error": str(e)
            }
    
    @staticmethod
    def _parse_ocr_results(ocr_result, confidence_threshold: float) -> dict:
        """
        Parse EasyOCR results thành format đơn giản.
        
        Args:
            ocr_result: Raw result từ EasyOCR
                Format: [[[bbox], text, confidence], ...] hoặc [[[bbox], text], ...]
            confidence_threshold: Ngưỡng confidence
            
        Returns:
            Dict với text và confidence
        """
        if not ocr_result:
            return {
                "text": "",
                "confidence": 0.0
            }
        
        all_texts = []
        all_confidences = []
        
        for detection in ocr_result:
            if not detection or len(detection) < 2:
                continue
            
            # EasyOCR format với detail=1
            # paragraph=False: [[bbox], text, confidence]
            # Tuy nhiên trong một số trường hợp chỉ có [[bbox], text]
            text = detection[1]
            
            # Lấy confidence từ vị trí 2 (nếu có)
            if len(detection) > 2:
                confidence = float(detection[2])
            else:
                # Nếu không có confidence, assume confidence cao (0.95)
                confidence = 0.95
            
            # Clamp confidence
            confidence = min(1.0, max(0.0, confidence))
            
            if confidence >= confidence_threshold and text.strip():
                all_texts.append(text)
                all_confidences.append(confidence)
        
        if not all_texts:
            return {
                "text": "",
                "confidence": 0.0
            }
        
        # Kết hợp text từ các dòng
        final_text = "".join(all_texts).upper()
        # Giữ lại dấu - cho định dạng biển số
        final_text = re.sub(r'[^A-Z0-9\-]', '', final_text)
        
        # Trả về text không gạch ngang để dễ so sánh
        text_no_dash = final_text.replace("-", "")
        
        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        
        return {
            "text": text_no_dash,
            "confidence": round(avg_confidence, 4),
            "details": [{"text": txt.upper(), "conf": round(conf, 4)} 
                       for txt, conf in zip(all_texts, all_confidences)]
        }
    
    def recognize_plate_from_coordinates(self, image: np.ndarray, box_xyxy: list) -> dict:
        """
        Nhận dạng biển số từ ảnh gốc dựa vào tọa độ box.
        
        Args:
            image: cv2 image array gốc
            box_xyxy: [x1, y1, x2, y2] tọa độ box biển số
            
        Returns:
            Dict chứa detected text và confidence
        """
        try:
            x1, y1, x2, y2 = map(int, box_xyxy)
            
            height = y2 - y1
            width = x2 - x1
            
            # Crop vùng biển số trong phần dưới bbox xe
            # Cố gắng lấy đủ hai dòng biển số: lấy phần dưới 45% của bbox và mở rộng ngang
            top = y1 + int(height * 0.45)
            bottom = y2
            left = x1 - int(width * 0.08)
            right = x2 + int(width * 0.08)
            
            left = max(0, left)
            top = max(0, top)
            right = min(image.shape[1], right)
            bottom = min(image.shape[0], bottom)
            
            plate_roi = image[top:bottom, left:right]
            
            if plate_roi.size == 0:
                plate_roi = image[y1:y2, x1:x2]
            
            if plate_roi.size == 0:
                plate_roi = image[y1:y2, x1:x2]
            
            # Recognize text
            result = self.recognize_plate(plate_roi)
            
            # If only top row found, fallback to full vehicle crop and bottom-half crop
            if result.get("text") and len(result.get("text")) <= 4:
                fallback_roi = image[y1:y2, x1:x2]
                fallback_result = self.recognize_plate(fallback_roi)
                if fallback_result.get("text") and len(fallback_result.get("text")) > len(result.get("text")):
                    result = fallback_result
            
            return result
            
            return result
        
        except Exception as e:
            return {
                "text": "",
                "confidence": 0.0,
                "error": str(e)
            }
