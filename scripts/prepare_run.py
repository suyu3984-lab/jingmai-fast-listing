#!/usr/bin/env python3
"""Normalize a Jingmai CSV/JSON batch into a resumable V2 run manifest."""

from __future__ import annotations

import argparse
import csv
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
IMAGE_STRATEGIES = {
    "inherit_template",
    "replace_all",
    "replace_main_only",
    "replace_detail_only",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_products(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    data = read_json(path)
    products = data.get("products") if isinstance(data, dict) else data
    if not isinstance(products, list):
        raise ValueError("JSON must be an array or contain a products array")
    return products


def clean_title(value: Any, remove_terms: list[str]) -> str:
    title = str(value or "").replace("_", " ")
    for term in remove_terms:
        title = re.sub(re.escape(str(term)), "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title)
    title = re.sub(r"\s*[,，;；]+\s*", " ", title)
    return title.strip(" -_，,；;")


def as_int(value: Any, label: str) -> int:
    text = str(value).strip()
    if not re.fullmatch(r"\d+", text):
        raise ValueError(f"{label} must be a non-negative integer")
    return int(text)


def as_price(value: Any, currency: Any = "元") -> str:
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise ValueError("price must be numeric") from exc
    if amount <= 0:
        raise ValueError("price must be greater than zero")
    if str(currency or "元").strip() == "万":
        amount *= Decimal("10000")
    return format(amount.quantize(Decimal("0.01")), "f")


def parse_json_value(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    return json.loads(str(value))


def parse_image_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if text.startswith("["):
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            raise ValueError("image list JSON must be an array")
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [part.strip() for part in text.split("|") if part.strip()]


def resolve_images(values: list[str], label: str) -> list[str]:
    resolved: list[str] = []
    for value in values:
        image = Path(value).expanduser().resolve()
        if image.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
            raise ValueError(f"{label} must use PNG/JPG/JPEG/WEBP: {image}")
        if not image.is_file():
            raise ValueError(f"{label} not found: {image}")
        resolved.append(str(image))
    return resolved


def adapt_product(row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    pipeline_images = row.get("images") or []
    legacy_image = row.get("image_path")
    if not legacy_image:
        legacy_image = next(
            (image.get("finalPath") for image in pipeline_images if image.get("finalPath")),
            "",
        )
    main_images = (
        row.get("main_images")
        or row.get("main_images_json")
        or ([legacy_image] if legacy_image else [])
    )
    detail_images = row.get("detail_images") or row.get("detail_images_json") or []
    quality = row.get("qualityMeta") or row.get("meta") or {}
    stock_value = row.get("stock")
    if not re.fullmatch(r"\d+", str(stock_value or "").strip()):
        stock_value = config.get("default_stock")
    raw_attrs = row.get("attributes_json")
    if raw_attrs in (None, ""):
        raw_attrs = quality
    return {
        **row,
        "title": row.get("title") or row.get("jdTitle") or row.get("sourceTitle"),
        "model": row.get("model") or quality.get("型号") or "",
        "price_currency": row.get("price_currency") or row.get("priceCurrency") or "元",
        "stock": stock_value,
        "main_images": main_images,
        "detail_images": detail_images,
        "source_url": row.get("source_url") or row.get("sourceUrl") or "",
        "attributes_json": raw_attrs,
        "dispatch_time": row.get("dispatch_time") or config.get("dispatch_time"),
        "image_strategy": row.get("image_strategy") or config.get("image_strategy") or "replace_all",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    args = parser.parse_args()

    config = read_json(args.config)
    required_config = ("store_name", "category_path", "brand", "template_ware_id")
    missing_config = [key for key in required_config if not str(config.get(key, "")).strip()]
    if missing_config:
        raise SystemExit("error: missing config: " + ", ".join(missing_config))
    if config.get("save_mode") != "submit_off_shelf":
        raise SystemExit("error: save_mode must be submit_off_shelf")

    rows = load_products(args.products)
    remove_terms = [str(x) for x in config.get("remove_title_terms", [])]
    seen: set[int] = set()
    items: list[dict[str, Any]] = []
    errors: list[str] = []

    for index, source_row in enumerate(rows, start=2):
        try:
            row = adapt_product(source_row, config)
            sequence = as_int(row.get("sequence"), "sequence")
            if args.start is not None and sequence < args.start:
                continue
            if args.end is not None and sequence > args.end:
                continue
            if sequence in seen:
                raise ValueError(f"duplicate sequence {sequence}")
            seen.add(sequence)
            title = clean_title(row.get("title"), remove_terms)
            if not title:
                raise ValueError("cleaned title is empty")
            image_strategy = str(row.get("image_strategy") or "").strip()
            if image_strategy not in IMAGE_STRATEGIES:
                raise ValueError(
                    "image_strategy must be one of: " + ", ".join(sorted(IMAGE_STRATEGIES))
                )
            main_images = resolve_images(parse_image_list(row.get("main_images")), "main image")
            detail_images = resolve_images(parse_image_list(row.get("detail_images")), "detail image")
            if image_strategy in {"replace_all", "replace_main_only"} and not main_images:
                raise ValueError(f"{image_strategy} requires at least one main image")
            if image_strategy == "replace_all" and not detail_images:
                detail_images = [main_images[0]]
            if image_strategy == "replace_detail_only" and not detail_images:
                raise ValueError("replace_detail_only requires at least one detail image")
            if image_strategy == "inherit_template" and (main_images or detail_images):
                raise ValueError("inherit_template must not supply replacement image paths")
            if image_strategy == "replace_main_only" and detail_images:
                raise ValueError("replace_main_only must not supply replacement detail images")
            if image_strategy == "replace_detail_only" and main_images:
                raise ValueError("replace_detail_only must not supply replacement main images")
            stock = as_int(row.get("stock"), "stock")
            attributes = parse_json_value(row.get("attributes_json"), {})
            if not isinstance(attributes, dict):
                raise ValueError("attributes_json must be an object")
            items.append(
                {
                    "sequence": sequence,
                    "title": title,
                    "model": str(row.get("model") or "").strip(),
                    "price": as_price(row.get("price"), row.get("price_currency")),
                    "stock": stock,
                    "main_images": main_images,
                    "detail_images": detail_images,
                    "final_image": main_images[0] if main_images else None,
                    "image_strategy": image_strategy,
                    "source_url": str(row.get("source_url") or "").strip(),
                    "attributes": attributes,
                    "dispatch_time": str(row.get("dispatch_time") or "").strip(),
                    "status": "pending",
                    "stage": "pending",
                    "execution_mode": None,
                    "attempts": 0,
                    "network_interruptions": 0,
                    "last_url": None,
                    "last_stage_at": None,
                    "ware_id": None,
                    "error": None,
                    "evidence": [],
                }
            )
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"row {index}: {exc}")

    if errors:
        raise SystemExit("error:\n" + "\n".join(errors))
    if not items:
        raise SystemExit("error: no products found")

    payload = {
        "schema_version": 2,
        "source_products": str(args.products.resolve()),
        "source_config": str(args.config.resolve()),
        "config": config,
        "runtime": {
            "recommended_mode": "safe",
            "profile_verified": False,
            "page_fingerprint": None,
            "last_verified_at": None,
            "invalidation_reason": "not_verified",
            "consecutive_successes": 0,
            "network_interruptions": 0,
        },
        "items": sorted(items, key=lambda item: item["sequence"]),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"prepared {len(items)} products -> {args.out.resolve()}")


if __name__ == "__main__":
    main()
