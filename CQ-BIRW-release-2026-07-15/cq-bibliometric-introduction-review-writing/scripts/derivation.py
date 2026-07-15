#!/usr/bin/env python3
"""Safe derivative-task creation with resumable workflow inheritance."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from common import ensure_task, file_sha256, read_json, utc_stamp, write_json


INHERITED_FIELDS = (
    "acquisition_mode", "metadata_enrichment", "language", "output_language",
    "theory_support_mode", "theory_support_non_blocking", "v5_workflow_enforced",
    "writing_audit_required", "skill_schema_version", "data_schema_version",
)


def derive_task(source_root: Path, output_root: Path, derivation_type: str, overrides: dict[str, Any] | None = None) -> tuple[Path, dict[str, Any]]:
    source_root, output_root = source_root.resolve(), output_root.expanduser().resolve()
    output_root = ensure_task(output_root)
    shutil.copytree(source_root / "00_plan", output_root / "00_plan", dirs_exist_ok=True)
    source_manifest = read_json(source_root / "manifest.json", {})
    target_manifest = read_json(output_root / "manifest.json", {"created_at": utc_stamp(), "events": []})
    inherited = []
    for key in INHERITED_FIELDS:
        if key in source_manifest:
            target_manifest[key] = source_manifest[key]; inherited.append(key)
    parent_hash = file_sha256(source_root / "manifest.json") if (source_root / "manifest.json").exists() else ""
    target_manifest.update({
        "parent_task": str(source_root), "source_task": str(source_root), "derivation_type": derivation_type,
        "derivation": {"type": derivation_type, "parent_manifest_sha256": parent_hash, "inherited_fields": inherited, "derived_at": utc_stamp()},
    })
    target_manifest.update(overrides or {})
    # Deliberately do not inherit transient failures, validation hashes, or credentials.
    write_json(output_root / "manifest.json", target_manifest)
    return output_root, target_manifest


def inherited_manifest(root: Path, manifest: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Read missing stable fields from a parent without mutating historical data."""
    parent = manifest.get("parent_task") or manifest.get("source_task")
    if not parent: return manifest, []
    parent_manifest = read_json(Path(parent) / "manifest.json", {})
    combined, inherited = dict(manifest), []
    for key in INHERITED_FIELDS:
        if key not in combined and key in parent_manifest:
            combined[key] = parent_manifest[key]; inherited.append(key)
    return combined, inherited
