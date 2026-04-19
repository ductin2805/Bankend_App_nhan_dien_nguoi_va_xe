"""Routes cho AI chat (Gemini)."""

import json
import os
import re
import time
import unicodedata
import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field


router = APIRouter(tags=["chat"])


# In-memory cache: {normalized_question: (expiry_ts, reply_text)}
_CHAT_CACHE: dict[str, tuple[float, str]] = {}
_RULES_CACHE: dict[str, object] = {
    "mtime": None,
    "exact_rules": {},
    "contains_rules": [],
}

_DEFAULT_EXACT_RULES = {
    "ping": "pong",
    "hello": "Xin chao, toi co the ho tro ban ve he thong nhan dien va API.",
    "hi": "Xin chao, toi co the ho tro ban ve he thong nhan dien va API.",
    "help": "Ban co the hoi ve detect, recognize-plate, detect-plates, recognize-video, face va history.",
}

_DEFAULT_CONTAINS_RULES = [
    {
        "keywords": ["header", "x-machine-id", "x-machine-key", "xac thuc", "machine key"],
        "reply": "API yeu cau header X-Machine-Id va X-Machine-Key cho cac route private. Cac route public gom /, /health, /docs, /redoc, /openapi.json, /chat/gemini.",
    },
]


def _normalize_text(text: str) -> str:
    """Chuan hoa input de tang kha nang hit rule/cache (khong phan biet dau)."""
    value = (text or "").strip().lower()
    value = value.replace("đ", "d")
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = re.sub(r"[^a-z0-9\-_/\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _text_tokens(normalized_text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", normalized_text))


def _keyword_hit(keyword: str, normalized_text: str, token_set: set[str]) -> bool:
    """Match keyword voi uu tien giam false-positive cho tu don ngan."""
    if not keyword:
        return False
    if " " in keyword:
        # Cho phep match cum tu khong phu thuoc thu tu: "recognize face" ~ "face recognize".
        phrase_tokens = [tok for tok in re.findall(r"[a-z0-9]+", keyword) if tok]
        if phrase_tokens and all(tok in token_set for tok in phrase_tokens):
            return True
        return keyword in normalized_text
    if "/" in keyword or "-" in keyword:
        return keyword in normalized_text
    if len(keyword) <= 2:
        return keyword in token_set
    return keyword in token_set or (keyword in normalized_text)


def _hard_rule_reply(normalized_text: str) -> str | None:
    """Rule cung cho cac cau hoi don gian/thuong gap."""
    exact_rules, contains_rules = _load_hard_rules()
    if normalized_text in exact_rules:
        return exact_rules[normalized_text]

    token_set = _text_tokens(normalized_text)
    best_reply = None
    best_score: tuple[int, int, int, int] | None = None

    for index, item in enumerate(contains_rules):
        keywords = item.get("keywords", [])
        reply = item.get("reply", "")
        if not keywords or not reply:
            continue

        matched_keywords = [
            keyword for keyword in keywords
            if _keyword_hit(str(keyword), normalized_text, token_set)
        ]
        if not matched_keywords:
            continue

        # Score cao hon khi match nhieu keyword va keyword dai hon.
        match_count = len(matched_keywords)
        total_len = sum(len(k) for k in matched_keywords)
        longest_len = max(len(k) for k in matched_keywords)
        score = (match_count, total_len, longest_len, -index)

        if best_score is None or score > best_score:
            best_score = score
            best_reply = str(reply)

    if best_reply:
        return best_reply

    return None


def _load_hard_rules() -> tuple[dict[str, str], list[dict[str, object]]]:
    """Load rules tu file JSON, cache theo mtime de giam I/O."""
    rules_file = os.getenv(
        "CHAT_RULES_FILE",
        os.path.join(os.path.dirname(__file__), "..", "rules", "chat_rules.json"),
    )
    rules_file = os.path.abspath(rules_file)

    try:
        mtime = os.path.getmtime(rules_file)
    except OSError:
        return _DEFAULT_EXACT_RULES, _DEFAULT_CONTAINS_RULES

    if _RULES_CACHE.get("mtime") == mtime:
        return _RULES_CACHE.get("exact_rules", {}), _RULES_CACHE.get("contains_rules", [])

    try:
        with open(rules_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        exact_rules_raw = data.get("exact_rules", {}) if isinstance(data, dict) else {}
        contains_rules_raw = data.get("contains_rules", []) if isinstance(data, dict) else []

        exact_rules: dict[str, str] = {}
        if isinstance(exact_rules_raw, dict):
            for key, value in exact_rules_raw.items():
                k = _normalize_text(str(key))
                v = str(value).strip()
                if k and v:
                    exact_rules[k] = v

        contains_rules: list[dict[str, object]] = []
        if isinstance(contains_rules_raw, list):
            for item in contains_rules_raw:
                if not isinstance(item, dict):
                    continue
                keywords_raw = item.get("keywords", [])
                reply = str(item.get("reply", "")).strip()
                if not isinstance(keywords_raw, list) or not reply:
                    continue
                keywords = [_normalize_text(str(keyword)) for keyword in keywords_raw if str(keyword).strip()]
                keywords = [keyword for keyword in keywords if keyword]
                # Loai trung, sap xep giam dan theo do dai de uu tien cum tu cu the.
                keywords = sorted(set(keywords), key=len, reverse=True)
                if keywords:
                    contains_rules.append({"keywords": keywords, "reply": reply})

        if not exact_rules and not contains_rules:
            return _DEFAULT_EXACT_RULES, _DEFAULT_CONTAINS_RULES

        _RULES_CACHE["mtime"] = mtime
        _RULES_CACHE["exact_rules"] = exact_rules
        _RULES_CACHE["contains_rules"] = contains_rules
        return exact_rules, contains_rules
    except Exception:
        return _DEFAULT_EXACT_RULES, _DEFAULT_CONTAINS_RULES


def _cache_get(normalized_text: str) -> str | None:
    """Lay cache neu con han."""
    record = _CHAT_CACHE.get(normalized_text)
    if not record:
        return None
    expiry_ts, cached_reply = record
    if time.time() > expiry_ts:
        _CHAT_CACHE.pop(normalized_text, None)
        return None
    return cached_reply


def _cache_set(normalized_text: str, reply: str) -> None:
    """Set cache theo TTL tu env, mac dinh 5 phut."""
    ttl_seconds = int(os.getenv("CHAT_CACHE_TTL_SEC", "300") or "300")
    ttl_seconds = max(10, ttl_seconds)
    _CHAT_CACHE[normalized_text] = (time.time() + ttl_seconds, reply)

    # Don cache nhe de tranh phinh memory.
    max_cache_items = int(os.getenv("CHAT_CACHE_MAX_ITEMS", "1000") or "1000")
    if len(_CHAT_CACHE) <= max_cache_items:
        return
    now_ts = time.time()
    expired_keys = [key for key, (expiry, _) in _CHAT_CACHE.items() if expiry <= now_ts]
    for key in expired_keys:
        _CHAT_CACHE.pop(key, None)
    # Neu van qua lon thi xoa bot theo thu tu chen.
    while len(_CHAT_CACHE) > max_cache_items:
        oldest_key = next(iter(_CHAT_CACHE.keys()))
        _CHAT_CACHE.pop(oldest_key, None)


def _fallback_reply() -> str:
    return "Tam thoi toi khong ket noi duoc AI. Ban vui long thu lai sau it phut."


class GeminiChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Noi dung cau hoi gui den Gemini")


@router.post("/chat/gemini")
async def chat_with_gemini(payload: GeminiChatRequest):
    """Flow: Rule cung -> Cache -> Gemini -> Fallback."""
    normalized_message = _normalize_text(payload.message)

    # 1) Rule cứng
    rule_reply = _hard_rule_reply(normalized_message)
    if rule_reply:
        return {
            "reply": rule_reply,
            "source": "rule",
            "cached": False,
        }

    # 2) Cache
    cached_reply = _cache_get(normalized_message)
    if cached_reply:
        return {
            "reply": cached_reply,
            "source": "cache",
            "cached": True,
        }

    # 3) Gemini
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {
            "reply": _fallback_reply(),
            "source": "fallback",
            "cached": False,
            "error": "Chua cau hinh GEMINI_API_KEY trong environment",
        }

    url = os.getenv(
        "GEMINI_API_URL",
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent",
    ).strip()

    body = {
        "contents": [
            {
                "parts": [
                    {"text": payload.message}
                ]
            }
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": api_key,
    }

    try:
        gemini_timeout = float(os.getenv("GEMINI_TIMEOUT_SEC", "12") or "12")
        gemini_timeout = max(3.0, gemini_timeout)
        async with httpx.AsyncClient(timeout=gemini_timeout) as client:
            response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()

        text = ""
        candidates = data.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if parts:
                text = str(parts[0].get("text", "")).strip()

        if not text:
            return {
                "reply": _fallback_reply(),
                "source": "fallback",
                "cached": False,
                "error": "Gemini khong tra ve noi dung text",
            }

        _cache_set(normalized_message, text)
        return {
            "reply": text,
            "source": "gemini",
            "cached": False,
        }
    except httpx.HTTPStatusError as e:
        # 4) Fallback
        return {
            "reply": _fallback_reply(),
            "source": "fallback",
            "cached": False,
            "error": "Gemini API tra ve loi",
            "status_code": e.response.status_code,
            "details": e.response.text,
        }
    except Exception as e:
        # 4) Fallback
        return {
            "reply": _fallback_reply(),
            "source": "fallback",
            "cached": False,
            "error": str(e),
        }
