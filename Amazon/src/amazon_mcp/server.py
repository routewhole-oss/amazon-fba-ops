from fastmcp import FastMCP

from amazon_mcp import catalog_service, cost_config, finances_service, inventory_service, orders_service
from amazon_mcp.errors import to_tool_error
from amazon_mcp.profitability_service import calculate_profitability as _calculate_profitability

mcp = FastMCP("amazon-fba-ops")


@mcp.tool
def get_orders(start_date: str, end_date: str, order_status: str | None = None) -> dict:
    """List Amazon orders created in a date range (YYYY-MM-DD). Optionally filter by order status
    (e.g. Shipped, Unshipped, Canceled)."""
    try:
        return orders_service.get_orders(start_date, end_date, order_status)
    except Exception as exc:
        return to_tool_error(exc)


@mcp.tool
def get_order_items(order_id: str) -> dict:
    """List the SKU/quantity/price line items for one Amazon order."""
    try:
        return orders_service.get_order_items(order_id)
    except Exception as exc:
        return to_tool_error(exc)


@mcp.tool
def get_financial_events(start_date: str, end_date: str) -> dict:
    """List Amazon financial events (fees, refunds, reimbursements) posted in a date range (YYYY-MM-DD)."""
    try:
        return finances_service.get_financial_events(start_date, end_date)
    except Exception as exc:
        return to_tool_error(exc)


@mcp.tool
def calculate_profitability(start_date: str, end_date: str, group_by: str = "sku") -> dict:
    """Compute profitability (revenue, Amazon fees, reimbursements, COGS, net profit, margin %) for a date
    range (YYYY-MM-DD), grouped by 'sku', 'order', or 'day'. Requires SKU costs to be set via set_sku_cost
    for accurate COGS -- SKUs missing a cost are flagged in 'missing_cogs_skus' rather than silently
    treated as zero-cost."""
    try:
        return _calculate_profitability(start_date, end_date, group_by)
    except Exception as exc:
        return to_tool_error(exc)


@mcp.tool
def get_inventory_summary(sku: str | None = None) -> dict:
    """Get current FBA inventory levels (fulfillable, inbound, reserved, unfulfillable quantities),
    optionally filtered to one SKU."""
    try:
        return inventory_service.get_inventory_summary(sku)
    except Exception as exc:
        return to_tool_error(exc)


@mcp.tool
def get_low_stock_alerts(days_of_supply_threshold: int = 14, lookback_days: int = 30) -> dict:
    """Flag SKUs at risk of stocking out soon, estimating days-of-supply from current fulfillable
    inventory and recent sales velocity (units sold over lookback_days)."""
    try:
        return inventory_service.get_low_stock_alerts(days_of_supply_threshold, lookback_days)
    except Exception as exc:
        return to_tool_error(exc)


@mcp.tool
def get_catalog_item(asin: str) -> dict:
    """Get a product's title, brand, image, and dimensions from the Amazon catalog by ASIN."""
    try:
        return catalog_service.get_catalog_item(asin)
    except Exception as exc:
        return to_tool_error(exc)


@mcp.tool
def set_sku_cost(sku: str, cost: float, effective_date: str | None = None) -> dict:
    """Record the cost-of-goods (COGS) for a SKU, used by calculate_profitability_tool. Amazon has no
    concept of product cost, so this must be maintained manually."""
    try:
        return cost_config.set_sku_cost(sku, cost, effective_date)
    except Exception as exc:
        return to_tool_error(exc)


@mcp.tool
def list_sku_costs() -> dict:
    """List all SKU costs currently configured for profitability calculations."""
    try:
        return cost_config.list_sku_costs()
    except Exception as exc:
        return to_tool_error(exc)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
