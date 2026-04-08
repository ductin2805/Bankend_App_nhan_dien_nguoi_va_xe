"""Formatter cho biển số Việt Nam - Tối ưu hoá định dạng và validation."""

import re


class VietnamPlateFormatter:
    """Xử lý và định dạng biển số Việt Nam theo chuẩn."""
    
    # Định dạng biển số Việt Nam phổ biến
    # Format 1: 29B-1234 (2 số + 1 chữ + 4 số)
    # Format 2: 29B-12345 (2 số + 1 chữ + 5 số)
    # Format 3: 29AB-1234 (2 số + 2 chữ + 4 số)
    # Format 4: 123B-4567 (3 số + 1 chữ + 4 số)
    # Format 5: 90-B2 (2 số + 1 chữ + 1-2 số - kiểm định)
    
    PATTERNS = [
        (r"^(\d{2})([A-Z])(\d{4})$", lambda m: f"{m.group(1)}{m.group(2)}-{m.group(3)}"),
        (r"^(\d{2})([A-Z])(\d{5})$", lambda m: f"{m.group(1)}{m.group(2)}-{m.group(3)}"),
        (r"^(\d{2})([A-Z]{2})(\d{4})$", lambda m: f"{m.group(1)}{m.group(2)}-{m.group(3)}"),
        (r"^(\d{3})([A-Z])(\d{4})$", lambda m: f"{m.group(1)}{m.group(2)}-{m.group(3)}"),
        (r"^(\d{2})([A-Z])(\d{1,3})$", lambda m: f"{m.group(1)}-{m.group(2)}{m.group(3)}"),
    ]
    
    # Mapping ký tự OCR thường sai
    CHAR_MAPPING = {
        'O': '0',
        'I': '1', 'L': '1',
        'Z': '2',
        'S': '5',
        'G': '6',
        'T': '7'
    }
    
    @staticmethod
    def correct_ocr_text(text: str) -> str:
        """Sửa các ký tự OCR sai thường gặp."""
        if not text:
            return ""
        
        corrected = []
        for ch in text.upper():
            if ch in VietnamPlateFormatter.CHAR_MAPPING:
                corrected.append(VietnamPlateFormatter.CHAR_MAPPING[ch])
            else:
                corrected.append(ch)
        return ''.join(corrected)
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Loại bỏ ký tự không hợp lệ."""
        if not text:
            return ""
        
        text = text.upper()
        text = re.sub(r'[^A-Z0-9]', '', text)
        return text
    
    @staticmethod
    def find_candidates(text: str) -> list:
        """Tìm tất cả candidate biển số hợp lệ trong text."""
        if not text:
            return []
        
        candidates = []
        seen = set()
        
        # Các pattern để tìm kiếm
        search_patterns = [
            r"\d{2}[A-Z]\d{4}",
            r"\d{2}[A-Z]\d{5}",
            r"\d{2}[A-Z]{2}\d{4}",
            r"\d{3}[A-Z]\d{4}",
            r"\d{2}[A-Z]\d{1,3}",
            r"\d{1,3}[A-Z]{1,2}\d{1,3}",
            r"\d{2}[A-Z]\d{5,6}",  # Format mới: 61A99166
        ]
        
        for pattern in search_patterns:
            for match in re.finditer(pattern, text):
                candidate = match.group(0)
                start = match.start()
                if candidate not in seen:
                    seen.add(candidate)
                    candidates.append((candidate, start))

        # Nếu không tìm được candidate rõ ràng, thử tìm trong các window của text
        if not candidates:
            text_len = len(text)
            reverse_map = {
                '0': ['O', 'D'],
                '1': ['I', 'L'],
                '2': ['Z'],
                '5': ['S'],
                '8': ['B'],
                '6': ['G'],
                '7': ['T']
            }
            for length in range(6, min(text_len, 12) + 1):
                for start in range(0, text_len - length + 1):
                    segment = text[start:start + length]
                    for pattern in search_patterns:
                        if re.fullmatch(pattern, segment) and segment not in seen:
                            seen.add(segment)
                            candidates.append((segment, start))
                    for i, ch in enumerate(segment):
                        if ch in reverse_map:
                            for replacement in reverse_map[ch]:
                                variant = segment[:i] + replacement + segment[i + 1:]
                                if variant not in seen:
                                    for pattern in search_patterns:
                                        if re.fullmatch(pattern, variant):
                                            seen.add(variant)
                                            candidates.append((variant, start))
                                            break
        
        return sorted(candidates, key=lambda x: (-len(x[0]), x[1], x[0]))
    
    @staticmethod
    def format_plate(plate_raw: str) -> str:
        """Định dạng biển số theo chuẩn Việt Nam."""
        if not plate_raw:
            return ""
        
        # Loại bỏ ký tự lạ
        plate_clean = VietnamPlateFormatter.clean_text(plate_raw)
        if not plate_clean:
            return ""

        plate_corrected = VietnamPlateFormatter.correct_ocr_text(plate_clean)

        candidates = VietnamPlateFormatter.find_candidates(plate_clean)
        if not candidates:
            candidates = VietnamPlateFormatter.find_candidates(plate_corrected)
        else:
            corrected_candidates = VietnamPlateFormatter.find_candidates(plate_corrected)
            seen = {candidate for candidate, _ in candidates}
            for candidate, start in corrected_candidates:
                if candidate not in seen:
                    seen.add(candidate)
                    candidates.append((candidate, start))

        best_formatted = ""
        best_score = 0
        best_start = len(plate_clean) + 1
        best_length = 0
        for candidate, start in candidates:
            formatted = VietnamPlateFormatter._apply_format(candidate)
            if formatted and VietnamPlateFormatter.validate_format(formatted):
                score = VietnamPlateFormatter._plate_score(formatted)
                candidate_len = len(candidate)
                if (
                    score > best_score or
                    (score == best_score and (start < best_start or (start == best_start and candidate_len > best_length)))
                ):
                    best_score = score
                    best_start = start
                    best_length = candidate_len
                    best_formatted = formatted
        
        if best_formatted:
            return best_formatted
        
        # Nếu chưa có candidate hợp lệ, thử các cách sửa sai khác
        fallback = VietnamPlateFormatter._format_with_ambiguity(plate_clean)
        if fallback:
            return fallback
        
        return ""
    
    @staticmethod
    def _apply_format(candidate: str) -> str:
        if re.fullmatch(r"^(\d{2})([A-Z])(\d{4})$", candidate):
            return f"{candidate[:3]}-{candidate[3:]}"
        elif re.fullmatch(r"^(\d{2})([A-Z])(\d{5})$", candidate):
            return f"{candidate[:3]}-{candidate[3:]}"
        elif re.fullmatch(r"^(\d{2})([A-Z])(\d{6})$", candidate):
            return f"{candidate[:3]}-{candidate[3:]}"
        elif re.fullmatch(r"^(\d{2})([A-Z]{2})(\d{4})$", candidate):
            return f"{candidate[:4]}-{candidate[4:]}"
        elif re.fullmatch(r"^(\d{3})([A-Z])(\d{4})$", candidate):
            return f"{candidate[:4]}-{candidate[4:]}"
        elif re.fullmatch(r"^(\d{2})([A-Z])(\d{1,3})$", candidate):
            return f"{candidate[:2]}-{candidate[2:]}"
        return ""

    @staticmethod
    def _plate_score(formatted: str) -> int:
        if re.fullmatch(r"^\d{2}[A-Z]-\d{6}$", formatted):
            return 110
        if re.fullmatch(r"^\d{2}[A-Z]-\d{5}$", formatted):
            return 100
        if re.fullmatch(r"^\d{2}[A-Z]-\d{4}$", formatted):
            return 90
        if re.fullmatch(r"^\d{2}[A-Z]{2}-\d{4}$", formatted):
            return 95
        if re.fullmatch(r"^\d{3}[A-Z]-\d{4}$", formatted):
            return 90
        if re.fullmatch(r"^\d{2}-[A-Z]\d{1,3}$", formatted):
            return 80
        if re.fullmatch(r"^\d{1,3}-[A-Z]{1,2}\d{1,3}$", formatted):
            return 70
        return 0

    @staticmethod
    def _format_with_ambiguity(text: str) -> str:
        """Thử sửa nhầm lẫn chữ/số trong candidate nếu candidate thô không hợp lệ."""
        if not text:
            return ""

        # Những ký tự dễ nhầm khi ở vị trí chữ cái hay số
        ambiguous_map = {
            '0': ['O', 'D'],
            '1': ['I', 'L'],
            '2': ['Z'],
            '5': ['S'],
            '8': ['B'],
            '6': ['G'],
            '7': ['T']
        }

        def generate_variants(candidate):
            variants = {candidate}
            for i, ch in enumerate(candidate):
                if ch in ambiguous_map:
                    for replacement in ambiguous_map[ch]:
                        variants.add(candidate[:i] + replacement + candidate[i+1:])
            return variants

        candidates = VietnamPlateFormatter.find_candidates(text)
        best_formatted = ""
        best_score = 0
        best_start = len(text) + 1
        best_length = 0
        for candidate, start in candidates:
            for variant in generate_variants(candidate):
                formatted = VietnamPlateFormatter._apply_format(variant)
                if formatted and VietnamPlateFormatter.validate_format(formatted):
                    score = VietnamPlateFormatter._plate_score(formatted)
                    candidate_len = len(candidate)
                    if (
                        score > best_score or
                        (score == best_score and (start < best_start or (start == best_start and candidate_len > best_length)))
                    ):
                        best_score = score
                        best_start = start
                        best_length = candidate_len
                        best_formatted = formatted
        return best_formatted
    
    
    @staticmethod
    def validate_format(plate_formatted: str) -> bool:
        """Kiểm tra xem biển số có format hợp lệ không."""
        if not plate_formatted:
            return False
        
        valid_patterns = [
            r"^\d{2}[A-Z]-\d{4}$",      # 61A-1234
            r"^\d{2}[A-Z]-\d{6}$",      # 61A-123456
            r"^\d{2}[A-Z]-\d{5}$",      # 61A-12345
            r"^\d{2}[A-Z]-\d{4}$",      # 61A-1234
            r"^\d{2}[A-Z]{2}-\d{4}$",   # 29AB-1234
            r"^\d{3}[A-Z]-\d{4}$",      # 123B-4567
            r"^\d{2}-[A-Z]\d{1,3}$",    # 90-B2
            r"^\d{1,3}-[A-Z]{1,2}\d{1,3}$",  # Linh hoạt
        ]
        
        for pattern in valid_patterns:
            if re.fullmatch(pattern, plate_formatted):
                return True
        
        return False
    
    @staticmethod
    def process(raw_ocr_text: str) -> dict:
        """
        Pipeline hoàn chỉnh: OCR text -> biển số format chuẩn.
        
        Args:
            raw_ocr_text: Raw text từ OCR
            
        Returns:
            {
                "text": "29B-1234",
                "is_valid": True,
                "raw": "29B1234",
                "corrected": "29B1234"
            }
        """
        if not raw_ocr_text:
            return {
                "text": "",
                "is_valid": False,
                "raw": "",
                "corrected": ""
            }
        
        raw = VietnamPlateFormatter.clean_text(raw_ocr_text)
        corrected = VietnamPlateFormatter.correct_ocr_text(raw)
        formatted = VietnamPlateFormatter.format_plate(corrected)
        is_valid = VietnamPlateFormatter.validate_format(formatted)
        
        return {
            "text": formatted,
            "is_valid": is_valid,
            "raw": raw,
            "corrected": corrected
        }
