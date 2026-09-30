#!/usr/bin/env python3
"""Fetch and normalize public demo product data for the local ShopCart catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

USER_AGENT = "ShopCartLocalCatalogSeed/1.0"
TARGET_COUNT = 400


def fetch_json(url: str) -> Any:
    last_error: Exception | None = None
    for attempt in range(4):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.load(response)
        except Exception as error:
            last_error = error
            if attempt < 3:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Unable to fetch {url}: {last_error}") from last_error


def clean_text(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit].strip()


def normalized_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def valid_image(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().strip("[]\"'")
    parsed = urllib.parse.urlparse(value)
    return value[:500] if parsed.scheme in {"http", "https"} and parsed.netloc else None


def vnd_price(source: str, source_id: str, raw_price: Any = None) -> int:
    if raw_price is not None:
        try:
            usd = min(max(Decimal(str(raw_price)), Decimal("0.6")), Decimal("2000"))
            return int((usd * 25000 / 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * 1000)
        except Exception:
            pass
    digest = int(hashlib.sha256(f"{source}:{source_id}".encode()).hexdigest()[:8], 16)
    return 15000 + (digest % 286) * 1000


def quantity(source: str, source_id: str, raw_stock: Any = None) -> int:
    try:
        stock = int(raw_stock)
        if stock >= 0:
            return min(stock, 9999)
    except Exception:
        pass
    digest = int(hashlib.sha256(f"stock:{source}:{source_id}".encode()).hexdigest()[:8], 16)
    return 15 + digest % 186


def canonical_category(source: str, raw_category: Any, name: str) -> str:
    if source == "off":
        return "thuc-pham-do-uong"
    text = normalized_name(f"{raw_category or ''} {name}")
    rules = [
        ("dien-thoai-phu-kien", ("phone", "smartphone", "tablet", "mobile", "accessor", "charger")),
        ("may-tinh-laptop", ("computer", "laptop", "keyboard", "mouse", "software")),
        ("dien-tu-am-thanh", ("electronic", "television", "audio", "speaker", "headphone", "camera")),
        ("thoi-trang-nam", ("mens", "men ", "shirt", "mens shoe", "tie")),
        ("thoi-trang-nu", ("womens", "women", "dress", "skirt", "jewel", "handbag", "heel")),
        ("suc-khoe-lam-dep", ("beauty", "skin", "fragrance", "cosmetic", "health", "personal care")),
        ("the-thao-du-lich", ("sport", "fitness", "outdoor", "travel", "bicycle")),
        ("sach-van-phong-pham", ("book", "stationery", "office", "fiction")),
        ("do-choi-me-be", ("toy", "baby", "kid", "child")),
        ("o-to-xe-may", ("vehicle", "motorcycle", "automotive", "car ")),
        ("thuc-pham-do-uong", ("food", "drink", "grocery", "milk", "meat", "fruit", "vegetable")),
    ]
    for slug, keywords in rules:
        if any(keyword in text for keyword in keywords):
            return slug
    return "nha-cua-doi-song"


def record(source: str, source_id: Any, name: Any, description: Any, price: Any,
           stock: Any, category: Any, image: Any) -> dict[str, Any] | None:
    source_id = clean_text(source_id, 32)
    name = clean_text(name, 200)
    image = valid_image(image)
    if not source_id or not name or not image:
        return None
    return {
        "sku": f"WEB-{source.upper()}-{source_id}"[:50],
        "name": name,
        "description": clean_text(description, 3000) or f"Sản phẩm demo nhập từ {source}.",
        "price": vnd_price(source, source_id, price),
        "currency": "VND",
        "quantity": quantity(source, source_id, stock),
        "category": canonical_category(source, category, name),
        "image_url": image,
    }


def collect_from_file(path: str) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as source_file:
        products = json.load(source_file)
    if len(products) != TARGET_COUNT:
        raise RuntimeError(f"Snapshot contains {len(products)} products, expected {TARGET_COUNT}")
    for product in products:
        sku_parts = product.get("sku", "").split("-", 2)
        source = sku_parts[1].lower() if len(sku_parts) > 2 else "snapshot"
        product["category"] = canonical_category(source, product.get("category"), product.get("name", ""))
        product.pop("id", None)
    return products


def collect() -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []

    dummy = fetch_json("https://dummyjson.com/products?limit=0")["products"]
    for item in dummy:
        candidate = record(
            "dummyjson", item.get("id"), item.get("title"), item.get("description"),
            item.get("price"), item.get("stock"), item.get("category"),
            item.get("thumbnail") or (item.get("images") or [None])[0],
        )
        if candidate:
            products.append(candidate)

    platzi = fetch_json("https://api.escuelajs.co/api/v1/products?offset=0&limit=300")
    for item in platzi:
        images = item.get("images") if isinstance(item.get("images"), list) else []
        category = item.get("category") if isinstance(item.get("category"), dict) else {}
        candidate = record(
            "platzi", item.get("id"), item.get("title"), item.get("description"),
            item.get("price"), None, category.get("name"), images[0] if images else None,
        )
        if candidate:
            products.append(candidate)

    for page in range(1, 5):
        off_url = (
            "https://world.openfoodfacts.org/api/v2/search?"
            "fields=code,product_name,brands,categories_tags,image_front_url&"
            f"countries_tags_en=Vietnam&page_size=100&page={page}"
        )
        for item in fetch_json(off_url).get("products", []):
            categories = item.get("categories_tags") or []
            category = categories[-1].removeprefix("en:").replace("-", " ").title() if categories else "Thực phẩm"
            brand = clean_text(item.get("brands"), 80)
            description = f"Thương hiệu: {brand}. Dữ liệu sản phẩm thực phẩm tại Việt Nam." if brand else None
            candidate = record(
                "off", item.get("code"), item.get("product_name"), description,
                None, None, category, item.get("image_front_url"),
            )
            if candidate:
                products.append(candidate)

    unique: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    seen_skus: set[str] = set()
    for item in products:
        name_key = normalized_name(item["name"])
        if not name_key or name_key in seen_names or item["sku"] in seen_skus:
            continue
        seen_names.add(name_key)
        seen_skus.add(item["sku"])
        unique.append(item)
        if len(unique) == TARGET_COUNT:
            break

    if len(unique) < TARGET_COUNT:
        raise RuntimeError(f"Only {len(unique)} distinct usable products were available")
    return unique


def sql_output(products: list[dict[str, Any]]) -> str:
    payload = json.dumps(products, ensure_ascii=False, separators=(",", ":"))
    return f"""BEGIN;
DELETE FROM products WHERE sku LIKE 'WEB-%';
WITH source AS (
  SELECT * FROM jsonb_to_recordset($shopcart${payload}$shopcart$::jsonb) AS x(
    sku text, name text, description text, price numeric, currency text,
    quantity numeric, category text, image_url text
  )
)
INSERT INTO products (
  id, sku, name, description, price, currency, quantity, category,
  is_active, image_url, seller_id, created_at, updated_at
)
SELECT (
  substr(md5(sku),1,8) || '-' || substr(md5(sku),9,4) || '-4' ||
  substr(md5(sku),14,3) || '-a' || substr(md5(sku),18,3) || '-' ||
  substr(md5(sku),21,12)
)::uuid, sku, name, description, price, currency, quantity, category,
true, image_url, NULL, now(), now()
FROM source
ON CONFLICT (sku) DO UPDATE SET
  name = EXCLUDED.name,
  description = EXCLUDED.description,
  price = EXCLUDED.price,
  currency = EXCLUDED.currency,
  quantity = EXCLUDED.quantity,
  category = EXCLUDED.category,
  image_url = EXCLUDED.image_url,
  is_active = true,
  updated_at = now();
COMMIT;
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("json", "sql", "summary"), default="summary")
    parser.add_argument("--input-json", help="Use a previously exported 400-product snapshot")
    args = parser.parse_args()
    products = collect_from_file(args.input_json) if args.input_json else collect()
    if args.format == "json":
        json.dump(products, sys.stdout, ensure_ascii=False, indent=2)
        print()
    elif args.format == "sql":
        print(sql_output(products), end="")
    else:
        print(json.dumps({
            "count": len(products),
            "unique_names": len({normalized_name(p["name"]) for p in products}),
            "categories": len({p["category"] for p in products}),
            "sources": {prefix: sum(p["sku"].startswith(f"WEB-{prefix}-") for p in products)
                        for prefix in ("DUMMYJSON", "PLATZI", "OFF")},
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
