"""Seed: category templates, the Demo Market, 5 demo shops with items and guardrails, and 40 simulated shoppers.
Idempotent.

    python seed/seed.py
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from shopnod_core import db, templates
from shopnod_core.models import Shop, User

DEMO_SHOPS = [
    ("Ali's Bakery", "bakery"),
    ("Green Basket Grocery", "grocery"),
    ("Chai & Chat Café", "cafe"),
    ("Fresh Mandi Fruit & Veg", "fruit_veg"),
    ("Corner General Store", "general"),
]


async def seed() -> dict[str, int]:
    created = 0
    async with db.session_scope() as s:
        await templates.seed_templates(s)
        area = await templates.ensure_demo_market(s)
        for i, (name, cat) in enumerate(DEMO_SHOPS):
            email = f"demo-shop-{i + 1}@shopnod.local"
            user = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is None:
                user = User(email=email, is_demo=True, is_admin=False)
                s.add(user)
                await s.flush()
            shop = (await s.execute(select(Shop).where(Shop.owner_id == user.id))).scalar_one_or_none()
            if shop is not None:
                continue
            shop = Shop(
                owner_id=user.id, name=name, category=cat, is_demo=True, languages=["en"], timezone=templates.DEMO_TZ,
                currency=templates.DEMO_CURRENCY, hours=dict(templates.DEFAULT_HOURS), quiet_grid=templates.default_quiet_grid(),
                onboarding_status="complete",
            )
            s.add(shop)
            await s.flush()
            lat, lng = templates.demo_spot(i)
            templates.set_location(shop, lat, lng, area)
            await templates.apply_template(s, shop, cat)
            created += 1
    from shopnod_worker.tasks.sim.sim import seed_shoppers

    return {"created_shops": created, "created_sim_shoppers": await seed_shoppers()}


if __name__ == "__main__":
    print(asyncio.run(seed()))
