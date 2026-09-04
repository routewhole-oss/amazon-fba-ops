import os

from dotenv import load_dotenv
from sp_api.base import Marketplaces

load_dotenv()

REQUIRED_ENV_VARS = ["LWA_APP_ID", "LWA_CLIENT_SECRET", "SP_API_REFRESH_TOKEN"]


def validate_credentials() -> None:
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "Missing required SP-API credentials in .env: "
            f"{', '.join(missing)}. See README.md for how to obtain them."
        )


def get_marketplace() -> Marketplaces:
    name = os.environ.get("SP_API_DEFAULT_MARKETPLACE", "US")
    try:
        return Marketplaces[name]
    except KeyError:
        valid = ", ".join(m.name for m in Marketplaces)
        raise RuntimeError(
            f"SP_API_DEFAULT_MARKETPLACE='{name}' is not a valid marketplace. "
            f"Valid values: {valid}"
        )


def get_sku_cost_store_path() -> str:
    return os.environ.get("SKU_COST_STORE_PATH", "./data/sku_costs.json")
