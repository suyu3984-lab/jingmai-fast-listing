#!/usr/bin/env python3
"""Validate a prepared Jingmai V2 run manifest on the current computer."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_RETURN_POLICY = "不支持7天无理由退货"
VALID_STATUSES = {
    "pending",
    "in_progress",
    "network_interrupted",
    "submission_unknown",
    "failed",
    "submitted_off_shelf",
}
VALID_STAGES = {"pending", "claimed", "opened", "acquired", "filled", "gated", "submit_clicked", "completed"}
VALID_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
IMAGE_STRATEGIES = {
    "inherit_template",
    "replace_all",
    "replace_main_only",
    "replace_detail_only",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    config = data.get("config") or {}
    runtime = data.get("runtime") or {}
    items = data.get("items")
    errors: list[str] = []
    warnings: list[str] = []

    if int(data.get("schema_version", 1)) < 2:
        warnings.append("schema_version is V1; run prepare_run.py again for full recovery support")
    if config.get("save_mode") != "submit_off_shelf":
        errors.append("save_mode must be submit_off_shelf")
    if not re.fullmatch(r"\d+", str(config.get("template_ware_id", ""))):
        errors.append("template_ware_id must contain digits only")
    if config.get("return_policy") != REQUIRED_RETURN_POLICY:
        errors.append(f"return_policy must be {REQUIRED_RETURN_POLICY}")
    if config.get("restrict_special_vat_invoice") is not True:
        errors.append("restrict_special_vat_invoice must be true")
    if runtime and runtime.get("recommended_mode") not in {"safe", "fast"}:
        errors.append("runtime.recommended_mode must be safe or fast")
    if not isinstance(items, list) or not items:
        errors.append("items must be a non-empty array")
        items = []

    sequences: set[int] = set()
    ware_ids: set[str] = set()
    for item in items:
        seq = item.get("sequence")
        if not isinstance(seq, int) or seq in sequences:
            errors.append(f"invalid or duplicate sequence: {seq}")
        sequences.add(seq)

        strategy = item.get("image_strategy", config.get("image_strategy", "replace_all"))
        if strategy not in IMAGE_STRATEGIES:
            errors.append(f"sequence {seq}: invalid image_strategy {strategy}")
        main_images = item.get("main_images") or (
            [item.get("final_image")] if item.get("final_image") else []
        )
        detail_images = item.get("detail_images") or []
        if strategy in {"replace_all", "replace_main_only"} and not main_images:
            errors.append(f"sequence {seq}: {strategy} requires main images")
        if strategy in {"replace_all", "replace_detail_only"} and not detail_images:
            errors.append(f"sequence {seq}: {strategy} requires detail images")
        if strategy == "inherit_template" and (main_images or detail_images):
            errors.append(f"sequence {seq}: inherit_template must not contain replacement images")
        if strategy == "replace_main_only" and detail_images:
            errors.append(f"sequence {seq}: replace_main_only must not contain detail images")
        if strategy == "replace_detail_only" and main_images:
            errors.append(f"sequence {seq}: replace_detail_only must not contain main images")
        for raw_image in [*(main_images or []), *(detail_images or [])]:
            image = Path(str(raw_image or ""))
            if image.suffix.lower() not in VALID_IMAGE_SUFFIXES or not image.is_file():
                errors.append(f"sequence {seq}: image missing or unsupported: {image}")

        status = item.get("status")
        if status not in VALID_STATUSES:
            errors.append(f"sequence {seq}: invalid status {status}")
        stage = item.get("stage", "completed" if status == "submitted_off_shelf" else "pending")
        if stage not in VALID_STAGES:
            errors.append(f"sequence {seq}: invalid stage {stage}")
        if status == "submission_unknown" and stage != "submit_clicked":
            errors.append(f"sequence {seq}: submission_unknown must use submit_clicked stage")

        ware_id = item.get("ware_id")
        if ware_id:
            if str(ware_id) in ware_ids:
                errors.append(f"duplicate ware_id: {ware_id}")
            ware_ids.add(str(ware_id))
        if status == "submitted_off_shelf" and not ware_id:
            errors.append(f"sequence {seq}: completed item has no ware_id")
        if not item.get("model"):
            warnings.append(f"sequence {seq}: model is empty")

    for warning in warnings:
        print("warning:", warning)
    if errors:
        for error in errors:
            print("error:", error)
        raise SystemExit(1)
    print(
        f"valid: {len(items)} products, store={config.get('store_name')}, "
        "adaptive_mode=safe+fast, network_recovery=enabled, "
        "mandatory_browser_gate=return_policy+special_vat_invoice"
    )


if __name__ == "__main__":
    main()
