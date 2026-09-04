from unittest.mock import patch

from amazon_mcp.profitability_service import calculate_profitability

FAKE_FINANCIAL_EVENTS = {
    "events": [
        {"event_type": "ShipmentEvent", "category": "charge", "order_id": "ORDER-1", "posted_date": "2026-07-01T00:00:00Z", "sku": "SKU-A", "description": "Principal", "amount": 20.00},
        {"event_type": "ShipmentEvent", "category": "fee", "order_id": "ORDER-1", "posted_date": "2026-07-01T00:00:00Z", "sku": "SKU-A", "description": "Commission", "amount": -3.00},
        {"event_type": "ShipmentEvent", "category": "charge", "order_id": "ORDER-2", "posted_date": "2026-07-02T00:00:00Z", "sku": "SKU-B", "description": "Principal", "amount": 15.00},
        {"event_type": "ShipmentEvent", "category": "fee", "order_id": "ORDER-2", "posted_date": "2026-07-02T00:00:00Z", "sku": "SKU-B", "description": "Commission", "amount": -2.50},
        {"event_type": "AdjustmentEvent", "category": "reimbursement", "order_id": None, "posted_date": "2026-07-03T00:00:00Z", "sku": "SKU-A", "description": "FBA_INVENTORY_REIMBURSEMENT", "amount": 5.00},
    ],
    "count": 5,
    "other_event_groups": {},
    "truncated": False,
}

FAKE_ORDERS = {
    "orders": [
        {"order_id": "ORDER-1", "purchase_date": "2026-07-01T00:00:00Z"},
        {"order_id": "ORDER-2", "purchase_date": "2026-07-02T00:00:00Z"},
    ],
    "count": 2,
    "truncated": False,
}

FAKE_ORDER_ITEMS = {
    "ORDER-1": {"order_id": "ORDER-1", "items": [{"sku": "SKU-A", "quantity_ordered": 1}], "truncated": False},
    "ORDER-2": {"order_id": "ORDER-2", "items": [{"sku": "SKU-B", "quantity_ordered": 1}], "truncated": False},
}

FAKE_SKU_COSTS = {
    "SKU-A": {"cost": 4.5, "effective_date": None},
    # SKU-B intentionally has no configured cost -- should surface in missing_cogs_skus
}


@patch("amazon_mcp.profitability_service.list_sku_costs", return_value=FAKE_SKU_COSTS)
@patch("amazon_mcp.profitability_service.get_order_items", side_effect=lambda order_id: FAKE_ORDER_ITEMS[order_id])
@patch("amazon_mcp.profitability_service.get_orders", return_value=FAKE_ORDERS)
@patch("amazon_mcp.profitability_service.get_financial_events", return_value=FAKE_FINANCIAL_EVENTS)
def test_calculate_profitability_by_sku(mock_events, mock_orders, mock_items, mock_costs):
    result = calculate_profitability("2026-07-01", "2026-07-03", group_by="sku")

    rows_by_sku = {row["sku"]: row for row in result["rows"]}

    assert rows_by_sku["SKU-A"]["revenue"] == 20.00
    assert rows_by_sku["SKU-A"]["amazon_fees"] == -3.00
    assert rows_by_sku["SKU-A"]["reimbursements"] == 5.00
    assert rows_by_sku["SKU-A"]["cogs"] == 4.5
    assert rows_by_sku["SKU-A"]["net_profit"] == 17.5

    assert rows_by_sku["SKU-B"]["revenue"] == 15.00
    assert rows_by_sku["SKU-B"]["amazon_fees"] == -2.50
    assert rows_by_sku["SKU-B"]["cogs"] == 0
    assert rows_by_sku["SKU-B"]["net_profit"] == 12.5

    assert result["missing_cogs_skus"] == ["SKU-B"]
    assert result["summary"]["net_profit"] == 30.0
    assert result["summary"]["revenue"] == 35.0
    # sorted ascending by net_profit -> SKU-B (12.5) before SKU-A (17.5)
    assert [r["sku"] for r in result["rows"]] == ["SKU-B", "SKU-A"]


@patch("amazon_mcp.profitability_service.list_sku_costs", return_value=FAKE_SKU_COSTS)
@patch("amazon_mcp.profitability_service.get_financial_events", return_value=FAKE_FINANCIAL_EVENTS)
def test_calculate_profitability_by_day(mock_events, mock_costs):
    result = calculate_profitability("2026-07-01", "2026-07-03", group_by="day")
    days = {row["day"] for row in result["rows"]}
    assert days == {"2026-07-01", "2026-07-02", "2026-07-03"}
    # group_by="day" doesn't compute COGS (no per-day unit mapping) -- cogs stays 0
    assert all(row["cogs"] == 0 for row in result["rows"])


def test_calculate_profitability_rejects_invalid_group_by():
    import pytest

    with pytest.raises(ValueError):
        calculate_profitability("2026-07-01", "2026-07-03", group_by="bogus")
