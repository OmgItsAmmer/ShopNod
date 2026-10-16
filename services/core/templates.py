"""Category templates (no pharmacy), the Demo Market and the wizard's "apply template" step."""
from __future__ import annotations

import math
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import clock, geo
from .models import CategoryTemplate, Guardrail, Item, ItemPriceHistory, MarketArea, Shop

DEMO_MARKET = {"slug": "demo", "name": "Demo Market", "center_lat": 31.5204, "center_lng": 74.3587}
DEMO_TZ = "Asia/Karachi"
DEMO_CURRENCY = "PKR"

DEFAULT_HOURS = {d: ["08:00", "21:00"] for d in ("mon", "tue", "wed", "thu", "fri", "sat")} | {"sun": ["09:00", "20:00"]}
DEFAULT_GUARDRAILS = {
    "min_price_minor": 0,
    "max_discount_pct": 20,
    "max_offers_per_day": 3,
    "max_redemptions_per_offer": 40,
    "daily_budget_minor": 150_000,
    "weekly_budget_minor": 700_000,
    "allowed_hours": {"start": "08:00", "end": "21:00"},
}


def default_quiet_grid() -> dict[str, list[str]]:
    """busy at breakfast, lunch and early evening; quiet mid-afternoon."""
    day = ["normal"] * 24
    for h in (8, 9, 12, 13, 17, 18):
        day[h] = "busy"
    for h in (15, 16):
        day[h] = "quiet"
    for h in list(range(0, 7)) + [22, 23]:
        day[h] = "normal"
    return {d: list(day) for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}


def _i(name, category, price, cost, qty, exp_h=None):
    return {"name": name, "category": category, "price": price, "cost": cost, "quantity": qty, "expires_in_hours": exp_h}


TEMPLATES: dict[str, dict] = {
    "bakery": {
        "name": "Bakery",
        "guardrails": {**DEFAULT_GUARDRAILS, "max_discount_pct": 25},
        "items": [
            _i("Croissant", "pastry", 180, 90, 12, 10), _i("Sourdough loaf", "bread", 450, 220, 8, 20),
            _i("White bread", "bread", 120, 70, 20, 30), _i("Chocolate cookies", "cookies", 250, 120, 15, None),
            _i("Cake slice", "cake", 400, 200, 6, 8),
        ],
    },
    "grocery": {
        "name": "Grocery",
        "guardrails": {**DEFAULT_GUARDRAILS, "max_discount_pct": 15},
        "items": [
            _i("Milk 1L", "dairy", 290, 250, 30, 48), _i("Eggs (dozen)", "eggs", 380, 330, 24, 96),
            _i("Rice 5kg", "pantry", 1450, 1250, 15, None), _i("Cooking oil 1L", "pantry", 620, 560, 20, None),
            _i("Yoghurt", "dairy", 180, 140, 18, 30),
        ],
    },
    "cafe": {
        "name": "Café",
        "guardrails": {**DEFAULT_GUARDRAILS, "max_discount_pct": 30},
        "items": [
            _i("Latte", "coffee", 450, 120, 40, None), _i("Cappuccino", "coffee", 420, 110, 40, None),
            _i("Iced tea", "drinks", 300, 80, 30, None), _i("Brownie", "dessert", 350, 150, 10, 20),
            _i("Club sandwich", "food", 550, 260, 8, 12),
        ],
    },
    "fruit_veg": {
        "name": "Fruit & veg",
        "guardrails": {**DEFAULT_GUARDRAILS, "max_discount_pct": 30},
        "items": [
            _i("Tomatoes (kg)", "vegetables", 160, 110, 25, 36), _i("Bananas (dozen)", "fruit", 200, 140, 20, 40),
            _i("Apples (kg)", "fruit", 380, 290, 15, None), _i("Spinach bunch", "vegetables", 60, 35, 30, 20),
            _i("Mangoes (kg)", "fruit", 420, 320, 12, 48),
        ],
    },
    "general": {
        "name": "General store",
        "guardrails": {**DEFAULT_GUARDRAILS, "max_discount_pct": 15},
        "items": [
            _i("Notebook", "stationery", 150, 100, 40, None), _i("Soap bar", "household", 120, 80, 50, None),
            _i("AA batteries (4)", "household", 380, 280, 25, None), _i("Biscuits", "snacks", 90, 60, 60, 120),
            _i("Soft drink 1.5L", "drinks", 210, 160, 36, None),
        ],
    },
}
TEMPLATE_KEYS = tuple(TEMPLATES)


async def seed_templates(session: AsyncSession) -> None:
    for key, t in TEMPLATES.items():
        row = await session.get(CategoryTemplate, key)
        if row is None:
            row = CategoryTemplate(key=key)
            session.add(row)
        row.name, row.items, row.guardrails, row.quiet_grid = t["name"], t["items"], t["guardrails"], default_quiet_grid()
    await session.flush()


async def ensure_demo_market(session: AsyncSession) -> MarketArea:
    area = (await session.execute(select(MarketArea).where(MarketArea.slug == "demo"))).scalar_one_or_none()
    if area is None:
        area = MarketArea(**DEMO_MARKET)
        session.add(area)
        await session.flush()
    return area


def demo_spot(index: int) -> tuple[float, float]:
    """Scatter shops within ~500 m of the market centre."""
    angle = (index * 137.5) % 360
    dist_m = 150 + (index * 90) % 350
    dlat = (dist_m * math.cos(math.radians(angle))) / 111_320
    dlng = (dist_m * math.sin(math.radians(angle))) / (111_320 * math.cos(math.radians(DEMO_MARKET["center_lat"])))
    return DEMO_MARKET["center_lat"] + dlat, DEMO_MARKET["center_lng"] + dlng


def set_location(shop: Shop, lat: float, lng: float, area: MarketArea | None = None) -> None:
    shop.lat, shop.lng = lat, lng
    shop.geohash6 = geo.encode(lat, lng, 6)
    if area is not None:
        shop.area_id = area.id


async def apply_template(session: AsyncSession, shop: Shop, key: str, *, replace_items: bool = True) -> int:
    """Fill items + guardrails + quiet grid + hours from a template. Returns the number of items created."""
    tpl = TEMPLATES.get(key) or TEMPLATES["general"]
    now = clock.now()
    if replace_items:
        old_ids = (await session.execute(select(Item.id).where(Item.shop_id == shop.id))).scalars().all()
        if old_ids:
            await session.execute(delete(ItemPriceHistory).where(ItemPriceHistory.item_id.in_(old_ids)))
            await session.execute(delete(Item).where(Item.id.in_(old_ids)))
    n = 0
    for spec in tpl["items"]:
        price, cost = int(spec["price"] * 100), int(spec["cost"] * 100)
        it = Item(
            shop_id=shop.id, name=spec["name"], category=spec["category"], price_minor=price, regular_price_minor=price,
            regular_price_since=(now - timedelta(days=90)).date(), cost_minor=cost,
            min_price_minor=int(math.ceil(cost * 1.05)), quantity=spec["quantity"],
            expires_at=now + timedelta(hours=spec["expires_in_hours"]) if spec["expires_in_hours"] else None,
        )
        session.add(it)
        await session.flush()
        session.add(ItemPriceHistory(item_id=it.id, price_minor=price, changed_at=now - timedelta(days=90)))
        n += 1
    g = (await session.execute(select(Guardrail).where(Guardrail.shop_id == shop.id))).scalar_one_or_none()
    if g is None:
        g = Guardrail(shop_id=shop.id)
        session.add(g)
    for k, v in tpl["guardrails"].items():
        setattr(g, k, v)
    g.never_discount_item_ids, g.blocked_categories, g.updated_at = [], [], now
    shop.template_key = key if key in TEMPLATES else "general"
    shop.hours = dict(DEFAULT_HOURS)
    shop.quiet_grid = default_quiet_grid()
    await session.flush()
    return n

