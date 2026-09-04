"""Local cost-of-goods (COGS) store -- Amazon has no concept of product cost,
so the seller maintains this themselves as a small JSON file, keyed by SKU."""

import json
import os
from pathlib import Path

from amazon_mcp.config import get_sku_cost_store_path


def _store_path() -> Path:
    path = Path(get_sku_cost_store_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load() -> dict:
    path = _store_path()
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return json.load(f)


def _save(data: dict) -> None:
    path = _store_path()
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp_path, path)


def set_sku_cost(sku: str, cost: float, effective_date: str | None = None) -> dict:
    data = _load()
    data[sku] = {"cost": cost, "effective_date": effective_date}
    _save(data)
    return data[sku]


def list_sku_costs() -> dict:
    return _load()


def get_sku_cost(sku: str) -> float | None:
    entry = _load().get(sku)
    return entry["cost"] if entry else None
