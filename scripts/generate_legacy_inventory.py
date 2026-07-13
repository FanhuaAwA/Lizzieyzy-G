#!/usr/bin/env python3
"""Generate and verify the read-only LizzieYzy legacy inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEGACY_ROOT = REPOSITORY_ROOT.parent / "lizzieyzy-next-main"
DEFAULT_MATRIX = REPOSITORY_ROOT / "migration" / "equivalence-matrix.json"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "migration" / "legacy-inventory.json"

JSON_APIS = (
    "optBoolean",
    "optInt",
    "optLong",
    "optDouble",
    "optString",
    "optJSONObject",
    "optJSONArray",
    "getBoolean",
    "getInt",
    "getLong",
    "getDouble",
    "getString",
    "getJSONObject",
    "getJSONArray",
    "put",
    "remove",
    "has",
)
CONFIG_CALL = re.compile(
    rf"(?P<receiver>(?:[A-Za-z_$][\w$]*\.)*[A-Za-z_$][\w$]*)\s*\.\s*"
    rf"(?P<api>{'|'.join(JSON_APIS)})\s*\(\s*\"(?P<key>(?:\\.|[^\"\\])*)\""
)
MENU_RESOURCE_CALL = re.compile(
    r"(?:Lizzie\.)?resourceBundle\.getString\s*\(\s*\"(?P<key>Menu\.[^\"]+)\""
)
PERSISTENT_RECEIVER_SUFFIXES = (
    ".uiConfig",
    ".leelazConfig",
    ".saveBoardConfig",
    ".persistedUi",
    ".persisted",
)
PERSISTENT_RECEIVERS = {
    "uiConfig",
    "leelazConfig",
    "saveBoardConfig",
    "persistedUi",
    "persisted",
    "theme.config",
    "config.uiConfig",
    "config.persistedUi",
    "Lizzie.config.config",
}
REQUIRED_ROW_FIELDS = {
    "id",
    "category",
    "legacy_entry",
    "legacy_shortcuts",
    "java_evidence",
    "config_keys",
    "inputs_preconditions",
    "success_behavior",
    "failure_cancel_behavior",
    "data_io",
    "external_dependencies",
    "target_modules",
    "automated_evidence",
    "manual_acceptance",
    "status",
    "evidence",
}
ALLOWED_STATUSES = (
    "未盘点",
    "已盘点",
    "实施中",
    "已实现待验证",
    "已验证",
    "用户批准不迁移",
)
ALLOWED_TARGET_MODULES = {"Lizzie.Core", "Lizzie.Engine", "Lizzie.Desktop"}


def strip_java_comments(source: str) -> str:
    """Remove Java comments while preserving strings, chars, and line numbers."""
    result: list[str] = []
    index = 0
    state = "code"
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""

        if state == "code":
            if char == "/" and following == "/":
                result.extend((" ", " "))
                index += 2
                state = "line_comment"
                continue
            if char == "/" and following == "*":
                result.extend((" ", " "))
                index += 2
                state = "block_comment"
                continue
            result.append(char)
            if char == '"':
                state = "string"
            elif char == "'":
                state = "char"
            index += 1
            continue

        if state == "line_comment":
            result.append("\n" if char == "\n" else " ")
            if char == "\n":
                state = "code"
            index += 1
            continue

        if state == "block_comment":
            if char == "*" and following == "/":
                result.extend((" ", " "))
                index += 2
                state = "code"
                continue
            result.append("\n" if char == "\n" else " ")
            index += 1
            continue

        result.append(char)
        if char == "\\" and following:
            result.append(following)
            index += 2
            continue
        if state == "string" and char == '"':
            state = "code"
        elif state == "char" and char == "'":
            state = "code"
        index += 1

    return "".join(result)


def validate_comment_stripper() -> None:
    sample = 'call("//"); // hidden\nnext(\'/*\'); /* gone\ncontinued */ tail();\n'
    stripped = strip_java_comments(sample)
    if '"//"' not in stripped or "'/*'" not in stripped or "hidden" in stripped:
        raise ValueError("Java comment stripper self-check failed")
    if stripped.count("\n") != sample.count("\n") or "tail();" not in stripped:
        raise ValueError("Java comment stripper did not preserve line structure")


def line_number(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def source_fingerprint(legacy_root: Path) -> tuple[str, list[Path]]:
    files = sorted(
        (path for path in (legacy_root / "src").rglob("*") if path.is_file()),
        key=lambda path: relative_path(path, legacy_root),
    )
    aggregate = hashlib.sha256()
    for path in files:
        aggregate.update(relative_path(path, legacy_root).encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
        aggregate.update(b"\n")
    return aggregate.hexdigest(), files


def is_persistent_config_call(path: Path, receiver: str) -> bool:
    if path.name == "Config.java":
        return receiver != "Lizzie.resourceBundle"
    return receiver in PERSISTENT_RECEIVERS or receiver.endswith(PERSISTENT_RECEIVER_SUFFIXES)


def collect_config_references(
    legacy_root: Path, main_java_files: list[Path]
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    references: dict[str, list[dict[str, Any]]] = defaultdict(list)
    commented_only: set[str] = set()

    for path in main_java_files:
        raw = path.read_text(encoding="utf-8", errors="replace")
        active = strip_java_comments(raw)
        active_keys: set[str] = set()
        for match in CONFIG_CALL.finditer(active):
            receiver = match.group("receiver")
            if not is_persistent_config_call(path, receiver):
                continue
            key = bytes(match.group("key"), "utf-8").decode("unicode_escape")
            active_keys.add(key)
            references[key].append(
                {
                    "path": relative_path(path, legacy_root),
                    "line": line_number(active, match.start()),
                    "receiver": receiver,
                    "api": match.group("api"),
                }
            )

        if path.name == "Config.java":
            for match in CONFIG_CALL.finditer(raw):
                receiver = match.group("receiver")
                if receiver == "Lizzie.resourceBundle":
                    continue
                key = bytes(match.group("key"), "utf-8").decode("unicode_escape")
                if key not in active_keys:
                    commented_only.add(key)

    for entries in references.values():
        entries.sort(key=lambda entry: (entry["path"], entry["line"], entry["receiver"], entry["api"]))
    return dict(sorted(references.items())), sorted(commented_only)


def collect_menu_resources(legacy_root: Path) -> dict[str, Any]:
    menu_path = legacy_root / "src/main/java/featurecat/lizzie/gui/Menu.java"
    source = strip_java_comments(menu_path.read_text(encoding="utf-8", errors="replace"))
    references: dict[str, list[int]] = defaultdict(list)
    for match in MENU_RESOURCE_CALL.finditer(source):
        references[match.group("key")].append(line_number(source, match.start()))
    return {
        "source": relative_path(menu_path, legacy_root),
        "unique_resource_keys": len(references),
        "resource_references": sum(len(lines) for lines in references.values()),
        "set_accelerator_calls": len(re.findall(r"\.setAccelerator\s*\(", source)),
        "keys": [
            {"key": key, "lines": lines} for key, lines in sorted(references.items())
        ],
    }


def read_legacy_version(legacy_root: Path) -> str:
    document = ET.parse(legacy_root / "pom.xml")
    root = document.getroot()
    namespace = {"m": "http://maven.apache.org/POM/4.0.0"}
    value = root.findtext("m:version", namespaces=namespace)
    if not value:
        raise ValueError("Legacy Maven version is missing")
    return value


def validate_evidence_entry(entry: Any, legacy_root: Path, row_id: str) -> None:
    if not isinstance(entry, dict) or set(entry) != {"path", "symbol"}:
        raise ValueError(f"{row_id}: evidence entries require exactly path and symbol")
    path = legacy_root / entry["path"]
    if not path.is_file():
        raise ValueError(f"{row_id}: evidence path does not exist: {entry['path']}")
    if entry["symbol"] not in path.read_text(encoding="utf-8", errors="replace"):
        raise ValueError(f"{row_id}: symbol {entry['symbol']!r} not found in {entry['path']}")


def validate_matrix(
    matrix: dict[str, Any], legacy_root: Path, config_keys: set[str], fingerprint: str
) -> dict[str, list[str]]:
    if matrix.get("schema_version") != 1:
        raise ValueError("Matrix schema_version must be 1")
    allowed_statuses = matrix.get("allowed_statuses")
    if allowed_statuses != list(ALLOWED_STATUSES):
        raise ValueError("Matrix allowed_statuses differ from the repository contract")
    baseline = matrix.get("legacy_baseline", {})
    if baseline.get("source_fingerprint_sha256") != fingerprint:
        raise ValueError("Matrix baseline fingerprint does not match the legacy source tree")
    if baseline.get("version") != read_legacy_version(legacy_root):
        raise ValueError("Matrix baseline version does not match pom.xml")

    matrix_ids_by_key: dict[str, list[str]] = defaultdict(list)
    seen_ids: set[str] = set()
    rows = matrix.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Matrix rows must be a non-empty list")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Every matrix row must be an object")
        missing = REQUIRED_ROW_FIELDS - set(row)
        extra = set(row) - REQUIRED_ROW_FIELDS
        if missing or extra:
            raise ValueError(
                f"Matrix row fields differ for {row.get('id', '<unknown>')}: "
                f"missing={sorted(missing)}, extra={sorted(extra)}"
            )
        row_id = row["id"]
        if not isinstance(row_id, str) or not row_id or row_id in seen_ids:
            raise ValueError(f"Matrix row id is empty or duplicated: {row_id!r}")
        seen_ids.add(row_id)
        if row["status"] not in allowed_statuses:
            raise ValueError(f"{row_id}: unsupported status {row['status']!r}")
        for field in (
            "legacy_shortcuts",
            "java_evidence",
            "config_keys",
            "external_dependencies",
            "target_modules",
            "automated_evidence",
        ):
            if not isinstance(row[field], list):
                raise ValueError(f"{row_id}: {field} must be a list")
        for field in REQUIRED_ROW_FIELDS - {
            "legacy_shortcuts",
            "java_evidence",
            "config_keys",
            "external_dependencies",
            "target_modules",
            "automated_evidence",
        }:
            if not isinstance(row[field], str) or not row[field].strip():
                raise ValueError(f"{row_id}: {field} must be a non-empty string")
        if not re.fullmatch(r"[A-Z]+(?:-[A-Z]+)*-\d{3}", row_id):
            raise ValueError(f"{row_id}: id must end in a three-digit stable sequence")
        if not row["java_evidence"]:
            raise ValueError(f"{row_id}: java_evidence must not be empty")
        if not row["target_modules"] or not set(row["target_modules"]) <= ALLOWED_TARGET_MODULES:
            raise ValueError(f"{row_id}: target_modules contain an unsupported module")
        for field in ("legacy_shortcuts", "config_keys", "external_dependencies", "target_modules"):
            if len(row[field]) != len(set(row[field])):
                raise ValueError(f"{row_id}: {field} contains duplicate values")
        for entry in row["java_evidence"] + row["automated_evidence"]:
            validate_evidence_entry(entry, legacy_root, row_id)
        for key in row["config_keys"]:
            if key not in config_keys:
                raise ValueError(f"{row_id}: config key is outside the active literal inventory: {key}")
            matrix_ids_by_key[key].append(row_id)
    return {key: sorted(ids) for key, ids in matrix_ids_by_key.items()}


def build_inventory(legacy_root: Path, matrix_path: Path) -> dict[str, Any]:
    validate_comment_stripper()
    if not legacy_root.is_dir():
        raise ValueError(f"Legacy root does not exist: {legacy_root}")
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    fingerprint, source_files = source_fingerprint(legacy_root)
    main_java_files = sorted((legacy_root / "src/main/java").rglob("*.java"))
    test_java_files = sorted((legacy_root / "src/test/java").rglob("*.java"))
    config_references, commented_only = collect_config_references(legacy_root, main_java_files)
    matrix_ids_by_key = validate_matrix(
        matrix, legacy_root, set(config_references), fingerprint
    )
    config_entries = [
        {
            "key": key,
            "reference_count": len(references),
            "matrix_ids": matrix_ids_by_key.get(key, []),
            "references": references,
        }
        for key, references in config_references.items()
    ]
    mapped_keys = sum(bool(entry["matrix_ids"]) for entry in config_entries)

    return {
        "schema_version": 1,
        "source": {
            "root": "../lizzieyzy-next-main",
            "version": read_legacy_version(legacy_root),
            "fingerprint_algorithm": "SHA-256 of sorted src-relative-to-root paths, NUL, per-file SHA-256 hex, LF",
            "fingerprint_sha256": fingerprint,
            "source_files": len(source_files),
            "main_java_files": len(main_java_files),
            "test_java_files": len(test_java_files),
        },
        "scope_notes": [
            "The legacy tree is read-only; this file is generated in the new repository.",
            "Config keys are active string-literal leaf keys on explicit persistent JSON receivers.",
            "Nested canonical JSON paths, computed keys, and semantic use-case mapping remain T-003 work.",
            "Commented-only Config.java keys are evidence, not active migration requirements.",
        ],
        "matrix_summary": {
            "rows": len(matrix["rows"]),
            "statuses": {
                status: sum(row["status"] == status for row in matrix["rows"])
                for status in matrix["allowed_statuses"]
            },
            "active_config_leaf_keys": len(config_entries),
            "mapped_config_leaf_keys": mapped_keys,
            "unmapped_config_leaf_keys": len(config_entries) - mapped_keys,
        },
        "config": {
            "active_literal_leaf_keys": len(config_entries),
            "active_literal_references": sum(entry["reference_count"] for entry in config_entries),
            "commented_only_config_java_keys": commented_only,
            "keys": config_entries,
        },
        "menu": collect_menu_resources(legacy_root),
        "tests": {
            "java_files": [relative_path(path, legacy_root) for path in test_java_files]
        },
    }


def serialized_inventory(legacy_root: Path, matrix_path: Path) -> str:
    return json.dumps(build_inventory(legacy_root, matrix_path), ensure_ascii=False, indent=2) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-root", type=Path, default=DEFAULT_LEGACY_ROOT)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Fail if the output is missing or stale")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        expected = serialized_inventory(args.legacy_root.resolve(), args.matrix.resolve())
        if args.check:
            if not args.output.is_file():
                print(f"Inventory is missing: {args.output}", file=sys.stderr)
                return 1
            if args.output.read_text(encoding="utf-8") != expected:
                print(f"Inventory is stale: {args.output}", file=sys.stderr)
                return 1
            print(f"Inventory is current: {args.output}")
            return 0

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(expected, encoding="utf-8", newline="\n")
        print(f"Wrote {args.output}")
        return 0
    except (OSError, ValueError, ET.ParseError, json.JSONDecodeError) as error:
        print(f"Inventory generation failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
