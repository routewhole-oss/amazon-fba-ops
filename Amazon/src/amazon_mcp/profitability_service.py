"""
Profitability calculation.

Revenue and Amazon fees are derived from Finances API events (not from Orders
directly) because financial events already carry per-SKU charge/fee
breakdowns and reflect what Amazon actually settled -- Orders API data is used
elsewhere (inventory velocity) but isn't re-summed here to avoid double
counting revenue.

Sign convention: amounts keep whatever sign Amazon's API returns (fees are
typically negative, charges/reimbursements positive) -- we sum them as-is
rather than re-deriving signs ourselves.

Local cost-of-goods (COGS) is subtracted per unit sold, using order-item
quantities (Orders API) matched by SKU, since Amazon has no concept of
product cost.
"""

from amazon_mcp.cost_config import list_sku_costs
from amazon_mcp.finances_service import get_financial_events
from amazon_mcp.orders_service import get_order_items, get_orders

VALID_GROUP_BY = ("sku", "order", "day")


def _group_key(event: dict, group_by: str) -> str:
    if group_by == "sku":
        return event.get("sku") or "UNKNOWN_SKU"
    if group_by == "order":
        return event.get("order_id") or "ACCOUNT_LEVEL"
    if group_by == "day":
        posted = event.get("posted_date")
        return posted[:10] if posted else "UNKNOWN_DATE"
    raise ValueError(f"group_by must be one of {VALID_GROUP_BY}")


def _units_sold_by_sku(start_date: str, end_date: str) -> dict[str, int]:
    orders = get_orders(start_date, end_date)["orders"]
    units_by_sku: dict[str, int] = {}
    for order in orders:
        order_id = order.get("order_id")
        if not order_id:
            continue
        for item in get_order_items(order_id)["items"]:
            sku = item.get("sku")
            qty = item.get("quantity_ordered") or 0
            if sku:
                units_by_sku[sku] = units_by_sku.get(sku, 0) + qty
    return units_by_sku


def calculate_profitability(start_date: str, end_date: str, group_by: str = "sku") -> dict:
    if group_by not in VALID_GROUP_BY:
        raise ValueError(f"group_by must be one of {VALID_GROUP_BY}, got '{group_by}'")

    financial_result = get_financial_events(start_date, end_date)
    events = financial_result["events"]

    groups: dict[str, dict] = {}
    for event in events:
        key = _group_key(event, group_by)
        row = groups.setdefault(
            key,
            {"key": key, "revenue": 0.0, "fees": 0.0, "reimbursements": 0.0, "other_adjustments": 0.0},
        )
        amount = event["amount"]
        category = event["category"]
        if category == "charge":
            row["revenue"] += amount
        elif category == "fee":
            row["fees"] += amount
        elif category == "reimbursement":
            row["reimbursements"] += amount
        else:
            row["other_adjustments"] += amount

    cogs_by_sku = {sku: entry["cost"] for sku, entry in list_sku_costs().items()}
    units_by_sku = _units_sold_by_sku(start_date, end_date) if group_by == "sku" else {}
    missing_cogs_skus = []

    rows = []
    for key, row in groups.items():
        cogs_total = 0.0
        if group_by == "sku":
            units = units_by_sku.get(key, 0)
            unit_cost = cogs_by_sku.get(key)
            if unit_cost is None and units > 0:
                missing_cogs_skus.append(key)
            cogs_total = (unit_cost or 0) * units
        net_profit = row["revenue"] + row["fees"] + row["reimbursements"] + row["other_adjustments"] - cogs_total
        rows.append(
            {
                group_by: key,
                "revenue": round(row["revenue"], 2),
                "amazon_fees": round(row["fees"], 2),
                "reimbursements": round(row["reimbursements"], 2),
                "other_adjustments": round(row["other_adjustments"], 2),
                "cogs": round(cogs_total, 2),
                "net_profit": round(net_profit, 2),
                "margin_pct": round((net_profit / row["revenue"] * 100), 1) if row["revenue"] else None,
            }
        )

    rows.sort(key=lambda r: r["net_profit"])

    summary = {
        "revenue": round(sum(r["revenue"] for r in rows), 2),
        "amazon_fees": round(sum(r["amazon_fees"] for r in rows), 2),
        "reimbursements": round(sum(r["reimbursements"] for r in rows), 2),
        "cogs": round(sum(r["cogs"] for r in rows), 2),
        "net_profit": round(sum(r["net_profit"] for r in rows), 2),
    }

    return {
        "group_by": group_by,
        "rows": rows,
        "summary": summary,
        "missing_cogs_skus": sorted(set(missing_cogs_skus)),
        "truncated": financial_result["truncated"],
    }
