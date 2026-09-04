from datetime import datetime, timedelta, timezone

from sp_api.util import throttle_retry

from amazon_mcp.orders_service import get_order_items, get_orders
from amazon_mcp.sp_client import get_inventories_client


@throttle_retry()
def _get_inventory_page(client, **kwargs):
    return client.get_inventory_summary_marketplace(**kwargs)


def get_inventory_summary(sku: str | None = None) -> dict:
    client = get_inventories_client()
    kwargs = {"sellerSkus": [sku]} if sku else {}

    summaries = []
    next_token = None
    for _ in range(50):
        if next_token:
            kwargs = {"nextToken": next_token}
        response = _get_inventory_page(client, **kwargs)
        payload = response.payload or {}
        summaries.extend(payload.get("inventorySummaries", []))
        next_token = (payload.get("pagination") or {}).get("nextToken")
        if not next_token:
            break

    return {
        "inventory": [
            {
                "sku": s.get("sellerSku"),
                "asin": s.get("asin"),
                "condition": s.get("condition"),
                "fulfillable_quantity": (s.get("inventoryDetails") or {}).get("fulfillableQuantity", 0),
                "inbound_working_quantity": (s.get("inventoryDetails") or {}).get("inboundWorkingQuantity", 0),
                "inbound_shipped_quantity": (s.get("inventoryDetails") or {}).get("inboundShippedQuantity", 0),
                "inbound_receiving_quantity": (s.get("inventoryDetails") or {}).get("inboundReceivingQuantity", 0),
                "reserved_quantity": ((s.get("inventoryDetails") or {}).get("reservedQuantity") or {}).get(
                    "totalReservedQuantity", 0
                ),
                "unfulfillable_quantity": ((s.get("inventoryDetails") or {}).get("unfulfillableQuantity") or {}).get(
                    "totalUnfulfillableQuantity", 0
                ),
                "total_quantity": s.get("totalQuantity", 0),
            }
            for s in summaries
        ],
        "count": len(summaries),
    }


MAX_ORDERS_FOR_VELOCITY = 200


def _sales_velocity(lookback_days: int) -> tuple[dict[str, float], bool]:
    """units sold per day, per SKU, over the lookback window.

    Calls get_order_items once per order, which doesn't scale to sellers with
    very high order volume -- capped at MAX_ORDERS_FOR_VELOCITY to avoid a slow,
    rate-limit-heavy call. Returns (velocity_by_sku, sampled) so callers know
    if the estimate is based on a subset of orders.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    orders = get_orders(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))["orders"]
    sampled = len(orders) > MAX_ORDERS_FOR_VELOCITY
    orders = orders[:MAX_ORDERS_FOR_VELOCITY]

    units_by_sku: dict[str, float] = {}
    for order in orders:
        order_id = order.get("order_id")
        if not order_id:
            continue
        for item in get_order_items(order_id)["items"]:
            sku = item.get("sku")
            qty = item.get("quantity_ordered") or 0
            if sku:
                units_by_sku[sku] = units_by_sku.get(sku, 0) + qty

    return {sku: units / lookback_days for sku, units in units_by_sku.items()}, sampled


def get_low_stock_alerts(days_of_supply_threshold: int = 14, lookback_days: int = 30) -> dict:
    inventory = get_inventory_summary()["inventory"]
    velocity, sampled = _sales_velocity(lookback_days)

    alerts = []
    dormant = []
    for item in inventory:
        sku = item["sku"]
        fulfillable = item["fulfillable_quantity"]
        daily_velocity = velocity.get(sku, 0.0)

        if daily_velocity <= 0:
            if fulfillable > 0:
                dormant.append({"sku": sku, "fulfillable_quantity": fulfillable})
            continue

        days_of_supply = fulfillable / daily_velocity
        if days_of_supply < days_of_supply_threshold:
            alerts.append(
                {
                    "sku": sku,
                    "fulfillable_quantity": fulfillable,
                    "daily_velocity": round(daily_velocity, 3),
                    "days_of_supply": round(days_of_supply, 1),
                }
            )

    alerts.sort(key=lambda a: a["days_of_supply"])

    return {
        "threshold_days": days_of_supply_threshold,
        "lookback_days": lookback_days,
        "low_stock": alerts,
        "dormant_with_stock": dormant,
        "velocity_sampled": sampled,
    }
