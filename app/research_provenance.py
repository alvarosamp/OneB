"""Immutable provenance companions for research artifacts.

Research outputs are deliberately accompanied by a separate manifest instead
of embedding mutable metadata in the result JSON.  The manifest hashes the
result after it is written, making it possible to answer: which exact inputs,
code revision, parameters and data-quality gate produced this file?
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _package_versions() -> dict[str, str | None]:
    result = {}
    for package in ("numpy", "pandas", "yfinance", "httpx"):
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = None
    return result


def file_fingerprint(path: Path | str) -> dict:
    path = Path(path)
    return {
        "path": path.as_posix(),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() and path.is_file() else None,
        "sha256": _sha256(path),
    }


def write_manifest(
    output_path: Path | str,
    *,
    command: str,
    parameters: dict,
    input_paths: list[Path | str],
    data_gate: dict | None = None,
    extra: dict | None = None,
) -> Path:
    """Write `<artifact>.manifest.json` after the artifact itself exists."""
    output = Path(output_path)
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    payload = {
        "schema_version": "research-provenance-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "git_commit": _git_commit(),
        "parameters": parameters,
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "packages": _package_versions(),
        },
        "inputs": [file_fingerprint(path) for path in input_paths],
        "output": file_fingerprint(output),
        "data_gate": data_gate,
        "extra": extra or {},
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path
