#!/usr/bin/env python3
"""Metadata sidecar helpers for workflow JSON artifacts."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any


def meta_path_for(artifact_path: str) -> str:
    root, ext = os.path.splitext(artifact_path)
    if ext.lower() == ".json":
        return root + ".meta.json"
    return artifact_path + ".meta.json"


def sha256_file(path: str) -> str | None:
    if not path or not os.path.exists(path) or not os.path.isfile(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_json_optional(path: str | None) -> dict[str, Any] | None:
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else None


def infer_manifest_path(artifact_path: str) -> str | None:
    directory = os.path.dirname(os.path.abspath(artifact_path))
    candidate = os.path.join(directory, "review-manifest.json")
    return candidate if os.path.exists(candidate) else None


def manifest_run_id(manifest: dict[str, Any] | None) -> str | None:
    if not manifest:
        return None
    if manifest.get("run_id"):
        return str(manifest["run_id"])
    matter_id = manifest.get("matter_id")
    round_id = manifest.get("round")
    if matter_id is not None:
        return f"{matter_id}:round-{round_id or 1}"
    return None


def manifest_source_hash(manifest: dict[str, Any] | None) -> str | None:
    if not manifest:
        return None
    for container_key in ("source", "document"):
        container = manifest.get(container_key)
        if isinstance(container, dict):
            for hash_key in ("sha256", "source_doc_hash", "hash"):
                if container.get(hash_key):
                    value = str(container[hash_key])
                    return value if value.startswith("sha256:") else "sha256:" + value
    value = manifest.get("source_doc_hash")
    if value:
        text = str(value)
        return text if text.startswith("sha256:") else "sha256:" + text
    return None


def infer_source_hash(
    *,
    artifact_path: str,
    manifest: dict[str, Any] | None = None,
    source_file: str | None = None,
) -> str | None:
    from_manifest = manifest_source_hash(manifest)
    if from_manifest:
        return from_manifest
    if source_file and os.path.exists(source_file):
        return sha256_file(source_file)
    return None


def build_artifact_meta(
    artifact_path: str,
    *,
    artifact_type: str,
    producer: dict[str, Any] | None = None,
    manifest_path: str | None = None,
    source_file: str | None = None,
) -> dict[str, Any]:
    manifest_path = manifest_path or infer_manifest_path(artifact_path)
    manifest = load_json_optional(manifest_path)
    return {
        "schema_version": "2026-04-24",
        "artifact_type": artifact_type,
        "artifact_path": os.path.basename(artifact_path),
        "artifact_sha256": sha256_file(artifact_path),
        "run_id": manifest_run_id(manifest),
        "source_doc_hash": infer_source_hash(
            artifact_path=artifact_path,
            manifest=manifest,
            source_file=source_file,
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "producer": producer or {},
    }


def write_artifact_meta(
    artifact_path: str,
    *,
    artifact_type: str,
    producer: dict[str, Any] | None = None,
    manifest_path: str | None = None,
    source_file: str | None = None,
) -> str:
    meta_path = meta_path_for(artifact_path)
    meta = build_artifact_meta(
        artifact_path,
        artifact_type=artifact_type,
        producer=producer,
        manifest_path=manifest_path,
        source_file=source_file,
    )
    meta_dir = os.path.dirname(meta_path)
    if meta_dir:
        os.makedirs(meta_dir, exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2, ensure_ascii=False)
    return meta_path


def validate_artifact(
    artifact_path: str,
    *,
    artifact_type: str | None = None,
    manifest_path: str | None = None,
    require_meta: bool = True,
) -> list[str]:
    errors: list[str] = []
    if not os.path.exists(artifact_path):
        return [f"artifact missing: {artifact_path}"]
    try:
        with open(artifact_path, "r", encoding="utf-8") as handle:
            json.load(handle)
    except Exception as exc:
        errors.append(f"artifact is not valid JSON: {exc}")

    meta_path = meta_path_for(artifact_path)
    if not os.path.exists(meta_path):
        if require_meta:
            errors.append(f"meta missing: {meta_path}")
        return errors

    try:
        with open(meta_path, "r", encoding="utf-8") as handle:
            meta = json.load(handle)
    except Exception as exc:
        errors.append(f"meta is not valid JSON: {exc}")
        return errors

    if artifact_type and meta.get("artifact_type") != artifact_type:
        errors.append(f"artifact_type mismatch: expected {artifact_type}, got {meta.get('artifact_type')}")
    actual_hash = sha256_file(artifact_path)
    if meta.get("artifact_sha256") != actual_hash:
        errors.append("artifact_sha256 mismatch")

    manifest_path = manifest_path or infer_manifest_path(artifact_path)
    manifest = load_json_optional(manifest_path)
    expected_run_id = manifest_run_id(manifest)
    if expected_run_id and meta.get("run_id") != expected_run_id:
        errors.append(f"run_id mismatch: expected {expected_run_id}, got {meta.get('run_id')}")
    expected_source_hash = manifest_source_hash(manifest)
    if expected_source_hash and meta.get("source_doc_hash") != expected_source_hash:
        errors.append("source_doc_hash mismatch")
    return errors


def validate_artifacts(
    entries: list[tuple[str | None, str | None]],
    *,
    require_meta: bool = False,
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for artifact_path, artifact_type in entries:
        if not artifact_path or not os.path.exists(artifact_path):
            continue
        for error in validate_artifact(
            artifact_path,
            artifact_type=artifact_type,
            require_meta=require_meta,
        ):
            errors.append({"path": artifact_path, "error": error})
    return errors
