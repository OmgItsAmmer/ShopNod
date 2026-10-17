from fastapi import APIRouter

from . import assistant, guardrails, insights, items, offers, onboarding, proposals, settings, stream
from .demo import router as demo_router

router = APIRouter()
for _r in (
    onboarding.router, items.router, guardrails.router, proposals.router, offers.router,
    insights.router, assistant.router, settings.router, stream.router, demo_router,
):
    router.include_router(_r)
