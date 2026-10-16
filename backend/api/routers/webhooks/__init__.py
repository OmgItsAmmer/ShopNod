from fastapi import APIRouter, Request

from shopnod_api.schemas import OkOut
from shopnod_core import billing

router = APIRouter()


@router.post("/stripe", response_model=OkOut)
async def stripe_webhook(request: Request):
    """Verify the signature, then process each Stripe event id only once (replays change nothing)."""
    payload = await request.body()
    event = billing.verify_webhook(payload, request.headers.get("stripe-signature"))
    await billing.handle_event(event)
    return OkOut()
