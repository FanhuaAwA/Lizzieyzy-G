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
    r"(?:Lizzie\.)?resourceBundle\.getString\s*\(\s*\"(?P<key>(?:Menu|menu)\.[^\"]+)\""
)
MENU_ACCELERATOR_CALL = re.compile(
    r"(?:(?P<windows_guard>if\s*\(\s*OS\.isWindows\(\)\s*\)\s*\{\s*))?"
    r"(?P<item>[A-Za-z_$][\w$]*)\.setAccelerator\s*\(\s*KeyStroke\.getKeyStroke\s*\(\s*"
    r"KeyEvent\.VK_(?P<key>[A-Z0-9_]+)\s*,\s*InputEvent\.(?P<modifier>[A-Z_]+)_DOWN_MASK"
    r"\s*\)\s*\)"
)
MENU_LITERAL_CONSTRUCTOR_CALL = re.compile(
    r"new\s+(?P<type>JFontMenu|JFontMenuItem|JFontCheckBoxMenuItem|"
    r"JMenu|JMenuItem|JCheckBoxMenuItem)\s*\(\s*"
    r'"(?P<label>(?:\\.|[^"\\])*)"'
)
ANY_MENU_LITERAL_CONSTRUCTOR_CALL = re.compile(
    r"new\s+[A-Za-z_$][\w$]*(?:Menu|MenuItem)\s*\(\s*\""
)
INPUT_KEY_METHOD = re.compile(
    r"public\s+void\s+(?P<event>keyPressed|keyReleased)\s*"
    r"\(\s*KeyEvent\s+e\s*\)\s*\{"
)
INPUT_KEY_CASE = re.compile(r"\bcase\s+(?P<key>VK_[A-Z0-9_]+)\s*:")
INPUT_MODIFIER_CHECKS = (
    ("Alt", re.compile(r"\be\.isAltDown\s*\(\s*\)")),
    ("Control", re.compile(r"\be\.isControlDown\s*\(\s*\)")),
    ("ControlOrMetaOnMac", re.compile(r"\bcontrolIsPressed\s*\(\s*e\s*\)")),
    ("Meta", re.compile(r"\be\.isMetaDown\s*\(\s*\)")),
    ("Shift", re.compile(r"\be\.isShiftDown\s*\(\s*\)")),
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
    "legacy_menu_keys",
    "legacy_menu_labels",
    "legacy_shortcuts",
    "legacy_input_cases",
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


def closing_brace(source: str, open_brace: int) -> int:
    depth = 0
    state = "code"
    index = open_brace
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char == '"':
                state = "string"
            elif char == "'":
                state = "char"
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return index
        elif char == "\\" and following:
            index += 1
        elif state == "string" and char == '"':
            state = "code"
        elif state == "char" and char == "'":
            state = "code"
        index += 1
    raise ValueError("Unbalanced Java braces while collecting input cases")


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
    literal_references: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for match in MENU_LITERAL_CONSTRUCTOR_CALL.finditer(source):
        literal_references[match.group("label")].append(
            {
                "type": match.group("type"),
                "line": line_number(source, match.start()),
            }
        )
    if sum(map(len, literal_references.values())) != len(
        ANY_MENU_LITERAL_CONSTRUCTOR_CALL.findall(source)
    ):
        raise ValueError("Menu.java contains an unsupported literal menu constructor")
    accelerators = [
        {
            "item": match.group("item"),
            "shortcut": f'{match.group("modifier").title()}+{match.group("key")}',
            "platform": "Windows" if match.group("windows_guard") else "All",
            "line": line_number(source, match.start("item")),
        }
        for match in MENU_ACCELERATOR_CALL.finditer(source)
    ]
    accelerator_calls = len(re.findall(r"\.setAccelerator\s*\(", source))
    if len(accelerators) != accelerator_calls:
        raise ValueError("Menu.java contains an unsupported setAccelerator form")
    return {
        "source": relative_path(menu_path, legacy_root),
        "unique_resource_keys": len(references),
        "resource_references": sum(len(lines) for lines in references.values()),
        "unique_literal_labels": len(literal_references),
        "literal_label_references": sum(map(len, literal_references.values())),
        "set_accelerator_calls": accelerator_calls,
        "accelerators": accelerators,
        "literal_labels": [
            {"label": label, "references": entries}
            for label, entries in sorted(literal_references.items())
        ],
        "keys": [
            {"key": key, "lines": lines} for key, lines in sorted(references.items())
        ],
    }


def collect_input_cases(legacy_root: Path) -> dict[str, Any]:
    input_path = legacy_root / "src/main/java/featurecat/lizzie/gui/Input.java"
    source = strip_java_comments(input_path.read_text(encoding="utf-8", errors="replace"))
    cases: list[dict[str, Any]] = []
    seen_events: set[str] = set()
    for method_match in INPUT_KEY_METHOD.finditer(source):
        event = method_match.group("event")
        if event in seen_events:
            raise ValueError(f"Input.java contains duplicate {event} methods")
        seen_events.add(event)
        open_brace = method_match.end() - 1
        method_end = closing_brace(source, open_brace)
        case_matches = list(INPUT_KEY_CASE.finditer(source, open_brace + 1, method_end))
        for index, case_match in enumerate(case_matches):
            segment_end = (
                case_matches[index + 1].start() if index + 1 < len(case_matches) else method_end
            )
            segment = source[case_match.end() : segment_end]
            cases.append(
                {
                    "case": f'{event}:{case_match.group("key")}',
                    "event": event,
                    "key": case_match.group("key"),
                    "line": line_number(source, case_match.start()),
                    "modifier_checks": [
                        name for name, pattern in INPUT_MODIFIER_CHECKS if pattern.search(segment)
                    ],
                }
            )

    expected_events = {"keyPressed", "keyReleased"}
    if seen_events != expected_events:
        raise ValueError(f"Input.java key methods differ from expected: {sorted(seen_events)}")
    if len(cases) != len(INPUT_KEY_CASE.findall(source)):
        raise ValueError("Input.java contains a VK_* case outside the indexed key methods")
    case_ids = [entry["case"] for entry in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Input.java contains duplicate key cases in an indexed method")
    return {
        "source": relative_path(input_path, legacy_root),
        "active_key_cases": len(cases),
        "events": {
            event: sum(entry["event"] == event for entry in cases)
            for event in sorted(expected_events)
        },
        "cases": cases,
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
    matrix: dict[str, Any],
    legacy_root: Path,
    config_keys: set[str],
    menu_keys: set[str],
    menu_labels: set[str],
    menu_shortcuts: set[str],
    input_cases: set[str],
    fingerprint: str,
) -> tuple[
    dict[str, list[str]],
    dict[str, list[str]],
    dict[str, list[str]],
    dict[str, list[str]],
    dict[str, list[str]],
]:
    if matrix.get("schema_version") != 3:
        raise ValueError("Matrix schema_version must be 3")
    allowed_statuses = matrix.get("allowed_statuses")
    if allowed_statuses != list(ALLOWED_STATUSES):
        raise ValueError("Matrix allowed_statuses differ from the repository contract")
    baseline = matrix.get("legacy_baseline", {})
    if baseline.get("source_fingerprint_sha256") != fingerprint:
        raise ValueError("Matrix baseline fingerprint does not match the legacy source tree")
    if baseline.get("version") != read_legacy_version(legacy_root):
        raise ValueError("Matrix baseline version does not match pom.xml")

    matrix_ids_by_config_key: dict[str, list[str]] = defaultdict(list)
    matrix_ids_by_menu_key: dict[str, list[str]] = defaultdict(list)
    matrix_ids_by_menu_label: dict[str, list[str]] = defaultdict(list)
    matrix_ids_by_shortcut: dict[str, list[str]] = defaultdict(list)
    matrix_ids_by_input_case: dict[str, list[str]] = defaultdict(list)
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
            "legacy_menu_keys",
            "legacy_menu_labels",
            "legacy_shortcuts",
            "legacy_input_cases",
            "java_evidence",
            "config_keys",
            "external_dependencies",
            "target_modules",
            "automated_evidence",
        ):
            if not isinstance(row[field], list):
                raise ValueError(f"{row_id}: {field} must be a list")
        for field in REQUIRED_ROW_FIELDS - {
            "legacy_menu_keys",
            "legacy_menu_labels",
            "legacy_shortcuts",
            "legacy_input_cases",
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
        for field in (
            "legacy_menu_keys",
            "legacy_menu_labels",
            "legacy_shortcuts",
            "legacy_input_cases",
            "config_keys",
            "external_dependencies",
            "target_modules",
        ):
            if len(row[field]) != len(set(row[field])):
                raise ValueError(f"{row_id}: {field} contains duplicate values")
        for entry in row["java_evidence"] + row["automated_evidence"]:
            validate_evidence_entry(entry, legacy_root, row_id)
        for key in row["config_keys"]:
            if key not in config_keys:
                raise ValueError(f"{row_id}: config key is outside the active literal inventory: {key}")
            matrix_ids_by_config_key[key].append(row_id)
        for key in row["legacy_menu_keys"]:
            if key not in menu_keys:
                raise ValueError(f"{row_id}: menu key is outside the active Menu.java inventory: {key}")
            matrix_ids_by_menu_key[key].append(row_id)
        for label in row["legacy_menu_labels"]:
            if label not in menu_labels:
                raise ValueError(
                    f"{row_id}: menu label is outside the active Menu.java literal inventory: {label}"
                )
            matrix_ids_by_menu_label[label].append(row_id)
        for shortcut in row["legacy_shortcuts"]:
            if shortcut not in menu_shortcuts:
                raise ValueError(f"{row_id}: shortcut is outside the active Menu.java accelerator inventory: {shortcut}")
            matrix_ids_by_shortcut[shortcut].append(row_id)
        for input_case in row["legacy_input_cases"]:
            if input_case not in input_cases:
                raise ValueError(
                    f"{row_id}: input case is outside the active Input.java inventory: {input_case}"
                )
            matrix_ids_by_input_case[input_case].append(row_id)
    return (
        {key: sorted(ids) for key, ids in matrix_ids_by_config_key.items()},
        {key: sorted(ids) for key, ids in matrix_ids_by_menu_key.items()},
        {label: sorted(ids) for label, ids in matrix_ids_by_menu_label.items()},
        {key: sorted(ids) for key, ids in matrix_ids_by_shortcut.items()},
        {case: sorted(ids) for case, ids in matrix_ids_by_input_case.items()},
    )


def build_inventory(legacy_root: Path, matrix_path: Path) -> dict[str, Any]:
    validate_comment_stripper()
    if not legacy_root.is_dir():
        raise ValueError(f"Legacy root does not exist: {legacy_root}")
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    fingerprint, source_files = source_fingerprint(legacy_root)
    main_java_files = sorted((legacy_root / "src/main/java").rglob("*.java"))
    test_java_files = sorted((legacy_root / "src/test/java").rglob("*.java"))
    config_references, commented_only = collect_config_references(legacy_root, main_java_files)
    menu = collect_menu_resources(legacy_root)
    input_inventory = collect_input_cases(legacy_root)
    (
        matrix_ids_by_config_key,
        matrix_ids_by_menu_key,
        matrix_ids_by_menu_label,
        matrix_ids_by_shortcut,
        matrix_ids_by_input_case,
    ) = validate_matrix(
        matrix,
        legacy_root,
        set(config_references),
        {entry["key"] for entry in menu["keys"]},
        {entry["label"] for entry in menu["literal_labels"]},
        {entry["shortcut"] for entry in menu["accelerators"]},
        {entry["case"] for entry in input_inventory["cases"]},
        fingerprint,
    )
    config_entries = [
        {
            "key": key,
            "reference_count": len(references),
            "matrix_ids": matrix_ids_by_config_key.get(key, []),
            "references": references,
        }
        for key, references in config_references.items()
    ]
    mapped_keys = sum(bool(entry["matrix_ids"]) for entry in config_entries)
    menu["keys"] = [
        {
            "key": entry["key"],
            "matrix_ids": matrix_ids_by_menu_key.get(entry["key"], []),
            "lines": entry["lines"],
        }
        for entry in menu["keys"]
    ]
    menu["accelerators"] = [
        {
            "item": entry["item"],
            "shortcut": entry["shortcut"],
            "platform": entry["platform"],
            "matrix_ids": matrix_ids_by_shortcut.get(entry["shortcut"], []),
            "line": entry["line"],
        }
        for entry in menu["accelerators"]
    ]
    menu["literal_labels"] = [
        {
            "label": entry["label"],
            "matrix_ids": matrix_ids_by_menu_label.get(entry["label"], []),
            "references": entry["references"],
        }
        for entry in menu["literal_labels"]
    ]
    input_inventory["cases"] = [
        {
            **entry,
            "matrix_ids": matrix_ids_by_input_case.get(entry["case"], []),
        }
        for entry in input_inventory["cases"]
    ]
    mapped_menu_keys = sum(bool(entry["matrix_ids"]) for entry in menu["keys"])
    mapped_menu_labels = sum(bool(entry["matrix_ids"]) for entry in menu["literal_labels"])
    mapped_shortcuts = sum(bool(entry["matrix_ids"]) for entry in menu["accelerators"])
    mapped_input_cases = sum(bool(entry["matrix_ids"]) for entry in input_inventory["cases"])

    return {
        "schema_version": 3,
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
            "Menu keys cover active Menu.java resource lookups with Menu. or menu. prefixes.",
            "Menu literal labels cover active string-literal menu constructors; dynamic labels remain represented by their resource or runtime source.",
            "Menu accelerators cover explicit Menu.java setAccelerator calls and direct OS.isWindows guards; other input bindings remain T-003 work.",
            "Input key cases cover active Input.java keyPressed/keyReleased VK_* dispatch and local modifier checks; exact fall-through, branch combinations, actions, and mouse bindings remain T-003 work.",
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
            "active_menu_resource_keys": len(menu["keys"]),
            "mapped_menu_resource_keys": mapped_menu_keys,
            "unmapped_menu_resource_keys": len(menu["keys"]) - mapped_menu_keys,
            "active_menu_literal_labels": len(menu["literal_labels"]),
            "mapped_menu_literal_labels": mapped_menu_labels,
            "unmapped_menu_literal_labels": len(menu["literal_labels"]) - mapped_menu_labels,
            "active_menu_accelerators": len(menu["accelerators"]),
            "mapped_menu_accelerators": mapped_shortcuts,
            "unmapped_menu_accelerators": len(menu["accelerators"]) - mapped_shortcuts,
            "active_input_key_cases": len(input_inventory["cases"]),
            "mapped_input_key_cases": mapped_input_cases,
            "unmapped_input_key_cases": len(input_inventory["cases"]) - mapped_input_cases,
        },
        "config": {
            "active_literal_leaf_keys": len(config_entries),
            "active_literal_references": sum(entry["reference_count"] for entry in config_entries),
            "commented_only_config_java_keys": commented_only,
            "keys": config_entries,
        },
        "menu": menu,
        "input": input_inventory,
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
