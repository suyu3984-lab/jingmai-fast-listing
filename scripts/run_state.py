#!/usr/bin/env python3
"""Manage atomic, restart-safe checkpoints for a Jingmai off-shelf run."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ACTIVE_STAGES = ("pending", "claimed", "opened", "acquired", "filled", "gated", "submit_clicked", "completed")
STAGE_ORDER = {stage: index for index, stage in enumerate(ACTIVE_STAGES)}
VALID_STATUSES = {
    "pending",
    "in_progress",
    "network_interrupted",
    "submission_unknown",
    "failed",
    "submitted_off_shelf",
}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    migrate(data)
    return data


def save(path: Path, data: dict[str, Any]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def migrate(data: dict[str, Any]) -> None:
    data["schema_version"] = max(2, int(data.get("schema_version", 1)))
    runtime = data.setdefault("runtime", {})
    runtime.setdefault("recommended_mode", "safe")
    runtime.setdefault("profile_verified", False)
    runtime.setdefault("page_fingerprint", None)
    runtime.setdefault("last_verified_at", None)
    runtime.setdefault("invalidation_reason", "not_verified")
    runtime.setdefault("consecutive_successes", 0)
    runtime.setdefault("network_interruptions", 0)
    for item in data.get("items", []):
        status = item.setdefault("status", "pending")
        if status == "submitted_off_shelf":
            item.setdefault("stage", "completed")
        else:
            item.setdefault("stage", "pending")
        item.setdefault("execution_mode", None)
        item.setdefault("network_interruptions", 0)
        item.setdefault("last_url", None)
        item.setdefault("last_stage_at", item.get("updated_at"))
        item.setdefault("evidence", [])


def find_item(data: dict[str, Any], sequence: int) -> dict[str, Any]:
    for item in data.get("items", []):
        if item.get("sequence") == sequence:
            return item
    raise SystemExit(f"error: sequence {sequence} not found")


def recovery_action(item: dict[str, Any]) -> str:
    status = item.get("status", "pending")
    stage = item.get("stage", "pending")
    if status == "submitted_off_shelf":
        return "none_already_completed"
    if status == "submission_unknown" or stage == "submit_clicked":
        return "verify_existing_product_before_any_retry"
    if status == "network_interrupted":
        return "reconnect_then_reopen_from_verified_template"
    if status == "failed":
        return "inspect_failure_then_choose_retry"
    if status == "in_progress" and stage != "pending":
        return "after_restart_reopen_from_verified_template"
    return "start_from_verified_template"


def summary(data: dict[str, Any], start: int | None, end: int | None) -> dict[str, Any]:
    items = data.get("items", [])
    counts: dict[str, int] = {}
    stages: dict[str, int] = {}
    for item in items:
        status = item.get("status", "unknown")
        stage = item.get("stage", "unknown")
        counts[status] = counts.get(status, 0) + 1
        stages[stage] = stages.get(stage, 0) + 1
    missing: list[int] = []
    if start is not None and end is not None:
        present = {item.get("sequence") for item in items if item.get("status") == "submitted_off_shelf"}
        missing = [seq for seq in range(start, end + 1) if seq not in present]
    ware_ids = [str(item.get("ware_id")) for item in items if item.get("ware_id")]
    duplicates = sorted({ware_id for ware_id in ware_ids if ware_ids.count(ware_id) > 1})
    return {
        "total": len(items),
        "counts": counts,
        "stages": stages,
        "missing": missing,
        "duplicate_ware_ids": duplicates,
        "runtime": data.get("runtime", {}),
    }


def touch(item: dict[str, Any]) -> None:
    item["updated_at"] = now()
    item["last_stage_at"] = item["updated_at"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("pending", "summary", "profile-show"):
        command = sub.add_parser(name)
        command.add_argument("manifest", type=Path)
        if name == "summary":
            command.add_argument("--expected-start", type=int)
            command.add_argument("--expected-end", type=int)

    claim = sub.add_parser("claim")
    claim.add_argument("manifest", type=Path)
    claim.add_argument("--sequence", type=int, required=True)
    claim.add_argument("--mode", choices=("safe", "fast"))

    stage = sub.add_parser("stage")
    stage.add_argument("manifest", type=Path)
    stage.add_argument("--sequence", type=int, required=True)
    stage.add_argument("--stage", choices=ACTIVE_STAGES[2:-1], required=True)
    stage.add_argument("--url")

    interrupt = sub.add_parser("interrupt")
    interrupt.add_argument("manifest", type=Path)
    interrupt.add_argument("--sequence", type=int, required=True)
    interrupt.add_argument("--stage", choices=ACTIVE_STAGES[1:-1], required=True)
    interrupt.add_argument("--error", default="network_or_browser_disconnected")

    uncertain = sub.add_parser("uncertain")
    uncertain.add_argument("manifest", type=Path)
    uncertain.add_argument("--sequence", type=int, required=True)
    uncertain.add_argument("--error", default="submit_clicked_but_success_not_observed")

    resume_plan = sub.add_parser("resume-plan")
    resume_plan.add_argument("manifest", type=Path)
    resume_plan.add_argument("--sequence", type=int, required=True)

    clear_unknown = sub.add_parser("clear-unknown")
    clear_unknown.add_argument("manifest", type=Path)
    clear_unknown.add_argument("--sequence", type=int, required=True)
    clear_unknown.add_argument("--verified-not-created", action="store_true", required=True)

    record = sub.add_parser("record")
    record.add_argument("manifest", type=Path)
    record.add_argument("--sequence", type=int, required=True)
    record.add_argument("--ware-id", required=True)

    fail = sub.add_parser("fail")
    fail.add_argument("manifest", type=Path)
    fail.add_argument("--sequence", type=int, required=True)
    fail.add_argument("--error", required=True)

    profile_verify = sub.add_parser("profile-verify")
    profile_verify.add_argument("manifest", type=Path)
    profile_verify.add_argument("--fingerprint", required=True)
    profile_verify.add_argument("--allow-fast", action="store_true")

    profile_invalidate = sub.add_parser("profile-invalidate")
    profile_invalidate.add_argument("manifest", type=Path)
    profile_invalidate.add_argument("--reason", required=True)

    args = parser.parse_args()
    data = load(args.manifest)
    runtime = data["runtime"]

    if args.command == "pending":
        rows = [
            {
                "sequence": item["sequence"],
                "title": item["title"],
                "status": item["status"],
                "stage": item.get("stage"),
                "attempts": item.get("attempts", 0),
                "next_action": recovery_action(item),
            }
            for item in data.get("items", [])
            if item.get("status") != "submitted_off_shelf"
        ]
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    if args.command == "summary":
        if (args.expected_start is None) != (args.expected_end is None):
            raise SystemExit("error: provide both expected range values")
        print(json.dumps(summary(data, args.expected_start, args.expected_end), ensure_ascii=False, indent=2))
        return

    if args.command == "profile-show":
        print(json.dumps(runtime, ensure_ascii=False, indent=2))
        return

    if args.command == "profile-verify":
        previous_fingerprint = runtime.get("page_fingerprint")
        if args.allow_fast and previous_fingerprint != args.fingerprint:
            raise SystemExit(
                "error: --allow-fast requires the fresh fingerprint to match the previously stored fingerprint"
            )
        runtime["page_fingerprint"] = args.fingerprint
        runtime["profile_verified"] = True
        runtime["last_verified_at"] = now()
        runtime["invalidation_reason"] = None
        runtime["recommended_mode"] = "fast" if args.allow_fast else "safe"
        save(args.manifest, data)
        print(json.dumps(runtime, ensure_ascii=False, indent=2))
        return

    if args.command == "profile-invalidate":
        runtime["profile_verified"] = False
        runtime["recommended_mode"] = "safe"
        runtime["invalidation_reason"] = args.reason
        runtime["consecutive_successes"] = 0
        save(args.manifest, data)
        print(json.dumps(runtime, ensure_ascii=False, indent=2))
        return

    item = find_item(data, args.sequence)

    if args.command == "resume-plan":
        print(
            json.dumps(
                {
                    "sequence": item["sequence"],
                    "status": item["status"],
                    "stage": item.get("stage"),
                    "next_action": recovery_action(item),
                    "recommended_mode": runtime.get("recommended_mode", "safe"),
                    "last_url": item.get("last_url"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "claim":
        if item.get("status") == "submitted_off_shelf":
            raise SystemExit(f"error: sequence {args.sequence} already submitted as {item.get('ware_id')}")
        if item.get("status") == "submission_unknown" or item.get("stage") == "submit_clicked":
            raise SystemExit("error: verify whether the product already exists before claiming")
        mode = args.mode or runtime.get("recommended_mode", "safe")
        if mode == "fast" and not runtime.get("profile_verified"):
            mode = "safe"
        item["status"] = "in_progress"
        item["stage"] = "claimed"
        item["execution_mode"] = mode
        item["attempts"] = int(item.get("attempts", 0)) + 1
        item["error"] = None
        item["last_url"] = None
        touch(item)

    elif args.command == "stage":
        if item.get("status") != "in_progress":
            raise SystemExit("error: stage updates require in_progress status")
        old_stage = item.get("stage", "pending")
        if STAGE_ORDER[args.stage] < STAGE_ORDER.get(old_stage, 0):
            raise SystemExit(f"error: cannot move stage backwards from {old_stage} to {args.stage}")
        item["stage"] = args.stage
        if args.url:
            item["last_url"] = args.url
        touch(item)

    elif args.command == "interrupt":
        item["stage"] = args.stage
        item["error"] = args.error
        item["network_interruptions"] = int(item.get("network_interruptions", 0)) + 1
        runtime["network_interruptions"] = int(runtime.get("network_interruptions", 0)) + 1
        runtime["recommended_mode"] = "safe"
        runtime["profile_verified"] = False
        runtime["invalidation_reason"] = args.error
        runtime["consecutive_successes"] = 0
        if args.stage == "submit_clicked":
            item["status"] = "submission_unknown"
        else:
            item["status"] = "network_interrupted"
        touch(item)

    elif args.command == "uncertain":
        item["status"] = "submission_unknown"
        item["stage"] = "submit_clicked"
        item["error"] = args.error
        runtime["recommended_mode"] = "safe"
        runtime["profile_verified"] = False
        runtime["invalidation_reason"] = args.error
        runtime["consecutive_successes"] = 0
        touch(item)

    elif args.command == "clear-unknown":
        if item.get("status") != "submission_unknown":
            raise SystemExit("error: item is not submission_unknown")
        if not args.verified_not_created:
            raise SystemExit("error: --verified-not-created is required")
        item["status"] = "pending"
        item["stage"] = "pending"
        item["error"] = None
        item["last_url"] = None
        item.setdefault("evidence", []).append("verified_not_created_before_retry")
        touch(item)

    elif args.command == "record":
        ware_id = str(args.ware_id).strip()
        if not ware_id.isdigit():
            raise SystemExit("error: ware-id must contain digits only")
        existing = item.get("ware_id")
        if item.get("status") == "submitted_off_shelf" and existing != ware_id:
            raise SystemExit(f"error: sequence already recorded as {existing}")
        for other in data.get("items", []):
            if other is not item and str(other.get("ware_id") or "") == ware_id:
                raise SystemExit(f"error: ware-id already belongs to sequence {other.get('sequence')}")
        item["status"] = "submitted_off_shelf"
        item["stage"] = "completed"
        item["ware_id"] = ware_id
        item["error"] = None
        item.setdefault("evidence", []).append(f"JD{ware_id}, publish-success")
        runtime["consecutive_successes"] = int(runtime.get("consecutive_successes", 0)) + 1
        if runtime.get("profile_verified"):
            runtime["recommended_mode"] = "fast"
        touch(item)

    elif args.command == "fail":
        item["status"] = "failed"
        item["error"] = args.error
        runtime["recommended_mode"] = "safe"
        runtime["consecutive_successes"] = 0
        touch(item)

    if item.get("status") not in VALID_STATUSES:
        raise SystemExit(f"error: invalid status {item.get('status')}")
    save(args.manifest, data)
    print(
        json.dumps(
            {
                "sequence": item["sequence"],
                "status": item["status"],
                "stage": item.get("stage"),
                "mode": item.get("execution_mode"),
                "ware_id": item.get("ware_id"),
                "next_action": recovery_action(item),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
