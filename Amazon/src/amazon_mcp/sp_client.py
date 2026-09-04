"""
Thin factory functions for SP-API clients.

Credentials (LWA_APP_ID / LWA_CLIENT_SECRET / SP_API_REFRESH_TOKEN) are read
directly from the environment by python-amazon-sp-api's own credential
provider -- we don't build a credentials dict ourselves. We only resolve
which marketplace to target and validate the env is set up before any call.
"""

from sp_api.api import CatalogItems, Finances, Inventories, Orders

from amazon_mcp.config import get_marketplace, validate_credentials


def get_orders_client() -> Orders:
    validate_credentials()
    return Orders(marketplace=get_marketplace())


def get_finances_client() -> Finances:
    validate_credentials()
    return Finances(marketplace=get_marketplace())


def get_inventories_client() -> Inventories:
    validate_credentials()
    return Inventories(marketplace=get_marketplace())


def get_catalog_client() -> CatalogItems:
    validate_credentials()
    return CatalogItems(marketplace=get_marketplace())
