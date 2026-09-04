from sp_api.util import throttle_retry

from amazon_mcp.sp_client import get_orders_client

MAX_PAGES = 50


def _to_iso(date_str: str) -> str:
    """Accepts 'YYYY-MM-DD' or a full ISO8601 string; returns ISO8601 UTC."""
    if "T" in date_str:
        return date_str
    return f"{date_str}T00:00:00Z"


@throttle_retry()
def _get_orders_page(client, **kwargs):
    return client.get_orders(**kwargs)


def get_orders(start_date: str, end_date: str, order_status: str | None = None) -> dict:
    client = get_orders_client()
    kwargs = {
        "CreatedAfter": _to_iso(start_date),
        "CreatedBefore": _to_iso(end_date),
    }
    if order_status:
        kwargs["OrderStatuses"] = [order_status]

    orders = []
    next_token = None
    truncated = False
    for _ in range(MAX_PAGES):
        if next_token:
            kwargs = {"NextToken": next_token}
        response = _get_orders_page(client, **kwargs)
        payload = response.payload or {}
        orders.extend(payload.get("Orders", []))
        next_token = payload.get("NextToken")
        if not next_token:
            break
    else:
        truncated = bool(next_token)

    return {
        "orders": [
            {
                "order_id": o.get("AmazonOrderId"),
                "purchase_date": o.get("PurchaseDate"),
                "order_status": o.get("OrderStatus"),
                "order_total": (o.get("OrderTotal") or {}).get("Amount"),
                "currency": (o.get("OrderTotal") or {}).get("CurrencyCode"),
                "fulfillment_channel": o.get("FulfillmentChannel"),
                "marketplace_id": o.get("MarketplaceId"),
            }
            for o in orders
        ],
        "count": len(orders),
        "truncated": truncated,
    }


@throttle_retry()
def _get_order_items_page(client, order_id: str, **kwargs):
    return client.get_order_items(order_id, **kwargs)


def get_order_items(order_id: str) -> dict:
    client = get_orders_client()
    items = []
    next_token = None
    truncated = False
    for _ in range(MAX_PAGES):
        kwargs = {"NextToken": next_token} if next_token else {}
        response = _get_order_items_page(client, order_id, **kwargs)
        payload = response.payload or {}
        items.extend(payload.get("OrderItems", []))
        next_token = payload.get("NextToken")
        if not next_token:
            break
    else:
        truncated = bool(next_token)

    return {
        "order_id": order_id,
        "items": [
            {
                "sku": i.get("SellerSKU"),
                "asin": i.get("ASIN"),
                "quantity_ordered": i.get("QuantityOrdered"),
                "item_price": (i.get("ItemPrice") or {}).get("Amount"),
                "item_tax": (i.get("ItemTax") or {}).get("Amount"),
                "currency": (i.get("ItemPrice") or {}).get("CurrencyCode"),
            }
            for i in items
        ],
        "truncated": truncated,
    }
