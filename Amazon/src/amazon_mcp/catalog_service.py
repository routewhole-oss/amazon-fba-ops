from sp_api.util import throttle_retry

from amazon_mcp.sp_client import get_catalog_client


@throttle_retry()
def _get_catalog_item(client, asin: str):
    return client.get_catalog_item(asin, includedData=["summaries", "images", "dimensions"])


def get_catalog_item(asin: str) -> dict:
    client = get_catalog_client()
    response = _get_catalog_item(client, asin)
    payload = response.payload or {}

    summaries = payload.get("summaries", [])
    summary = summaries[0] if summaries else {}
    images = payload.get("images", [])
    image_url = None
    if images and images[0].get("images"):
        image_url = images[0]["images"][0].get("link")

    return {
        "asin": asin,
        "title": summary.get("itemName"),
        "brand": summary.get("brandName"),
        "image_url": image_url,
        "dimensions": payload.get("dimensions"),
    }
