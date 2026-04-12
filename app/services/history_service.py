"""Service quản lý lịch sử thao tác của app."""

import time
import json
import os
from typing import List, Dict, Any
from collections import deque
from app.utils.plate_formatter import VietnamPlateFormatter


class HistoryService:
    """Service lưu trữ và quản lý lịch sử thao tác."""

    def __init__(self, max_entries: int = 1000, save_to_file: bool = True, file_path: str = "history.json"):
        """
        Khởi tạo HistoryService.

        Args:
            max_entries: Số lượng entry tối đa lưu trữ
            save_to_file: Có lưu vào file không
            file_path: Đường dẫn file lưu trữ
        """
        self.history: deque = deque(maxlen=max_entries)
        self.max_entries = max_entries
        self.save_to_file = save_to_file
        self.file_path = file_path
        
        # Load từ file nếu có
        if save_to_file and os.path.exists(file_path):
            self._load_from_file()

    def add_entry(self, entry: Dict[str, Any], full_result: Dict[str, Any] = None) -> str:
        """
        Thêm entry mới vào lịch sử.

        Args:
            entry: Dict chứa thông tin entry
            full_result: Kết quả đầy đủ (optional)

        Returns:
            ID của entry
        """
        entry_id = f"{int(time.time() * 1000)}"
        entry['id'] = entry_id
        entry['timestamp'] = time.time()
        
        # Lưu full result nếu có và không quá lớn
        if full_result:
            result_size = len(json.dumps(full_result, default=str).encode('utf-8'))
            if result_size < 5 * 1024 * 1024:  # Max 5MB per result
                entry['full_result'] = full_result
            else:
                entry['full_result'] = {"error": "Result too large to store"}
        
        self.history.append(entry)
        
        # Lưu vào file nếu enabled
        if self.save_to_file:
            self._save_to_file()
        
        return entry_id

    def get_entry_by_id(self, entry_id: str) -> Dict[str, Any]:
        """
        Lấy entry theo ID.

        Args:
            entry_id: ID của entry

        Returns:
            Entry dict hoặc None nếu không tìm thấy
        """
        for entry in self.history:
            if entry.get('id') == entry_id:
                return self._normalize_entry(entry)
        return None

    def get_history(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Lấy danh sách lịch sử.

        Args:
            limit: Số lượng entry trả về
            offset: Vị trí bắt đầu từ bản ghi mới nhất

        Returns:
            List các entry lịch sử
        """
        history_list = list(self.history)
        if not history_list:
            return []

        # Trả về theo thứ tự mới nhất trước
        history_list.reverse()
        start = min(offset, len(history_list))
        end = min(start + limit, len(history_list))
        return [self._normalize_entry(entry) for entry in history_list[start:end]]

    def get_history_filtered(
        self,
        endpoint: str | None = None,
        action_type: str | None = None,
        method: str | None = None,
        keyword: str | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Lấy lịch sử có lọc theo endpoint/type/method/keyword/time."""
        endpoint_filter = (endpoint or "").strip().lower()
        type_filter = (action_type or "").strip().lower()
        method_filter = (method or "").strip().lower()
        keyword_filter = (keyword or "").strip().lower()

        filtered = []
        for entry in self.history:
            entry_type = str(entry.get("type", "")).strip().lower()
            entry_method = str(entry.get("method", "")).strip().lower()
            entry_path = str(entry.get("path", "")).strip().lower()
            mapped_path = self._type_to_endpoint(entry_type).lower()
            entry_endpoint = entry_path or mapped_path
            entry_ts = entry.get("timestamp")

            if endpoint_filter and entry_endpoint != endpoint_filter:
                continue
            if type_filter and entry_type != type_filter:
                continue
            if method_filter and entry_method != method_filter:
                continue
            if start_time is not None:
                try:
                    if float(entry_ts or 0) < float(start_time):
                        continue
                except Exception:
                    continue
            if end_time is not None:
                try:
                    if float(entry_ts or 0) > float(end_time):
                        continue
                except Exception:
                    continue

            if keyword_filter:
                raw_plates = []
                summary = entry.get("summary")
                if isinstance(summary, dict):
                    summary_plates = summary.get("plates_found")
                    if isinstance(summary_plates, list):
                        raw_plates.extend([str(p) for p in summary_plates])

                top_level_plates = entry.get("plates_found")
                if isinstance(top_level_plates, list):
                    raw_plates.extend([str(p) for p in top_level_plates])

                normalized_plates = []
                for value in raw_plates:
                    formatted = VietnamPlateFormatter.format_plate(value)
                    if formatted and VietnamPlateFormatter.validate_format(formatted):
                        normalized_plates.append(formatted.lower())

                searchable = " ".join(
                    [
                        str(entry.get("id", "")).lower(),
                        entry_type,
                        entry_method,
                        entry_endpoint,
                        " ".join(normalized_plates),
                    ]
                )
                if keyword_filter not in searchable:
                    continue
            filtered.append(entry)

        if not filtered:
            return []

        filtered.reverse()
        start = min(offset, len(filtered))
        end = min(start + limit, len(filtered))
        return [self._normalize_entry(entry) for entry in filtered[start:end]]

    def list_filter_values(self) -> Dict[str, List[str]]:
        """Lấy các giá trị lọc hợp lệ để client hiển thị."""
        endpoints = set()
        action_types = set()
        methods = set()

        for entry in self.history:
            entry_type = str(entry.get("type", "")).strip().lower()
            entry_method = str(entry.get("method", "")).strip().lower()
            entry_path = str(entry.get("path", "")).strip()

            if entry_type:
                action_types.add(entry_type)
                mapped = self._type_to_endpoint(entry_type)
                if mapped:
                    endpoints.add(mapped)

            if entry_method:
                methods.add(entry_method)

            if entry_path.startswith("/"):
                endpoints.add(entry_path)

        return {
            "endpoints": sorted(endpoints),
            "action_types": sorted(action_types),
            "methods": sorted(methods),
        }

    def filter_history(self, category: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Lọc lịch sử theo danh mục.

        Danh mục có thể là `type`, `path` hoặc `method` của entry.
        """
        normalized_category = (category or "").strip().lower()
        if not normalized_category:
            return []

        filtered = []
        for entry in self.history:
            entry_type = str(entry.get("type", "")).lower()
            entry_path = str(entry.get("path", "")).lower()
            entry_method = str(entry.get("method", "")).lower()

            if normalized_category in {entry_type, entry_path, entry_method}:
                filtered.append(entry)

        if not filtered:
            return []

        filtered.reverse()
        start = min(offset, len(filtered))
        end = min(start + limit, len(filtered))
        return [self._normalize_entry(entry) for entry in filtered[start:end]]

    def delete_by_category(self, category: str) -> int:
        """Xóa các entry theo danh mục và trả về số lượng đã xóa."""
        normalized_category = (category or "").strip().lower()
        if not normalized_category:
            return 0

        remaining = []
        deleted_count = 0
        for entry in self.history:
            entry_type = str(entry.get("type", "")).lower()
            entry_path = str(entry.get("path", "")).lower()
            entry_method = str(entry.get("method", "")).lower()

            if normalized_category in {entry_type, entry_path, entry_method}:
                deleted_count += 1
            else:
                remaining.append(entry)

        if deleted_count > 0:
            self.history = deque(remaining, maxlen=self.max_entries)
            if self.save_to_file:
                self._save_to_file()

        return deleted_count

    @staticmethod
    def _type_to_endpoint(entry_type: str) -> str:
        mapping = {
            "video_processing": "/recognize-video",
            "image_detection": "/detect-plates",
            "plate_recognition": "/recognize-plate",
            "object_detection": "/detect",
            "face_registration": "/face/register",
            "face_recognition": "/face/recognize",
        }
        return mapping.get(entry_type, "")

    def list_endpoints(self) -> List[str]:
        """Lấy danh sách endpoint đang có trong lịch sử để client hiển thị checkbox."""
        endpoints = set()
        for entry in self.history:
            path = str(entry.get("path", "")).strip()
            if path.startswith("/"):
                endpoints.add(path)

            entry_type = str(entry.get("type", "")).strip().lower()
            mapped = self._type_to_endpoint(entry_type)
            if mapped:
                endpoints.add(mapped)

        return sorted(endpoints)

    def delete_by_endpoints(self, endpoints: List[str]) -> int:
        """Xóa lịch sử theo danh sách endpoint được chọn."""
        normalized = {str(ep).strip().lower() for ep in endpoints if str(ep).strip()}
        if not normalized:
            return 0

        remaining = []
        deleted_count = 0

        for entry in self.history:
            path = str(entry.get("path", "")).strip().lower()
            entry_type = str(entry.get("type", "")).strip().lower()
            mapped_path = self._type_to_endpoint(entry_type).lower()

            if path in normalized or mapped_path in normalized:
                deleted_count += 1
            else:
                remaining.append(entry)

        if deleted_count > 0:
            self.history = deque(remaining, maxlen=self.max_entries)
            if self.save_to_file:
                self._save_to_file()

        return deleted_count

    def delete_by_ids(self, ids: List[str]) -> int:
        """Xóa lịch sử theo danh sách id đã tích chọn."""
        id_set = {str(item).strip() for item in ids if str(item).strip()}
        if not id_set:
            return 0

        remaining = []
        deleted_count = 0
        for entry in self.history:
            if str(entry.get("id", "")) in id_set:
                deleted_count += 1
            else:
                remaining.append(entry)

        if deleted_count > 0:
            self.history = deque(remaining, maxlen=self.max_entries)
            if self.save_to_file:
                self._save_to_file()

        return deleted_count

    def clear_history(self) -> int:
        """Xóa toàn bộ lịch sử và trả về số lượng đã xóa."""
        deleted_count = len(self.history)
        self.history.clear()
        if self.save_to_file:
            self._save_to_file()
        return deleted_count

    @staticmethod
    def _to_public_path(path: str) -> str:
        """Chuẩn hóa path file thành URL path có thể truy cập qua static route."""
        if not path:
            return ""
        normalized = path.replace("\\", "/")
        if normalized.startswith("/runs/"):
            return normalized
        if normalized.startswith("runs/"):
            return f"/{normalized}"
        return normalized

    @staticmethod
    def _extract_representative_path(entry: Dict[str, Any]) -> str:
        """Lấy đường dẫn ảnh đại diện từ entry nếu có."""
        if entry.get("representative_image_path"):
            return HistoryService._to_public_path(entry.get("representative_image_path", ""))

        full_result = entry.get("full_result")
        if isinstance(full_result, dict):
            image_path = full_result.get("image_path")
            if image_path:
                return HistoryService._to_public_path(image_path)

            results = full_result.get("results")
            if isinstance(results, list):
                for item in results:
                    if isinstance(item, dict) and item.get("annotated_frame_path"):
                        return HistoryService._to_public_path(item.get("annotated_frame_path", ""))

        return ""

    def _normalize_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Chuẩn hóa entry để response /history nhất quán."""
        normalized = dict(entry)
        normalized["representative_image_path"] = self._extract_representative_path(normalized)

        def _normalize_plates(values: Any) -> List[str]:
            if not isinstance(values, list):
                return []
            output = []
            seen = set()
            for value in values:
                if not isinstance(value, str):
                    continue
                formatted = VietnamPlateFormatter.format_plate(value)
                if formatted and VietnamPlateFormatter.validate_format(formatted) and formatted not in seen:
                    seen.add(formatted)
                    output.append(formatted)
            return output

        if "plates_found" in normalized:
            normalized["plates_found"] = _normalize_plates(normalized.get("plates_found"))

        summary = normalized.get("summary")
        if isinstance(summary, dict) and "plates_found" in summary:
            summary = dict(summary)
            summary["plates_found"] = _normalize_plates(summary.get("plates_found"))
            normalized["summary"] = summary

        full_result = normalized.get("full_result")
        if isinstance(full_result, dict):
            image_path = full_result.get("image_path")
            if isinstance(image_path, str):
                full_result["image_path"] = self._to_public_path(image_path)

            results = full_result.get("results")
            if isinstance(results, list):
                for item in results:
                    if isinstance(item, dict) and isinstance(item.get("annotated_frame_path"), str):
                        item["annotated_frame_path"] = self._to_public_path(item.get("annotated_frame_path", ""))

        return normalized

    def get_stats(self) -> Dict[str, Any]:
        """
        Lấy thống kê lịch sử.

        Returns:
            Dict chứa thống kê
        """
        if not self.history:
            return {
                "total_entries": 0,
                "oldest_timestamp": None,
                "newest_timestamp": None
            }

        timestamps = [entry['timestamp'] for entry in self.history]
        return {
            "total_entries": len(self.history),
            "oldest_timestamp": min(timestamps),
            "newest_timestamp": max(timestamps)
        }

    def _save_to_file(self) -> None:
        """Lưu lịch sử vào file JSON."""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(list(self.history), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving history to file: {e}")

    def _load_from_file(self) -> None:
        """Tải lịch sử từ file JSON."""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Chỉ load số lượng tối đa
                for entry in data[-self.max_entries:]:
                    self.history.append(entry)
        except Exception as e:
            print(f"Error loading history from file: {e}")


# Global instance
history_service = HistoryService()