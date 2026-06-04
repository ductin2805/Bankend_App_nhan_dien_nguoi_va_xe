"""Service quản lý lịch sử thao tác của app."""

from __future__ import annotations

import json
import time
from typing import Any

from app.services.machine_context import get_current_machine_id
from app.services.postgres_service import postgres_storage
from app.utils.plate_formatter import VietnamPlateFormatter


class HistoryService:
    """Service lưu trữ và quản lý lịch sử thao tác bằng PostgreSQL."""

    def __init__(self, max_entries: int = 1000):
        self.max_entries = max_entries
        self._memory_entries: list[dict[str, Any]] = []
        postgres_storage.init_schema()

    def add_entry(self, entry: dict[str, Any], full_result: dict[str, Any] | None = None, machine_id: str | None = None) -> str:
        """
        Thêm entry mới vào lịch sử.

        Args:
            entry: Dict chứa thông tin entry
            full_result: Kết quả đầy đủ (optional)

        Returns:
            ID của entry
        """
        entry_id = f"{int(time.time() * 1000)}"
        machine_scope = (machine_id or get_current_machine_id() or "default").strip() or "default"
        payload = dict(entry)
        payload["id"] = entry_id
        payload["timestamp"] = time.time()
        payload["machine_id"] = machine_scope

        # Lưu full result nếu có và không quá lớn
        if full_result:
            result_size = len(json.dumps(full_result, default=str).encode("utf-8"))
            if result_size < 5 * 1024 * 1024:  # Max 5MB per result
                payload["full_result"] = full_result
            else:
                payload["full_result"] = {"error": "Result too large to store"}

        if postgres_storage.enabled:
            postgres_storage.execute(
                """
                INSERT INTO history_entries (
                    id, machine_id, timestamp, type, method, path, summary,
                    full_result, representative_image_path, raw_entry
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    machine_id = EXCLUDED.machine_id,
                    timestamp = EXCLUDED.timestamp,
                    type = EXCLUDED.type,
                    method = EXCLUDED.method,
                    path = EXCLUDED.path,
                    summary = EXCLUDED.summary,
                    full_result = EXCLUDED.full_result,
                    representative_image_path = EXCLUDED.representative_image_path,
                    raw_entry = EXCLUDED.raw_entry
                """,
                (
                    payload.get("id"),
                    payload.get("machine_id"),
                    float(payload.get("timestamp", time.time())),
                    payload.get("type"),
                    payload.get("method"),
                    payload.get("path"),
                    postgres_storage.to_json(payload.get("summary", {})),
                    postgres_storage.to_json(payload.get("full_result")),
                    payload.get("representative_image_path", ""),
                    postgres_storage.to_json(payload),
                ),
            )
            self._trim_history_table()
        else:
            self._memory_entries.append(payload)
            self._memory_entries = self._memory_entries[-self.max_entries :]

        return entry_id

    def get_entry_by_id(self, entry_id: str, machine_id: str | None = None) -> dict[str, Any] | None:
        """
        Lấy entry theo ID.

        Args:
            entry_id: ID của entry

        Returns:
            Entry dict hoặc None nếu không tìm thấy
        """
        machine_scope = (machine_id or get_current_machine_id() or "default").strip() or "default"
        rows = self._fetch_machine_entries(machine_scope)
        for entry in rows:
            if entry.get("id") == entry_id:
                return self._normalize_entry(entry)
        return None

    def get_history(self, limit: int = 50, offset: int = 0, machine_id: str | None = None) -> list[dict[str, Any]]:
        """
        Lấy danh sách lịch sử.

        Args:
            limit: Số lượng entry trả về
            offset: Vị trí bắt đầu từ bản ghi mới nhất

        Returns:
            List các entry lịch sử
        """
        machine_scope = (machine_id or get_current_machine_id() or "default").strip() or "default"
        rows = self._fetch_machine_entries(machine_scope)
        if not rows:
            return []
        start = min(offset, len(rows))
        end = min(start + limit, len(rows))
        return [self._normalize_entry(entry) for entry in rows[start:end]]

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
        machine_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Lấy lịch sử có lọc theo endpoint/type/method/keyword/time."""
        machine_scope = (machine_id or get_current_machine_id() or "default").strip() or "default"
        endpoint_filter = (endpoint or "").strip().lower()
        type_filter = (action_type or "").strip().lower()
        method_filter = (method or "").strip().lower()
        keyword_filter = (keyword or "").strip().lower()

        filtered = []
        for entry in self._fetch_machine_entries(machine_scope):
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

        start = min(offset, len(filtered))
        end = min(start + limit, len(filtered))
        return [self._normalize_entry(entry) for entry in filtered[start:end]]

    def list_filter_values(self, machine_id: str | None = None) -> dict[str, list[str]]:
        """Lấy các giá trị lọc hợp lệ để client hiển thị."""
        machine_scope = (machine_id or get_current_machine_id() or "default").strip() or "default"
        endpoints = set()
        action_types = set()
        methods = set()

        for entry in self._fetch_machine_entries(machine_scope):
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

    def filter_history(self, category: str, limit: int = 50, offset: int = 0, machine_id: str | None = None) -> list[dict[str, Any]]:
        """
        Lọc lịch sử theo danh mục.

        Danh mục có thể là `type`, `path` hoặc `method` của entry.
        """
        normalized_category = (category or "").strip().lower()
        if not normalized_category:
            return []

        machine_scope = (machine_id or get_current_machine_id() or "default").strip() or "default"
        filtered = []
        for entry in self._fetch_machine_entries(machine_scope):
            entry_type = str(entry.get("type", "")).lower()
            entry_path = str(entry.get("path", "")).lower()
            entry_method = str(entry.get("method", "")).lower()

            if normalized_category in {entry_type, entry_path, entry_method}:
                filtered.append(entry)

        if not filtered:
            return []

        start = min(offset, len(filtered))
        end = min(start + limit, len(filtered))
        return [self._normalize_entry(entry) for entry in filtered[start:end]]

    def delete_by_category(self, category: str, machine_id: str | None = None) -> int:
        """Xóa các entry theo danh mục và trả về số lượng đã xóa."""
        normalized_category = (category or "").strip().lower()
        if not normalized_category:
            return 0

        machine_scope = (machine_id or get_current_machine_id() or "default").strip() or "default"
        entries = self._fetch_machine_entries(machine_scope)
        ids_to_delete = []
        for entry in entries:
            entry_type = str(entry.get("type", "")).lower()
            entry_path = str(entry.get("path", "")).lower()
            entry_method = str(entry.get("method", "")).lower()
            if normalized_category in {entry_type, entry_path, entry_method}:
                ids_to_delete.append(str(entry.get("id", "")))

        return self.delete_by_ids(ids_to_delete, machine_id=machine_scope)

    @staticmethod
    def _type_to_endpoint(entry_type: str) -> str:
        mapping = {
            "video_processing": "/recognize-video",
            "live_camera_frame": "/recognize-live-frame",
            "image_detection": "/detect-plates",
            "plate_recognition": "/recognize-plate",
            "object_detection": "/detect",
            "face_registration": "/face/register",
            "face_recognition": "/face/recognize",
        }
        return mapping.get(entry_type, "")

    def list_endpoints(self) -> list[str]:
        """Lấy danh sách endpoint đang có trong lịch sử để client hiển thị checkbox."""
        machine_scope = get_current_machine_id() or "default"
        endpoints = set()
        for entry in self._fetch_machine_entries(machine_scope):
            path = str(entry.get("path", "")).strip()
            if path.startswith("/"):
                endpoints.add(path)

            entry_type = str(entry.get("type", "")).strip().lower()
            mapped = self._type_to_endpoint(entry_type)
            if mapped:
                endpoints.add(mapped)

        return sorted(endpoints)

    def delete_by_endpoints(self, endpoints: list[str], machine_id: str | None = None) -> int:
        """Xóa lịch sử theo danh sách endpoint được chọn."""
        machine_scope = (machine_id or get_current_machine_id() or "default").strip() or "default"
        normalized = {str(ep).strip().lower() for ep in endpoints if str(ep).strip()}
        if not normalized:
            return 0

        ids_to_delete = []

        for entry in self._fetch_machine_entries(machine_scope):
            path = str(entry.get("path", "")).strip().lower()
            entry_type = str(entry.get("type", "")).strip().lower()
            mapped_path = self._type_to_endpoint(entry_type).lower()

            if path in normalized or mapped_path in normalized:
                ids_to_delete.append(str(entry.get("id", "")))

        return self.delete_by_ids(ids_to_delete, machine_id=machine_scope)

    def delete_by_ids(self, ids: list[str], machine_id: str | None = None) -> int:
        """Xóa lịch sử theo danh sách id đã tích chọn."""
        machine_scope = (machine_id or get_current_machine_id() or "default").strip() or "default"
        id_set = {str(item).strip() for item in ids if str(item).strip()}
        if not id_set:
            return 0

        if postgres_storage.enabled:
            return postgres_storage.execute(
                "DELETE FROM history_entries WHERE machine_id = %s AND id = ANY(%s)",
                (machine_scope, list(id_set)),
            )

        before = len(self._memory_entries)
        self._memory_entries = [
            item
            for item in self._memory_entries
            if not (self._entry_machine_id(item) == machine_scope and str(item.get("id", "")) in id_set)
        ]
        return max(0, before - len(self._memory_entries))

    def clear_history(self) -> int:
        """Xóa toàn bộ lịch sử và trả về số lượng đã xóa."""
        machine_scope = get_current_machine_id() or "default"
        if postgres_storage.enabled:
            return postgres_storage.execute(
                "DELETE FROM history_entries WHERE machine_id = %s",
                (machine_scope,),
            )

        before = len(self._memory_entries)
        self._memory_entries = [item for item in self._memory_entries if self._entry_machine_id(item) != machine_scope]
        return max(0, before - len(self._memory_entries))

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
    def _extract_representative_path(entry: dict[str, Any]) -> str:
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

    @staticmethod
    def _entry_machine_id(entry: dict[str, Any]) -> str:
        machine_id = str(entry.get("machine_id", "default")).strip()
        return machine_id or "default"

    def _normalize_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Chuẩn hóa entry để response /history nhất quán."""
        normalized = dict(entry)
        normalized.pop("machine_id", None)
        full_result = normalized.get("full_result")
        if isinstance(full_result, dict):
            if not normalized.get("method") and isinstance(full_result.get("method"), str):
                normalized["method"] = full_result.get("method", "")
            if not normalized.get("path") and isinstance(full_result.get("path"), str):
                normalized["path"] = full_result.get("path", "")
        if not normalized.get("method"):
            normalized["method"] = "POST"
        if not normalized.get("path"):
            mapped_path = self._type_to_endpoint(str(normalized.get("type", "")).strip().lower())
            if mapped_path:
                normalized["path"] = mapped_path
        normalized["representative_image_path"] = self._extract_representative_path(normalized)

        def _normalize_plates(values: Any) -> list[str]:
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

    def get_stats(self) -> dict[str, Any]:
        """
        Lấy thống kê lịch sử.

        Returns:
            Dict chứa thống kê
        """
        machine_scope = get_current_machine_id() or "default"
        scoped_history = self._fetch_machine_entries(machine_scope)

        if not scoped_history:
            return {
                "total_entries": 0,
                "oldest_timestamp": None,
                "newest_timestamp": None
            }

        timestamps = [entry["timestamp"] for entry in scoped_history]
        return {
            "total_entries": len(scoped_history),
            "oldest_timestamp": min(timestamps),
            "newest_timestamp": max(timestamps)
        }

    def _fetch_machine_entries(self, machine_scope: str) -> list[dict[str, Any]]:
        if postgres_storage.enabled:
            rows = postgres_storage.fetch_all(
                """
                SELECT raw_entry
                FROM history_entries
                WHERE machine_id = %s
                ORDER BY timestamp DESC
                """,
                (machine_scope,),
            )
            entries = []
            for row in rows:
                raw_entry = row.get("raw_entry") if isinstance(row, dict) else None
                if isinstance(raw_entry, dict):
                    entries.append(raw_entry)
            return entries

        rows = [entry for entry in self._memory_entries if self._entry_machine_id(entry) == machine_scope]
        rows.sort(key=lambda item: float(item.get("timestamp", 0.0)), reverse=True)
        return rows

    def _trim_history_table(self) -> None:
        if not postgres_storage.enabled:
            return

        postgres_storage.execute(
            """
            DELETE FROM history_entries
            WHERE id IN (
                SELECT id
                FROM history_entries
                ORDER BY timestamp DESC
                OFFSET %s
            )
            """,
            (self.max_entries,),
        )


# Global instance
history_service = HistoryService()