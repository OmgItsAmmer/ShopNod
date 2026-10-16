"""GET /v1/shop/stream: Server-Sent Events. Messages are {type, data}; heartbeat every 15 s."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from shopnod_core import auth, sse

router = APIRouter()


@router.get("/stream")
async def stream(su: auth.ShopUser = Depends(auth.shop_user_complete)):
    shop = su.shop_required
    return StreamingResponse(
        sse.event_stream(sse.shop_channel(shop.id)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
