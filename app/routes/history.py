"""Routes cho history - xem lịch sử thao tác."""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from app.services.history_service import history_service

router = APIRouter(tags=["history"])


class DeleteEndpointsRequest(BaseModel):
    endpoints: list[str] = Field(default_factory=list, description="Danh sách endpoint cần xóa")


class DeleteEntriesRequest(BaseModel):
    ids: list[str] = Field(default_factory=list, description="Danh sách id hành động cần xóa")


@router.get("/history")
async def get_history(
    limit: int = Query(50, ge=1, le=200, description="Số lượng entry trả về"),
    offset: int = Query(0, ge=0, description="Vị trí bắt đầu (0 = mới nhất)")
):
    """
    Lấy lịch sử thao tác của app.

    Args:
        limit: Số lượng entry tối đa trả về
        offset: Vị trí bắt đầu (0 = entry mới nhất)

    Returns:
        Dict chứa danh sách lịch sử và thống kê
    """
    history = history_service.get_history(limit=limit, offset=offset)
    stats = history_service.get_stats()

    return {
        "history": history,
        "stats": stats,
        "limit": limit,
        "offset": offset
    }


@router.get("/history/filter")
async def filter_history(
    endpoint: str | None = Query(None, description="Lọc theo endpoint, ví dụ /detect-plates"),
    action_type: str | None = Query(None, description="Lọc theo type, ví dụ video_processing"),
    method: str | None = Query(None, description="Lọc theo method, ví dụ post"),
    keyword: str | None = Query(None, description="Lọc theo ký tự/từ khóa: biển số, id, endpoint, type"),
    start_time: float | None = Query(None, description="Mốc thời gian bắt đầu (unix timestamp)"),
    end_time: float | None = Query(None, description="Mốc thời gian kết thúc (unix timestamp)"),
    limit: int = Query(50, ge=1, le=200, description="Số lượng entry trả về"),
    offset: int = Query(0, ge=0, description="Vị trí bắt đầu (0 = mới nhất)")
):
    """Lọc lịch sử theo endpoint/type/method/keyword/time."""
    history = history_service.get_history_filtered(
        endpoint=endpoint,
        action_type=action_type,
        method=method,
        keyword=keyword,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    available = history_service.list_filter_values()
    return {
        "applied_filters": {
            "endpoint": endpoint,
            "action_type": action_type,
            "method": method,
            "keyword": keyword,
            "start_time": start_time,
            "end_time": end_time,
        },
        "available_filter_values": available,
        "history": history,
        "count": len(history),
        "limit": limit,
        "offset": offset
    }


@router.get("/history/endpoints")
async def get_history_endpoints():
    """Lấy danh sách endpoint có trong lịch sử để client hiển thị checkbox."""
    endpoints = history_service.list_endpoints()
    return {
        "endpoints": endpoints,
        "count": len(endpoints)
    }


@router.get("/history/stats")
async def get_history_stats():
    """
    Lấy thống kê lịch sử.

    Returns:
        Dict chứa thống kê lịch sử
    """
    return history_service.get_stats()


@router.get("/history/{entry_id}")
async def get_history_entry(entry_id: str):
    """
    Lấy chi tiết entry lịch sử theo ID.

    Args:
        entry_id: ID của entry lịch sử

    Returns:
        Chi tiết entry với full result nếu có
    """
    entry = history_service.get_entry_by_id(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    return entry


@router.delete("/history/all")
async def delete_all_history():
    """Xóa toàn bộ lịch sử."""
    deleted_count = history_service.clear_history()
    return {
        "message": "Deleted all history entries",
        "deleted_count": deleted_count
    }


@router.delete("/history/endpoints")
async def delete_history_by_endpoints(payload: DeleteEndpointsRequest):
    """Xóa lịch sử theo danh sách endpoint người dùng tick chọn."""
    deleted_count = history_service.delete_by_endpoints(payload.endpoints)
    return {
        "message": "Deleted history entries by selected endpoints",
        "endpoints": payload.endpoints,
        "deleted_count": deleted_count
    }


@router.delete("/history/entries")
async def delete_history_entries(payload: DeleteEntriesRequest):
    """Xóa lịch sử theo danh sách id đã tích chọn."""
    deleted_count = history_service.delete_by_ids(payload.ids)
    return {
        "message": "Deleted selected history entries",
        "ids": payload.ids,
        "deleted_count": deleted_count
    }

    """
    Lấy thống kê lịch sử.

    Returns:
        Dict chứa thống kê lịch sử
    """
    return history_service.get_stats()