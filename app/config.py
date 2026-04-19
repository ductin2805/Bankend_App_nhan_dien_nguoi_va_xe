"""Configuration và constants cho ứng dụng."""

import json
import os

# Model configuration
MODEL_PATH = "yolov8n.pt"

# Image processing
SUPPORTED_FORMATS = [".jpg", ".jpeg", ".png", ".bmp"]
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

PUBLIC_PATH_PREFIXES = (
	"/",
	"/health",
	"/docs",
	"/redoc",
	"/openapi.json",
	"/chat/gemini",
)


def get_machine_access_keys() -> dict[str, str]:
	"""Đọc mapping machine_id -> secret từ biến môi trường."""
	raw_value = os.getenv("MACHINE_ACCESS_KEYS", "").strip()
	if not raw_value:
		return {}

	try:
		parsed = json.loads(raw_value)
	except Exception:
		return {}

	if not isinstance(parsed, dict):
		return {}

	return {
		str(machine_id).strip(): str(secret).strip()
		for machine_id, secret in parsed.items()
		if str(machine_id).strip() and str(secret).strip()
	}


def is_public_path(path: str) -> bool:
	"""Xác định đường dẫn public không cần machine auth."""
	normalized = (path or "").strip()
	return normalized in PUBLIC_PATH_PREFIXES
