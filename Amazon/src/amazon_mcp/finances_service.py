from sp_api.util import throttle_retry

from amazon_mcp.sp_client import get_finances_client

MAX_PAGES = 50

# Event-list keys we fully normalize into flat, profitability-relevant entries.
# Everything else in FinancialEvents is still counted (see "other_event_groups")
# so nothing is silently dropped, but isn't broken down line-by-line for MVP.
_NORMALIZED_GROUPS = ("ShipmentEventList", "RefundEventList", "ServiceFeeEventList", "AdjustmentEventList")


def _to_iso(date_str: str) -> str:
    if "T" in date_str:
        return date_str
    return f"{date_str}T00:00:00Z"


def _money(m: dict | None) -> float:
    if not m:
        return 0.0
    try:
        return float(m.get("CurrencyAmount", m.get("Amount", 0)) or 0)
    except (TypeError, ValueError):
        return 0.0


def _flatten_shipment_or_refund(events: list, event_type: str) -> list[dict]:
    flat = []
    for event in events:
        order_id = event.get("AmazonOrderId")
        posted_date = event.get("PostedDate")
        for item in event.get("ShipmentItemList", []) or event.get("ShipmentItemAdjustmentList", []):
            sku = item.get("SellerSKU")
            for charge in item.get("ItemChargeList", []) or item.get("ItemChargeAdjustmentList", []):
                flat.append(
                    {
                        "event_type": event_type,
                        "category": "charge",
                        "order_id": order_id,
                        "posted_date": posted_date,
                        "sku": sku,
                        "description": charge.get("ChargeType"),
                        "amount": _money(charge.get("ChargeAmount")),
                    }
                )
            for fee in item.get("ItemFeeList", []) or item.get("ItemFeeAdjustmentList", []):
                flat.append(
                    {
                        "event_type": event_type,
                        "category": "fee",
                        "order_id": order_id,
                        "posted_date": posted_date,
                        "sku": sku,
                        "description": fee.get("FeeType"),
                        "amount": _money(fee.get("FeeAmount")),
                    }
                )
    return flat


def _flatten_service_fees(events: list) -> list[dict]:
    """Account-level fees (e.g. subscription, A-to-z claims) -- not tied to an order."""
    flat = []
    for event in events:
        fee_reason = event.get("FeeReason")
        for fee in event.get("FeeList", []):
            flat.append(
                {
                    "event_type": "ServiceFeeEvent",
                    "category": "fee",
                    "order_id": None,
                    "posted_date": event.get("PostedDate"),
                    "sku": event.get("SellerSKU"),
                    "description": f"{fee_reason}:{fee.get('FeeType')}" if fee_reason else fee.get("FeeType"),
                    "amount": _money(fee.get("FeeAmount")),
                }
            )
    return flat


def _flatten_adjustments(events: list) -> list[dict]:
    flat = []
    for event in events:
        adjustment_type = event.get("AdjustmentType")
        for item in event.get("AdjustmentItemList", []):
            flat.append(
                {
                    "event_type": "AdjustmentEvent",
                    "category": "reimbursement" if adjustment_type == "FBA_INVENTORY_REIMBURSEMENT" else "adjustment",
                    "order_id": None,
                    "posted_date": event.get("PostedDate"),
                    "sku": item.get("SellerSKU"),
                    "description": adjustment_type,
                    "amount": _money(item.get("TotalAmount")),
                }
            )
    return flat


@throttle_retry()
def _list_events_page(client, **kwargs):
    return client.list_financial_events(**kwargs)


def get_financial_events(start_date: str, end_date: str) -> dict:
    client = get_finances_client()
    kwargs = {
        "PostedAfter": _to_iso(start_date),
        "PostedBefore": _to_iso(end_date),
    }

    flat_events: list[dict] = []
    other_group_counts: dict[str, int] = {}
    next_token = None
    truncated = False
    for _ in range(MAX_PAGES):
        if next_token:
            kwargs = {"NextToken": next_token}
        response = _list_events_page(client, **kwargs)
        payload = response.payload or {}
        financial_events = payload.get("FinancialEvents", {})

        flat_events.extend(_flatten_shipment_or_refund(financial_events.get("ShipmentEventList", []), "ShipmentEvent"))
        flat_events.extend(_flatten_shipment_or_refund(financial_events.get("RefundEventList", []), "RefundEvent"))
        flat_events.extend(_flatten_service_fees(financial_events.get("ServiceFeeEventList", [])))
        flat_events.extend(_flatten_adjustments(financial_events.get("AdjustmentEventList", [])))

        for key, value in financial_events.items():
            if key not in _NORMALIZED_GROUPS and isinstance(value, list) and value:
                other_group_counts[key] = other_group_counts.get(key, 0) + len(value)

        next_token = payload.get("NextToken")
        if not next_token:
            break
    else:
        truncated = bool(next_token)

    return {
        "events": flat_events,
        "count": len(flat_events),
        "other_event_groups": other_group_counts,
        "truncated": truncated,
    }
