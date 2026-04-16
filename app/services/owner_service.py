"""Service tra cứu chủ sở hữu biển số từ danh bạ khuôn mặt (public toàn hệ thống)."""

import json
import os
from typing import Any

from app.utils.plate_formatter import VietnamPlateFormatter


class OwnerLookupService:
    """Tra cứu owner theo biển số từ face_db.json."""

    def __init__(self, face_db_path: str = "runs/face_db.json"):
        self.face_db_path = face_db_path

    def _load_face_db(self) -> dict[str, Any]:
        if not os.path.exists(self.face_db_path):
            return {"persons": []}
        try:
            with open(self.face_db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"persons": []}
            if not isinstance(data.get("persons"), list):
                data["persons"] = []
            return data
        except Exception:
            return {"persons": []}

    @staticmethod
    def _extract_plate_candidates(info: dict[str, Any]) -> list[str]:
        """Lấy các trường biển số có thể có trong info."""
        if not isinstance(info, dict):
            return []

        candidates: list[str] = []
        plate_keys = [
            "plate",
            "plate_number",
            "license_plate",
            "vehicle_plate",
            "car_plate",
            "bike_plate",
        ]
        list_keys = [
            "plates",
            "plate_numbers",
            "vehicle_plates",
            "license_plates",
        ]

        for key in plate_keys:
            value = info.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())

        for key in list_keys:
            value = info.get(key)
            if isinstance(value, str) and value.strip():
                # Hỗ trợ chuỗi csv/semicolon/newline
                chunks = [chunk.strip() for chunk in value.replace(";", ",").replace("\n", ",").split(",")]
                candidates.extend([chunk for chunk in chunks if chunk])
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item.strip():
                        candidates.append(item.strip())

        return candidates

    @staticmethod
    def _normalize_plate(plate_text: str) -> str:
        if not plate_text:
            return ""
        formatted = VietnamPlateFormatter.format_plate(plate_text)
        if formatted:
            return formatted
        return VietnamPlateFormatter.clean_text(plate_text)

    @staticmethod
    def _loose_plate(plate_text: str) -> str:
        """Chuẩn hóa so khớp mềm: bỏ dấu '-' và ký tự không phải chữ/số."""
        return VietnamPlateFormatter.clean_text(plate_text)

    @staticmethod
    def _head_token(loose_plate: str) -> str:
        """Đầu biển thường ổn định (ví dụ 67B hoặc 51H)."""
        return loose_plate[:3] if len(loose_plate) >= 3 else loose_plate

    @staticmethod
    def _common_prefix_len(a: str, b: str) -> int:
        n = min(len(a), len(b))
        for i in range(n):
            if a[i] != b[i]:
                return i
        return n

    @staticmethod
    def _levenshtein(a: str, b: str) -> int:
        """Khoảng cách chỉnh sửa tối thiểu, dùng cho fuzzy match biển số."""
        if a == b:
            return 0
        if not a:
            return len(b)
        if not b:
            return len(a)

        prev = list(range(len(b) + 1))
        for i, ch_a in enumerate(a, start=1):
            curr = [i]
            for j, ch_b in enumerate(b, start=1):
                ins = curr[j - 1] + 1
                delete = prev[j] + 1
                replace = prev[j - 1] + (0 if ch_a == ch_b else 1)
                curr.append(min(ins, delete, replace))
            prev = curr
        return prev[-1]

    def find_owner_by_plate(self, plate_text: str) -> dict[str, Any] | None:
        """Tìm owner theo biển số. Public: scan toàn bộ danh bạ, không scope theo machine."""
        normalized_target = self._normalize_plate(plate_text)
        loose_target = self._loose_plate(normalized_target or plate_text)
        if not loose_target:
            return {
                "found": False,
                "person_id": "",
                "name": "",
                "person_code": "",
                "info": {},
                "owner_machine_id": "",
                "plate": "",
                "match_type": "none",
            }

        data = self._load_face_db()
        best_fuzzy: dict[str, Any] | None = None
        best_score: tuple[int, int, int] | None = None

        for person in data.get("persons", []):
            info = person.get("info", {}) if isinstance(person, dict) else {}
            owner_machine_id = (person.get("owner_machine_id") or person.get("machine_id") or "default") if isinstance(person, dict) else "default"
            candidates = self._extract_plate_candidates(info)
            for candidate in candidates:
                normalized_candidate = self._normalize_plate(candidate)
                loose_candidate = self._loose_plate(normalized_candidate)
                if not normalized_candidate or not loose_candidate:
                    continue

                # Exact ưu tiên cao nhất
                if normalized_candidate == normalized_target or loose_candidate == loose_target:
                    return {
                        "found": True,
                        "person_id": person.get("person_id", ""),
                        "name": person.get("name", ""),
                        "person_code": person.get("person_code", ""),
                        "info": info,
                        "owner_machine_id": owner_machine_id,
                        "plate": normalized_candidate,
                        "match_type": "exact_plate",
                    }

                # Fuzzy match: chỉ khi đủ dài và cùng đầu biển để tránh false positive.
                if len(loose_target) < 7 or len(loose_candidate) < 7:
                    continue
                if self._head_token(loose_target) != self._head_token(loose_candidate):
                    continue

                contains_match = (
                    loose_target in loose_candidate or
                    loose_candidate in loose_target
                ) and abs(len(loose_target) - len(loose_candidate)) <= 1
                edit_distance = self._levenshtein(loose_target, loose_candidate)

                if not (contains_match or edit_distance <= 1):
                    continue

                # Ưu tiên: chứa nhau (thiếu/thừa 1 ký tự) > distance nhỏ > prefix dài.
                quality = 2 if contains_match else 1
                prefix_len = self._common_prefix_len(loose_target, loose_candidate)
                current_score = (quality, prefix_len, -edit_distance)

                if best_score is None or current_score > best_score:
                    best_score = current_score
                    best_fuzzy = {
                        "found": True,
                        "person_id": person.get("person_id", ""),
                        "name": person.get("name", ""),
                        "person_code": person.get("person_code", ""),
                        "info": info,
                        "owner_machine_id": owner_machine_id,
                        "plate": normalized_candidate,
                        "match_type": "fuzzy_plate",
                    }

        if best_fuzzy is not None:
            return best_fuzzy

        return {
            "found": False,
            "person_id": "",
            "name": "",
            "person_code": "",
            "info": {},
            "owner_machine_id": "",
            "plate": normalized_target or loose_target,
            "match_type": "none",
        }


owner_lookup_service = OwnerLookupService()
