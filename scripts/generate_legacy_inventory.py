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
    r"\(\s*KeyEvent\s+(?P<parameter>[A-Za-z_$][\w$]*)\s*\)\s*\{"
)
INPUT_KEY_CASE = re.compile(r"\bcase\s+(?P<key>VK_[A-Z0-9_]+)\s*:")
INPUT_DEFAULT_CASE = re.compile(r"\bdefault\s*:")
INPUT_KEY_SOURCES = (
    ("Input", "src/main/java/featurecat/lizzie/gui/Input.java"),
    (
        "InputIndependentMainBoard",
        "src/main/java/featurecat/lizzie/gui/InputIndependentMainBoard.java",
    ),
    (
        "InputIndependentSubboard",
        "src/main/java/featurecat/lizzie/gui/InputIndependentSubboard.java",
    ),
    ("InputSubboard", "src/main/java/featurecat/lizzie/gui/InputSubboard.java"),
)
INPUT_CONDITIONAL_KEY_SOURCES = (
    ("FloatBoard", "src/main/java/featurecat/lizzie/gui/FloatBoard.java", "keyPressed", 1),
    (
        "AnalysisFrameTable",
        "src/main/java/featurecat/lizzie/gui/AnalysisFrame.java",
        "keyPressed",
        1,
    ),
    (
        "AnalysisFrameWindow",
        "src/main/java/featurecat/lizzie/gui/AnalysisFrame.java",
        "keyPressed",
        2,
    ),
    (
        "DrawPainting",
        "src/main/java/featurecat/lizzie/gui/DrawPainting.java",
        "keyPressed",
        1,
    ),
    (
        "ChooseMoreEngine",
        "src/main/java/featurecat/lizzie/gui/ChooseMoreEngine.java",
        "keyPressed",
        1,
    ),
    (
        "LoadEngine",
        "src/main/java/featurecat/lizzie/gui/LoadEngine.java",
        "keyPressed",
        1,
    ),
    (
        "OtherPrograms",
        "src/main/java/featurecat/lizzie/gui/OtherPrograms.java",
        "keyPressed",
        1,
    ),
    (
        "TencentKifuDownload",
        "src/main/java/featurecat/lizzie/gui/TencentKifuDownload.java",
        "keyPressed",
        1,
    ),
    (
        "FoxKifuDownload",
        "src/main/java/featurecat/lizzie/gui/FoxKifuDownload.java",
        "keyPressed",
        1,
    ),
    (
        "BrowserFrame",
        "src/main/java/featurecat/lizzie/gui/BrowserFrame.java",
        "keyPressed",
        1,
    ),
    (
        "CaptureTsumeGoFrame",
        "src/main/java/featurecat/lizzie/gui/CaptureTsumeGoFrame.java",
        "keyPressed",
        1,
    ),
)
INPUT_POINTER_METHOD = re.compile(
    r"public\s+void\s+(?P<event>mouseClicked|mousePressed|mouseWheelMoved|mouseReleased|"
    r"mouseEntered|mouseExited|mouseMoved|mouseDragged)\s*\(\s*"
    r"(?:java\.awt\.event\.)?(?:MouseEvent|MouseWheelEvent)\s+"
    r"[A-Za-z_$][\w$]*\s*\)\s*\{"
)
INPUT_POINTER_SOURCES = (
    (
        "InputIndependentSubboard",
        "src/main/java/featurecat/lizzie/gui/InputIndependentSubboard.java",
        {
            "mouseClicked",
            "mousePressed",
            "mouseWheelMoved",
            "mouseReleased",
            "mouseEntered",
            "mouseExited",
        },
    ),
    (
        "InputSubboard",
        "src/main/java/featurecat/lizzie/gui/InputSubboard.java",
        {
            "mouseClicked",
            "mousePressed",
            "mouseWheelMoved",
            "mouseReleased",
            "mouseEntered",
            "mouseExited",
        },
    ),
    (
        "FloatBoard",
        "src/main/java/featurecat/lizzie/gui/FloatBoard.java",
        {"mousePressed", "mouseExited", "mouseWheelMoved", "mouseMoved"},
    ),
    (
        "AnalysisFrame",
        "src/main/java/featurecat/lizzie/gui/AnalysisFrame.java",
        {
            "mouseDragged",
            "mouseMoved",
            "mouseWheelMoved",
            "mouseExited",
            "mouseClicked",
            "mouseReleased",
        },
    ),
    (
        "DrawPainting",
        "src/main/java/featurecat/lizzie/gui/DrawPainting.java",
        {"mouseReleased", "mouseDragged", "mouseMoved"},
    ),
    (
        "ChooseMoreEngine",
        "src/main/java/featurecat/lizzie/gui/ChooseMoreEngine.java",
        {"mouseClicked", "mouseReleased"},
    ),
    (
        "LoadEngine",
        "src/main/java/featurecat/lizzie/gui/LoadEngine.java",
        {"mouseClicked", "mouseReleased"},
    ),
    (
        "OtherPrograms",
        "src/main/java/featurecat/lizzie/gui/OtherPrograms.java",
        {"mouseClicked", "mouseReleased"},
    ),
    (
        "TencentKifuDownload",
        "src/main/java/featurecat/lizzie/gui/TencentKifuDownload.java",
        {"mouseClicked"},
    ),
    (
        "FoxKifuDownload",
        "src/main/java/featurecat/lizzie/gui/FoxKifuDownload.java",
        {"mouseClicked"},
    ),
    (
        "BrowserFrameLoad",
        "src/main/java/featurecat/lizzie/gui/BrowserFrame.java",
        {"mouseClicked"},
        {"mouseClicked": 1},
    ),
    (
        "BrowserFrameStop",
        "src/main/java/featurecat/lizzie/gui/BrowserFrame.java",
        {"mouseClicked"},
        {"mouseClicked": 2},
    ),
    (
        "BrowserFrameLabelButton",
        "src/main/java/featurecat/lizzie/gui/BrowserFrame.java",
        {"mouseEntered", "mouseExited", "mousePressed", "mouseReleased"},
        {
            "mouseEntered": 1,
            "mouseExited": 1,
            "mousePressed": 1,
            "mouseReleased": 1,
        },
    ),
    (
        "JFontTextArea",
        "src/main/java/featurecat/lizzie/gui/JFontTextArea.java",
        {"mouseClicked", "mousePressed", "mouseReleased", "mouseEntered", "mouseExited"},
    ),
    (
        "JFontTextField",
        "src/main/java/featurecat/lizzie/gui/JFontTextField.java",
        {"mouseClicked", "mousePressed", "mouseReleased", "mouseEntered", "mouseExited"},
    ),
    (
        "JIMSendTextPane",
        "src/main/java/featurecat/lizzie/gui/JIMSendTextPane.java",
        {"mouseClicked", "mousePressed", "mouseReleased", "mouseEntered", "mouseExited"},
    ),
    (
        "DemoScrollBarUI2Increase",
        "src/main/java/featurecat/lizzie/gui/DemoScrollBarUI2.java",
        {"mouseEntered", "mouseExited"},
        {"mouseEntered": 1, "mouseExited": 1},
    ),
    (
        "DemoScrollBarUI2Decrease",
        "src/main/java/featurecat/lizzie/gui/DemoScrollBarUI2.java",
        {"mouseEntered", "mouseExited"},
        {"mouseEntered": 2, "mouseExited": 2},
    ),
    (
        "JPaintTextPane",
        "src/main/java/featurecat/lizzie/gui/JPaintTextPane.java",
        {"mouseClicked", "mousePressed", "mouseReleased", "mouseEntered", "mouseExited"},
    ),
    (
        "WindowMenuStrip",
        "src/main/java/featurecat/lizzie/gui/WindowMenuStrip.java",
        {"mousePressed", "mouseEntered", "mouseExited"},
    ),
    (
        "YikeLiveDialog",
        "src/main/java/featurecat/lizzie/gui/YikeLiveDialog.java",
        {"mouseClicked"},
    ),
    (
        "IndependentSubBoardLockButton",
        "src/main/java/featurecat/lizzie/gui/IndependentSubBoard.java",
        {"mouseEntered", "mouseExited"},
        {"mouseEntered": 1, "mouseExited": 1},
    ),
    (
        "IndependentSubBoardCloseButton",
        "src/main/java/featurecat/lizzie/gui/IndependentSubBoard.java",
        {"mouseEntered", "mouseExited"},
        {"mouseEntered": 2, "mouseExited": 2},
    ),
    (
        "IndependentSubBoardTopButton",
        "src/main/java/featurecat/lizzie/gui/IndependentSubBoard.java",
        {"mouseEntered", "mouseExited"},
        {"mouseEntered": 3, "mouseExited": 3},
    ),
    (
        "IndependentSubBoardWindow",
        "src/main/java/featurecat/lizzie/gui/IndependentSubBoard.java",
        {"mousePressed", "mouseDragged", "mouseMoved"},
        {"mousePressed": 1, "mouseDragged": 1, "mouseMoved": 1},
    ),
    (
        "BlunderListPanel",
        "src/main/java/featurecat/lizzie/gui/BlunderListPanel.java",
        {"mouseMoved", "mouseExited", "mouseClicked"},
    ),
    (
        "SidebarHeaderPanel",
        "src/main/java/featurecat/lizzie/gui/SidebarHeaderPanel.java",
        {"mouseClicked"},
    ),
    (
        "BottomToolbar",
        "src/main/java/featurecat/lizzie/gui/BottomToolbar.java",
        {"mouseClicked", "mousePressed", "mouseReleased", "mouseEntered", "mouseExited"},
    ),
    (
        "ConfigDialog2SidebarNav",
        "src/main/java/featurecat/lizzie/gui/ConfigDialog2.java",
        {"mousePressed"},
        {"mousePressed": 1},
    ),
    (
        "ConfigDialog2ToggleRow",
        "src/main/java/featurecat/lizzie/gui/ConfigDialog2.java",
        {"mouseClicked"},
        {"mouseClicked": 1},
    ),
    (
        "ConfigDialog2ColorLabel",
        "src/main/java/featurecat/lizzie/gui/ConfigDialog2.java",
        {"mouseClicked"},
        {"mouseClicked": 2},
    ),
    (
        "IndependentMainBoardLockButton",
        "src/main/java/featurecat/lizzie/gui/IndependentMainBoard.java",
        {"mouseEntered", "mouseExited"},
        {"mouseEntered": 1, "mouseExited": 1},
    ),
    (
        "IndependentMainBoardCloseButton",
        "src/main/java/featurecat/lizzie/gui/IndependentMainBoard.java",
        {"mouseEntered", "mouseExited"},
        {"mouseEntered": 2, "mouseExited": 2},
    ),
    (
        "IndependentMainBoardTopButton",
        "src/main/java/featurecat/lizzie/gui/IndependentMainBoard.java",
        {"mouseEntered", "mouseExited"},
        {"mouseEntered": 3, "mouseExited": 3},
    ),
    (
        "IndependentMainBoardWindow",
        "src/main/java/featurecat/lizzie/gui/IndependentMainBoard.java",
        {
            "mouseClicked",
            "mousePressed",
            "mouseDragged",
            "mouseExited",
            "mouseEntered",
            "mouseWheelMoved",
            "mouseReleased",
            "mouseMoved",
        },
        {
            "mouseClicked": 1,
            "mousePressed": 1,
            "mouseDragged": 1,
            "mouseExited": 4,
            "mouseEntered": 4,
            "mouseWheelMoved": 1,
            "mouseReleased": 1,
            "mouseMoved": 1,
        },
    ),
    (
        "Input",
        "src/main/java/featurecat/lizzie/gui/Input.java",
        {
            "mouseClicked",
            "mousePressed",
            "mouseWheelMoved",
            "mouseReleased",
            "mouseEntered",
            "mouseExited",
            "mouseMoved",
            "mouseDragged",
        },
    ),
    (
        "MoreEngines",
        "src/main/java/featurecat/lizzie/gui/MoreEngines.java",
        {"mouseClicked"},
    ),
    (
        "LizzieFrameMainPanel",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseEntered"},
        {"mouseEntered": 1},
    ),
    (
        "LizzieFrameVariationTreeClick",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseClicked"},
        {"mouseClicked": 1},
    ),
    (
        "LizzieFrameVariationTreeWheel",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseWheelMoved"},
        {"mouseWheelMoved": 1},
    ),
    (
        "LizzieFrameVariationTreeMotion",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseMoved"},
        {"mouseMoved": 1},
    ),
    (
        "LizzieFrameMoveListScrollPaneMotion",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseMoved"},
        {"mouseMoved": 2},
    ),
    (
        "LizzieFrameMoveListScrollPaneClick",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseClicked"},
        {"mouseClicked": 2},
    ),
    (
        "LizzieFrameMoveListTableWheel",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseWheelMoved"},
        {"mouseWheelMoved": 2},
    ),
    (
        "LizzieFrameMoveListTableClick",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseClicked"},
        {"mouseClicked": 3},
    ),
    (
        "LizzieFrameBlunderContentHover",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseExited", "mouseEntered"},
        {"mouseExited": 1, "mouseEntered": 2},
    ),
    (
        "LizzieFrameBlunderBlackClick",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseClicked"},
        {"mouseClicked": 4},
    ),
    (
        "LizzieFrameBlunderWhiteClick",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseClicked"},
        {"mouseClicked": 5},
    ),
    (
        "LizzieFrameBlunderBlackHeaderRelease",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseReleased"},
        {"mouseReleased": 1},
    ),
    (
        "LizzieFrameBlunderBlackHeaderHover",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseExited", "mouseEntered"},
        {"mouseExited": 2, "mouseEntered": 3},
    ),
    (
        "LizzieFrameBlunderBlackHover",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseExited", "mouseEntered"},
        {"mouseExited": 3, "mouseEntered": 4},
    ),
    (
        "LizzieFrameBlunderWhiteHeaderRelease",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseReleased"},
        {"mouseReleased": 2},
    ),
    (
        "LizzieFrameBlunderWhiteHeaderExit",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseExited"},
        {"mouseExited": 4},
    ),
    (
        "LizzieFrameBlunderWhiteHover",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseExited", "mouseEntered"},
        {"mouseExited": 5, "mouseEntered": 5},
    ),
    (
        "LizzieFrameBlunderMinBlackHover",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseExited", "mouseEntered"},
        {"mouseExited": 6, "mouseEntered": 6},
    ),
    (
        "LizzieFrameBlunderMinWhiteHover",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseExited", "mouseEntered"},
        {"mouseExited": 7, "mouseEntered": 7},
    ),
    (
        "LizzieFrameBlunderMinBlackScrollbarHover",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseExited", "mouseEntered"},
        {"mouseExited": 8, "mouseEntered": 8},
    ),
    (
        "LizzieFrameBlunderMinWhiteScrollbarHover",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseExited", "mouseEntered"},
        {"mouseExited": 9, "mouseEntered": 9},
    ),
    (
        "LizzieFrameCommentBlunderControlHover",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseExited", "mouseEntered"},
        {"mouseExited": 10, "mouseEntered": 10},
    ),
    (
        "LizzieFrameCommentTextAreaHover",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseExited", "mouseEntered"},
        {"mouseExited": 11, "mouseEntered": 11},
    ),
    (
        "LizzieFrameCommentTextPaneHover",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseExited", "mouseEntered"},
        {"mouseExited": 12, "mouseEntered": 12},
    ),
    (
        "LizzieFrameCommentTextAreaClick",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseClicked"},
        {"mouseClicked": 6},
    ),
    (
        "LizzieFrameCommentTextPaneClick",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseClicked"},
        {"mouseClicked": 7},
    ),
    (
        "LizzieFrameKifuLoadGlassPaneMotion",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseDragged", "mouseMoved"},
        {"mouseDragged": 1, "mouseMoved": 3},
    ),
    (
        "LizzieFrameTempGamePanelMotion",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseMoved"},
        {"mouseMoved": 4},
    ),
    (
        "LizzieFrameTempGamePanelClick",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseClicked"},
        {"mouseClicked": 8},
    ),
    (
        "LizzieFrameBigBoardPanelClick",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseClicked"},
        {"mouseClicked": 9},
    ),
    (
        "LizzieFramePlayerStrengthModelComboHover",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseEntered", "mouseExited"},
        {"mouseEntered": 13, "mouseExited": 13},
    ),
    (
        "LizzieFramePlayerStrengthMoveHitMapHover",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseMoved", "mouseExited"},
        {"mouseMoved": 5, "mouseExited": 14},
    ),
    (
        "LizzieFramePlayerStrengthMatchChartHover",
        "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
        {"mouseMoved", "mouseExited"},
        {"mouseMoved": 6, "mouseExited": 15},
    ),
    (
        "MenuKomiTextExit",
        "src/main/java/featurecat/lizzie/gui/Menu.java",
        {"mouseExited"},
        {"mouseExited": 1},
    ),
    (
        "MenuKomiUpHold",
        "src/main/java/featurecat/lizzie/gui/Menu.java",
        {"mousePressed", "mouseReleased"},
        {"mousePressed": 1, "mouseReleased": 1},
    ),
    (
        "MenuKomiDownHold",
        "src/main/java/featurecat/lizzie/gui/Menu.java",
        {"mousePressed", "mouseReleased"},
        {"mousePressed": 2, "mouseReleased": 2},
    ),
    (
        "MenuKomiUpHover",
        "src/main/java/featurecat/lizzie/gui/Menu.java",
        {"mouseEntered", "mouseExited"},
        {"mouseEntered": 1, "mouseExited": 2},
    ),
    (
        "MenuKomiDownHover",
        "src/main/java/featurecat/lizzie/gui/Menu.java",
        {"mouseEntered", "mouseExited"},
        {"mouseEntered": 2, "mouseExited": 3},
    ),
    (
        "MoveListFullTableClick",
        "src/main/java/featurecat/lizzie/gui/MoveListFrame.java",
        {"mouseClicked"},
        {"mouseClicked": 1},
    ),
    (
        "MoveListMinTable1Click",
        "src/main/java/featurecat/lizzie/gui/MoveListFrame.java",
        {"mouseClicked"},
        {"mouseClicked": 2},
    ),
    (
        "MoveListMinTable2Click",
        "src/main/java/featurecat/lizzie/gui/MoveListFrame.java",
        {"mouseClicked"},
        {"mouseClicked": 3},
    ),
    (
        "MoveListMatchPanelPointer",
        "src/main/java/featurecat/lizzie/gui/MoveListFrame.java",
        {"mousePressed", "mouseExited", "mouseMoved", "mouseDragged", "mouseWheelMoved"},
        {
            "mousePressed": 1,
            "mouseExited": 1,
            "mouseMoved": 1,
            "mouseDragged": 1,
            "mouseWheelMoved": 1,
        },
        {"selectedIndex"},
    ),
    (
        "MoveListFullHeaderRelease",
        "src/main/java/featurecat/lizzie/gui/MoveListFrame.java",
        {"mouseReleased"},
        {"mouseReleased": 1},
    ),
    (
        "MoveListMin1HeaderRelease",
        "src/main/java/featurecat/lizzie/gui/MoveListFrame.java",
        {"mouseReleased"},
        {"mouseReleased": 2},
    ),
    (
        "MoveListMin2HeaderRelease",
        "src/main/java/featurecat/lizzie/gui/MoveListFrame.java",
        {"mouseReleased"},
        {"mouseReleased": 3},
    ),
)
FULL_POINTER_COVERAGE_PATHS = {
    "src/main/java/featurecat/lizzie/gui/LizzieFrame.java",
    "src/main/java/featurecat/lizzie/gui/Menu.java",
    "src/main/java/featurecat/lizzie/gui/MoveListFrame.java",
}
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
    "legacy_input_bindings",
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
    return closing_delimiter(source, open_brace, "{", "}")


def closing_delimiter(source: str, open_index: int, opening: str, closing: str) -> int:
    depth = 0
    state = "code"
    index = open_index
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char == '"':
                state = "string"
            elif char == "'":
                state = "char"
            elif char == opening:
                depth += 1
            elif char == closing:
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
    raise ValueError(f"Unbalanced Java {opening}{closing} while collecting input bindings")


def normalize_java(fragment: str) -> str:
    return re.sub(r"\s+", " ", fragment).strip()


def skip_space(source: str, index: int, end: int) -> int:
    while index < end and source[index].isspace():
        index += 1
    return index


def word_at(source: str, index: int, word: str) -> bool:
    before = source[index - 1] if index else ""
    after_index = index + len(word)
    after = source[after_index] if after_index < len(source) else ""
    return source.startswith(word, index) and not (
        before and (before.isalnum() or before in "_$")
    ) and not (
        after and (after.isalnum() or after in "_$")
    )


def parse_java_body(source: str, index: int, end: int) -> tuple[list[dict[str, Any]], int]:
    index = skip_space(source, index, end)
    if index < end and source[index] == "{":
        close = closing_brace(source, index)
        if close >= end:
            raise ValueError("Legacy key branch block extends beyond its case")
        return parse_java_sequence(source, index + 1, close), close + 1
    node, index = parse_java_statement(source, index, end)
    return [node], index


def parse_java_statement(source: str, index: int, end: int) -> tuple[dict[str, Any], int]:
    index = skip_space(source, index, end)
    if word_at(source, index, "try"):
        body_open = skip_space(source, index + 3, end)
        if body_open >= end or source[body_open] != "{":
            raise ValueError(
                f"Legacy input try statement must use a block at line {line_number(source, index)}"
            )
        cursor = closing_brace(source, body_open) + 1
        has_handler = False
        while True:
            cursor = skip_space(source, cursor, end)
            if cursor < end and word_at(source, cursor, "catch"):
                parameter_open = skip_space(source, cursor + 5, end)
                if parameter_open >= end or source[parameter_open] != "(":
                    raise ValueError(
                        f"Unsupported legacy input catch at line {line_number(source, cursor)}"
                    )
                parameter_close = closing_delimiter(source, parameter_open, "(", ")")
                catch_open = skip_space(source, parameter_close + 1, end)
                if catch_open >= end or source[catch_open] != "{":
                    raise ValueError(
                        f"Legacy input catch must use a block at line {line_number(source, cursor)}"
                    )
                cursor = closing_brace(source, catch_open) + 1
                has_handler = True
                continue
            if cursor < end and word_at(source, cursor, "finally"):
                finally_open = skip_space(source, cursor + 7, end)
                if finally_open >= end or source[finally_open] != "{":
                    raise ValueError(
                        "Legacy input finally must use a block at line "
                        f"{line_number(source, cursor)}"
                    )
                cursor = closing_brace(source, finally_open) + 1
                has_handler = True
            break
        if not has_handler:
            raise ValueError(
                f"Legacy input try has no catch or finally at line {line_number(source, index)}"
            )
        return (
            {
                "kind": "action",
                "statement": normalize_java(source[index:cursor]),
                "line": line_number(source, index),
            },
            cursor,
        )
    if word_at(source, index, "for"):
        condition_open = skip_space(source, index + 3, end)
        if condition_open >= end or source[condition_open] != "(":
            raise ValueError(f"Unsupported legacy input for statement at line {line_number(source, index)}")
        condition_close = closing_delimiter(source, condition_open, "(", ")")
        body_open = skip_space(source, condition_close + 1, end)
        if body_open >= end or source[body_open] != "{":
            raise ValueError(f"Legacy input for loop must use a block at line {line_number(source, index)}")
        body_close = closing_brace(source, body_open)
        if body_close >= end:
            raise ValueError(f"Legacy input for loop crosses its branch at line {line_number(source, index)}")
        return (
            {
                "kind": "action",
                "statement": normalize_java(source[index : body_close + 1]),
                "line": line_number(source, index),
            },
            body_close + 1,
        )
    if word_at(source, index, "if"):
        condition_open = skip_space(source, index + 2, end)
        if condition_open >= end or source[condition_open] != "(":
            raise ValueError(f"Unsupported legacy key if statement at line {line_number(source, index)}")
        condition_close = closing_delimiter(source, condition_open, "(", ")")
        if condition_close >= end:
            raise ValueError(
                f"Legacy key condition crosses its case boundary at line {line_number(source, index)}"
            )
        then_nodes, next_index = parse_java_body(source, condition_close + 1, end)
        next_index = skip_space(source, next_index, end)
        else_nodes: list[dict[str, Any]] = []
        if next_index < end and word_at(source, next_index, "else"):
            else_nodes, next_index = parse_java_body(source, next_index + 4, end)
        return (
            {
                "kind": "if",
                "condition": normalize_java(source[condition_open + 1 : condition_close]),
                "line": line_number(source, index),
                "then": then_nodes,
                "else": else_nodes,
            },
            next_index,
        )

    state = "code"
    parentheses = brackets = braces = 0
    cursor = index
    while cursor < end:
        char = source[cursor]
        following = source[cursor + 1] if cursor + 1 < end else ""
        if state == "code":
            if char == '"':
                state = "string"
            elif char == "'":
                state = "char"
            elif char == "(":
                parentheses += 1
            elif char == ")":
                parentheses -= 1
            elif char == "[":
                brackets += 1
            elif char == "]":
                brackets -= 1
            elif char == "{":
                braces += 1
            elif char == "}":
                braces -= 1
            elif char == ";" and parentheses == brackets == braces == 0:
                statement = normalize_java(source[index : cursor + 1])
                kind = "action"
                if statement == "break;":
                    kind = "break"
                elif statement == "return;":
                    kind = "return"
                return (
                    {
                        "kind": kind,
                        "statement": statement,
                        "line": line_number(source, index),
                    },
                    cursor + 1,
                )
        elif char == "\\" and following:
            cursor += 1
        elif state == "string" and char == '"':
            state = "code"
        elif state == "char" and char == "'":
            state = "code"
        cursor += 1
    raise ValueError(f"Unsupported legacy key statement at line {line_number(source, index)}")


def parse_java_sequence(source: str, start: int, end: int) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    index = skip_space(source, start, end)
    while index < end:
        node, index = parse_java_statement(source, index, end)
        nodes.append(node)
        index = skip_space(source, index, end)
    return nodes


def known_boolean_expression(expression: str, values: dict[str, bool]) -> bool | None:
    expression = expression.strip()
    if expression in values:
        return values[expression]
    if expression.startswith("(") and expression.endswith(")"):
        depth = 0
        closes_at_end = True
        for index, char in enumerate(expression):
            depth += char == "("
            depth -= char == ")"
            if depth == 0 and index != len(expression) - 1:
                closes_at_end = False
                break
        if closes_at_end:
            return known_boolean_expression(expression[1:-1], values)
    for operator in ("||", "&&"):
        depth = 0
        parts: list[str] = []
        start = 0
        index = 0
        while index < len(expression) - 1:
            char = expression[index]
            depth += char == "("
            depth -= char == ")"
            if depth == 0 and expression.startswith(operator, index):
                parts.append(expression[start:index])
                start = index + 2
                index += 1
            index += 1
        if parts:
            parts.append(expression[start:])
            results = [known_boolean_expression(part, values) for part in parts]
            if operator == "||":
                if True in results:
                    return True
                return False if None not in results else None
            if False in results:
                return False
            return True if None not in results else None
    if expression.startswith("!"):
        value = known_boolean_expression(expression[1:], values)
        return None if value is None else not value
    return None


def condition_value_identifiers(values: dict[str, bool]) -> set[str]:
    return {
        name
        for expression in values
        for name in re.findall(r"[A-Za-z_$][\w$]*", expression)
        if name not in {"true", "false"}
    }


def invalidate_condition_value(values: dict[str, bool], name: str) -> None:
    reference = re.compile(rf"(?<![\w$]){re.escape(name)}(?![\w$])")
    for expression in list(values):
        if reference.search(expression):
            values.pop(expression)


def integer_conditions_are_consistent(
    conditions: list[dict[str, Any]], stable_integer_variables: set[str]
) -> bool:
    bounds: dict[str, list[Any]] = {}
    opposite = {
        "==": "!=",
        "!=": "==",
        ">": "<=",
        ">=": "<",
        "<": ">=",
        "<=": ">",
    }
    for condition in conditions:
        match = re.fullmatch(
            r"([A-Za-z_$][\w$]*)\s*(==|!=|>=|<=|>|<)\s*(-?\d+)",
            condition["expression"],
        )
        if not match:
            continue
        name, operator, literal = match.group(1), match.group(2), int(match.group(3))
        if name not in stable_integer_variables:
            continue
        if not condition["expected"]:
            operator = opposite[operator]
        lower, upper, excluded = bounds.setdefault(name, [None, None, set()])
        if operator == "==":
            lower = max(lower if lower is not None else literal, literal)
            upper = min(upper if upper is not None else literal, literal)
        elif operator == "!=":
            excluded.add(literal)
        elif operator == ">":
            lower = max(lower if lower is not None else literal + 1, literal + 1)
        elif operator == ">=":
            lower = max(lower if lower is not None else literal, literal)
        elif operator == "<":
            upper = min(upper if upper is not None else literal - 1, literal - 1)
        else:
            upper = min(upper if upper is not None else literal, literal)
        bounds[name] = [lower, upper, excluded]
        if lower is not None and upper is not None and (
            lower > upper or (lower == upper and lower in excluded)
        ):
            return False
    return True


def branch_path(path: dict[str, Any], expression: str, expected: bool) -> dict[str, Any] | None:
    values = path["condition_values"]
    known_value = known_boolean_expression(expression, values)
    if known_value is not None:
        return path if known_value == expected else None
    if expression in values:
        return path if values[expression] == expected else None
    conditions = [*path["conditions"], {"expression": expression, "expected": expected}]
    if not integer_conditions_are_consistent(
        conditions, path.get("stable_integer_variables", set())
    ):
        return None
    return {
        **path,
        "conditions": conditions,
        "condition_values": {**values, expression: expected},
    }


def execute_java_nodes(
    nodes: list[dict[str, Any]],
    paths: list[dict[str, Any]],
    track_boolean_assignments: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    continuing = paths
    broken: list[dict[str, Any]] = []
    for node in nodes:
        if node["kind"] == "action":
            updated: list[dict[str, Any]] = []
            for path in continuing:
                candidate = {
                    **path,
                    "actions": [
                        *path["actions"],
                        {"line": node["line"], "statement": node["statement"]},
                    ],
                }
                if track_boolean_assignments:
                    values = dict(candidate["condition_values"])
                    assignment = re.fullmatch(
                        r"(?:boolean\s+)?([A-Za-z_$][\w$]*)\s*=\s*(true|false);",
                        node["statement"],
                    )
                    if assignment:
                        name = assignment.group(1)
                        invalidate_condition_value(values, name)
                        values[name] = assignment.group(2) == "true"
                    elif node["statement"].startswith("for "):
                        loop_statement = node["statement"]
                        literal_assignments = re.findall(
                            r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*=\s*(true|false)\s*;",
                            loop_statement,
                        )
                        for name in condition_value_identifiers(values):
                            literals = [
                                literal
                                for assigned_name, literal in literal_assignments
                                if assigned_name == name
                            ]
                            simple_writes = re.findall(
                                rf"(?<![\w$.]){re.escape(name)}\s*=(?!=)",
                                loop_statement,
                            )
                            other_write = re.search(
                                rf"(?:\b{re.escape(name)}\s*(?:[+\-*/%&|^]=|\+\+|--)|"
                                rf"(?:\+\+|--)\s*\b{re.escape(name)}\b|"
                                rf"\b(?:boolean|Boolean)\s+{re.escape(name)}\b)",
                                loop_statement,
                            )
                            assigned_values = {literal == "true" for literal in literals}
                            has_write = bool(simple_writes or other_write)
                            can_preserve = (
                                has_write
                                and len(simple_writes) == len(literals)
                                and not other_write
                                and len(assigned_values) == 1
                                and values.get(name) in assigned_values
                            )
                            if has_write and not can_preserve:
                                invalidate_condition_value(values, name)
                    else:
                        for name in condition_value_identifiers(values):
                            write = re.search(
                                rf"(?:\b{re.escape(name)}\s*(?:=(?!=)|[+\-*/%&|^]=|\+\+|--)|"
                                rf"(?:\+\+|--)\s*\b{re.escape(name)}\b)",
                                node["statement"],
                            )
                            if write:
                                invalidate_condition_value(values, name)
                    candidate["condition_values"] = values
                updated.append(candidate)
            continuing = updated
        elif node["kind"] in {"break", "return"}:
            if node["kind"] == "return":
                continuing = [
                    {
                        **path,
                        "actions": [
                            *path["actions"],
                            {"line": node["line"], "statement": node["statement"]},
                        ],
                    }
                    for path in continuing
                ]
            broken.extend(continuing)
            continuing = []
        else:
            branches: list[dict[str, Any]] = []
            for path in continuing:
                for expected, branch_nodes in ((True, node["then"]), (False, node["else"])):
                    candidate = branch_path(path, node["condition"], expected)
                    if candidate is None:
                        continue
                    branch_continuing, branch_broken = execute_java_nodes(
                        branch_nodes, [candidate], track_boolean_assignments
                    )
                    branches.extend(branch_continuing)
                    broken.extend(branch_broken)
            continuing = branches
        if not continuing:
            break
    return continuing, broken


def validate_input_parser() -> None:
    first = "if (e.isAltDown()) { first(); break; }"
    second = "if (e.isAltDown()) { unreachable(); break; } second(); break;"
    initial = [{"conditions": [], "condition_values": {}, "actions": [], "case_chain": []}]
    continuing, completed = execute_java_nodes(parse_java_sequence(first, 0, len(first)), initial)
    continuing, second_completed = execute_java_nodes(
        parse_java_sequence(second, 0, len(second)), continuing
    )
    completed.extend(second_completed)
    statements = [[action["statement"] for action in path["actions"]] for path in completed]
    if continuing or statements != [["first();"], ["second();"]]:
        raise ValueError("Input binding parser fall-through self-check failed")
    bounded_initial = {**initial[0], "stable_integer_variables": {"selectedIndex"}}
    bounded = branch_path(bounded_initial, "selectedIndex >= 7", True)
    if bounded is None or branch_path(bounded, "selectedIndex == 0", True) is not None:
        raise ValueError("Input binding parser integer-condition self-check failed")
    floating = branch_path(initial[0], "x > 0", True)
    if floating is None or branch_path(floating, "x < 1", True) is None:
        raise ValueError("Input binding parser untyped-number self-check failed")
    boolean_path = {
        **initial[0],
        "condition_values": {"noRefresh": False},
    }
    if branch_path(boolean_path, "!(sameNode && noRefresh)", False) is not None:
        raise ValueError("Input binding parser boolean-expression self-check failed")
    precedence_values = {"x": False, "y": False}
    if known_boolean_expression("!x && y", precedence_values) is not False:
        raise ValueError("Input binding parser boolean-and precedence self-check failed")
    precedence_values = {"x": True, "y": True}
    if known_boolean_expression("!x || y", precedence_values) is not True:
        raise ValueError("Input binding parser boolean-or precedence self-check failed")
    reassigned = "boolean a = false; a = ready(); if (a && other()) hit();"
    continuing, completed = execute_java_nodes(
        parse_java_sequence(reassigned, 0, len(reassigned)),
        initial,
        True,
    )
    completed.extend(continuing)
    if not any(
        any(action["statement"] == "hit();" for action in path["actions"])
        for path in completed
    ):
        raise ValueError("Input binding parser boolean-reassignment self-check failed")
    loop_reassigned = "boolean a = false; for (;;) { a = ready(); } if (a) hit();"
    continuing, completed = execute_java_nodes(
        parse_java_sequence(loop_reassigned, 0, len(loop_reassigned)),
        initial,
        True,
    )
    completed.extend(continuing)
    if not any(
        any(action["statement"] == "hit();" for action in path["actions"])
        for path in completed
    ):
        raise ValueError("Input binding parser loop-reassignment self-check failed")
    composite_reassigned = (
        "if (a && b) first(); a = true; b = true; if (a && b) second();"
    )
    continuing, completed = execute_java_nodes(
        parse_java_sequence(composite_reassigned, 0, len(composite_reassigned)),
        initial,
        True,
    )
    completed.extend(continuing)
    if not completed or any(
        not any(action["statement"] == "second();" for action in path["actions"])
        for path in completed
    ):
        raise ValueError("Input binding parser composite-cache self-check failed")
    returning = "if (stop()) return; after();"
    continuing, completed = execute_java_nodes(
        parse_java_sequence(returning, 0, len(returning)), initial
    )
    completed.extend(continuing)
    statements = [[action["statement"] for action in path["actions"]] for path in completed]
    if statements != [["return;"], ["after();"]]:
        raise ValueError("Input binding parser return self-check failed")
    looping = "if (hasMoves()) for (int i = 0; i < moves.size(); i++) { use(moves.get(i)); } done();"
    continuing, completed = execute_java_nodes(
        parse_java_sequence(looping, 0, len(looping)), initial
    )
    completed.extend(continuing)
    statements = [[action["statement"] for action in path["actions"]] for path in completed]
    if statements != [
        ["for (int i = 0; i < moves.size(); i++) { use(moves.get(i)); }", "done();"],
        ["done();"],
    ]:
        raise ValueError("Input binding parser for-loop self-check failed")
    guarded = "try { act(); } catch (Exception e) { report(); } done();"
    continuing, completed = execute_java_nodes(
        parse_java_sequence(guarded, 0, len(guarded)), initial
    )
    completed.extend(continuing)
    statements = [[action["statement"] for action in path["actions"]] for path in completed]
    if statements != [["try { act(); } catch (Exception e) { report(); }", "done();"]]:
        raise ValueError("Input binding parser try/catch self-check failed")
    tracked = "boolean changed = false; if (ready()) changed = true; if (changed) apply();"
    continuing, completed = execute_java_nodes(
        parse_java_sequence(tracked, 0, len(tracked)), initial, True
    )
    completed.extend(continuing)
    statements = [[action["statement"] for action in path["actions"]] for path in completed]
    if statements != [
        ["boolean changed = false;", "changed = true;", "apply();"],
        ["boolean changed = false;"],
    ]:
        raise ValueError("Input binding parser boolean-tracking self-check failed")
    monotonic_loop = (
        "boolean matched = true; "
        "for (int i = 0; i < moves.size(); i++) { if (ready()) matched = true; } "
        "if (matched) apply();"
    )
    continuing, completed = execute_java_nodes(
        parse_java_sequence(monotonic_loop, 0, len(monotonic_loop)), initial, True
    )
    completed.extend(continuing)
    statements = [[action["statement"] for action in path["actions"]] for path in completed]
    if statements != [
        [
            "boolean matched = true;",
            "for (int i = 0; i < moves.size(); i++) { if (ready()) matched = true; }",
            "apply();",
        ]
    ]:
        raise ValueError("Input binding parser monotonic-loop self-check failed")
    changing_loop = (
        "boolean matched = false; "
        "for (int i = 0; i < moves.size(); i++) { if (ready()) matched = true; } "
        "if (matched) apply();"
    )
    continuing, completed = execute_java_nodes(
        parse_java_sequence(changing_loop, 0, len(changing_loop)), initial, True
    )
    completed.extend(continuing)
    statements = [[action["statement"] for action in path["actions"]] for path in completed]
    loop_statement = "for (int i = 0; i < moves.size(); i++) { if (ready()) matched = true; }"
    if statements != [
        ["boolean matched = false;", loop_statement, "apply();"],
        ["boolean matched = false;", loop_statement],
    ]:
        raise ValueError("Input binding parser changing-loop self-check failed")
    mixed_loop = (
        "boolean matched = true; "
        "for (int i = 0; i < moves.size(); i++) { matched = maybe(); matched = true; } "
        "if (matched) apply();"
    )
    continuing, completed = execute_java_nodes(
        parse_java_sequence(mixed_loop, 0, len(mixed_loop)), initial, True
    )
    completed.extend(continuing)
    statements = [[action["statement"] for action in path["actions"]] for path in completed]
    loop_statement = (
        "for (int i = 0; i < moves.size(); i++) { matched = maybe(); matched = true; }"
    )
    if statements != [
        ["boolean matched = true;", loop_statement, "apply();"],
        ["boolean matched = true;", loop_statement],
    ]:
        raise ValueError("Input binding parser mixed-loop self-check failed")


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


def collect_switch_key_source(
    legacy_root: Path, source_id: str, source_path: str
) -> dict[str, Any]:
    input_path = legacy_root / source_path
    id_prefix = "" if source_id == "Input" else f"{source_id}:"
    source = strip_java_comments(input_path.read_text(encoding="utf-8", errors="replace"))
    cases: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    post_dispatch_actions: dict[str, list[dict[str, Any]]] = {}
    seen_events: set[str] = set()
    for method_match in INPUT_KEY_METHOD.finditer(source):
        event = method_match.group("event")
        if event in seen_events:
            raise ValueError(f"{input_path.name} contains duplicate {event} methods")
        seen_events.add(event)
        open_brace = method_match.end() - 1
        method_end = closing_brace(source, open_brace)
        parameter = re.escape(method_match.group("parameter"))
        switch_match = re.search(
            rf"switch\s*\(\s*{parameter}\.getKeyCode\s*\(\s*\)\s*\)\s*\{{",
            source[open_brace + 1 : method_end],
        )
        if not switch_match:
            if normalize_java(source[open_brace + 1 : method_end]):
                raise ValueError(f"{input_path.name} {event} has no supported key-code switch")
            post_dispatch_actions[event] = []
            continue
        switch_start = open_brace + 1 + switch_match.start()
        switch_open = open_brace + switch_match.end()
        if normalize_java(source[open_brace + 1 : switch_start]):
            raise ValueError(f"{input_path.name} {event} has unsupported pre-switch statements")
        switch_end = closing_brace(source, switch_open)
        case_matches = list(INPUT_KEY_CASE.finditer(source, switch_open + 1, switch_end))
        default_match = INPUT_DEFAULT_CASE.search(source, switch_open + 1, switch_end)
        segments: list[dict[str, Any]] = []
        for index, case_match in enumerate(case_matches):
            candidates = [switch_end]
            if index + 1 < len(case_matches):
                candidates.append(case_matches[index + 1].start())
            if default_match and default_match.start() > case_match.start():
                candidates.append(default_match.start())
            segment_end = min(candidates)
            case_id = f'{id_prefix}{event}:{case_match.group("key")}'
            segments.append(
                {
                    "case": case_id,
                    "event": event,
                    "key": case_match.group("key"),
                    "line": line_number(source, case_match.start()),
                    "nodes": parse_java_sequence(source, case_match.end(), segment_end),
                }
            )

        event_bindings: list[dict[str, Any]] = []
        for start_index, segment in enumerate(segments):
            paths = [
                {
                    "conditions": [],
                    "condition_values": {},
                    "actions": [],
                    "case_chain": [],
                }
            ]
            completed: list[dict[str, Any]] = []
            for current in segments[start_index:]:
                paths = [
                    {**path, "case_chain": [*path["case_chain"], current["case"]]} for path in paths
                ]
                paths, broken = execute_java_nodes(current["nodes"], paths)
                completed.extend(broken)
                if not paths:
                    break
            completed.extend(paths)
            if not completed:
                raise ValueError(f"{input_path.name} {segment['case']} produced no binding paths")
            for ordinal, path in enumerate(completed, start=1):
                event_bindings.append(
                    {
                        "binding": f'{segment["case"]}#{ordinal}',
                        "case": segment["case"],
                        "source_id": source_id,
                        "event": event,
                        "key": segment["key"],
                        "line": segment["line"],
                        "conditions": path["conditions"],
                        "case_chain": path["case_chain"],
                        "statements": path["actions"],
                    }
                )

        post_nodes = parse_java_sequence(source, switch_end + 1, method_end)
        post_paths, post_breaks = execute_java_nodes(
            post_nodes,
            [{"conditions": [], "condition_values": {}, "actions": [], "case_chain": []}],
        )
        if post_breaks or len(post_paths) != 1 or post_paths[0]["conditions"]:
            raise ValueError(f"{input_path.name} {event} has unsupported post-switch control flow")
        post_dispatch_actions[event] = post_paths[0]["actions"]
        bindings.extend(event_bindings)

        by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for binding in event_bindings:
            by_case[binding["case"]].append(binding)
        for segment in segments:
            searchable = " ".join(
                condition["expression"]
                for binding in by_case[segment["case"]]
                for condition in binding["conditions"]
            )
            cases.append(
                {
                    "case": segment["case"],
                    "source_id": source_id,
                    "event": event,
                    "key": segment["key"],
                    "line": segment["line"],
                    "modifier_checks": [
                        name for name, pattern in INPUT_MODIFIER_CHECKS if pattern.search(searchable)
                    ],
                    "binding_count": len(by_case[segment["case"]]),
                }
            )

    expected_events = {"keyPressed", "keyReleased"}
    if seen_events != expected_events:
        raise ValueError(f"{input_path.name} key methods differ from expected: {sorted(seen_events)}")
    if len(cases) != len(INPUT_KEY_CASE.findall(source)):
        raise ValueError(f"{input_path.name} contains a VK_* case outside the indexed key methods")
    case_ids = [entry["case"] for entry in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError(f"{input_path.name} contains duplicate key cases in an indexed method")
    binding_ids = [entry["binding"] for entry in bindings]
    if len(binding_ids) != len(set(binding_ids)):
        raise ValueError(f"{input_path.name} produced duplicate normalized key bindings")
    return {
        "id": source_id,
        "source": relative_path(input_path, legacy_root),
        "active_key_cases": len(cases),
        "active_key_bindings": len(bindings),
        "events": {
            event: sum(entry["event"] == event for entry in cases)
            for event in sorted(expected_events)
        },
        "post_dispatch_actions": post_dispatch_actions,
        "cases": cases,
        "bindings": bindings,
    }


def collect_conditional_key_source(
    legacy_root: Path,
    source_id: str,
    source_path: str,
    expected_event: str,
    method_ordinal: int,
) -> dict[str, Any]:
    input_path = legacy_root / source_path
    source = strip_java_comments(input_path.read_text(encoding="utf-8", errors="replace"))
    cases: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    indexed_keys: list[str] = []
    method_matches = [
        match
        for match in INPUT_KEY_METHOD.finditer(source)
        if match.group("event") == expected_event
    ]
    if method_ordinal < 1 or method_ordinal > len(method_matches):
        raise ValueError(
            f"{input_path.name} has no {expected_event} method ordinal {method_ordinal}"
        )
    method_match = method_matches[method_ordinal - 1]
    open_brace = method_match.end() - 1
    method_end = closing_brace(source, open_brace)
    nodes = parse_java_sequence(source, open_brace + 1, method_end)
    parameter = re.escape(method_match.group("parameter"))
    key_check = re.compile(
        rf"{parameter}\.(?:getKeyCode|getKeyChar)\s*\(\s*\)\s*==\s*"
        r"KeyEvent\.(VK_[A-Z0-9_]+)"
    )
    for node in nodes:
        if node["kind"] != "if" or node["else"]:
            raise ValueError(f"{input_path.name} {expected_event} has unsupported key dispatch")
        keys = key_check.findall(node["condition"])
        reduced = key_check.sub("KEY", node["condition"])
        if not keys or not re.fullmatch(r"KEY(?:\s*\|\|\s*KEY)*", reduced):
            raise ValueError(f"{input_path.name} {expected_event} has unsupported key condition")
        for key in keys:
            case_id = f"{source_id}:{expected_event}:{key}"
            continuing, completed = execute_java_nodes(
                node["then"],
                [
                    {
                        "conditions": [],
                        "condition_values": {},
                        "actions": [],
                        "case_chain": [case_id],
                    }
                ],
            )
            completed.extend(continuing)
            if not completed:
                raise ValueError(f"{input_path.name} {case_id} produced no binding paths")
            for ordinal, path in enumerate(completed, start=1):
                bindings.append(
                    {
                        "binding": f"{case_id}#{ordinal}",
                        "case": case_id,
                        "source_id": source_id,
                        "event": expected_event,
                        "key": key,
                        "line": node["line"],
                        "conditions": path["conditions"],
                        "case_chain": path["case_chain"],
                        "statements": path["actions"],
                    }
                )
            cases.append(
                {
                    "case": case_id,
                    "source_id": source_id,
                    "event": expected_event,
                    "key": key,
                    "line": node["line"],
                    "modifier_checks": [],
                    "binding_count": len(completed),
                }
            )
            indexed_keys.append(key)

    if indexed_keys != re.findall(
        r"\bKeyEvent\.(VK_[A-Z0-9_]+)", source[open_brace + 1 : method_end]
    ):
        raise ValueError(f"{input_path.name} contains a key constant outside the indexed dispatch")
    case_ids = [entry["case"] for entry in cases]
    binding_ids = [entry["binding"] for entry in bindings]
    if len(case_ids) != len(set(case_ids)) or len(binding_ids) != len(set(binding_ids)):
        raise ValueError(f"{input_path.name} produced duplicate normalized key input")
    return {
        "id": source_id,
        "source": relative_path(input_path, legacy_root),
        "active_key_cases": len(cases),
        "active_key_bindings": len(bindings),
        "events": {expected_event: len(cases)},
        "post_dispatch_actions": {expected_event: []},
        "cases": cases,
        "bindings": bindings,
    }


def collect_pointer_source(
    legacy_root: Path,
    source_id: str,
    source_path: str,
    expected_events: set[str],
    method_ordinals: dict[str, int] | None = None,
    stable_integer_variables: set[str] | None = None,
) -> dict[str, Any]:
    input_path = legacy_root / source_path
    source = strip_java_comments(input_path.read_text(encoding="utf-8", errors="replace"))
    events: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    seen_events: set[str] = set()
    event_ordinals: dict[str, int] = {}
    stable_integer_variables = stable_integer_variables or set()
    for name in stable_integer_variables:
        if not re.search(rf"\b(?:int|Integer)\s+{re.escape(name)}\b", source):
            raise ValueError(f"{input_path.name} does not declare stable integer {name}")
    if method_ordinals is not None:
        if set(method_ordinals) != expected_events or any(
            ordinal < 1 for ordinal in method_ordinals.values()
        ):
            raise ValueError(f"{input_path.name} has invalid pointer method ordinals")
    for method_match in INPUT_POINTER_METHOD.finditer(source):
        event = method_match.group("event")
        event_ordinals[event] = event_ordinals.get(event, 0) + 1
        if method_ordinals is not None and method_ordinals.get(event) != event_ordinals[event]:
            continue
        if event in seen_events:
            raise ValueError(f"{input_path.name} contains duplicate {event} methods")
        seen_events.add(event)
        open_brace = method_match.end() - 1
        method_end = closing_brace(source, open_brace)
        method_source = source[open_brace + 1 : method_end]
        for name in stable_integer_variables:
            mutation = re.search(
                rf"(?:\b{re.escape(name)}\s*(?:=(?!=)|[+\-*/%&|^]=|\+\+|--)|"
                rf"(?:\+\+|--)\s*\b{re.escape(name)}\b)",
                method_source,
            )
            if mutation:
                raise ValueError(f"{input_path.name} mutates stable integer {name}")
        nodes = parse_java_sequence(source, open_brace + 1, method_end)
        continuing, completed = execute_java_nodes(
            nodes,
            [
                {
                    "conditions": [],
                    "condition_values": {},
                    "stable_integer_variables": stable_integer_variables,
                    "actions": [],
                    "case_chain": [],
                }
            ],
            True,
        )
        completed.extend(continuing)
        event_id = f"{source_id}:{event}"
        for ordinal, path in enumerate(completed, start=1):
            bindings.append(
                {
                    "binding": f"{event_id}#{ordinal}",
                    "event_id": event_id,
                    "source_id": source_id,
                    "event": event,
                    "line": line_number(source, method_match.start()),
                    "conditions": path["conditions"],
                    "statements": path["actions"],
                }
            )
        events.append(
            {
                "event_id": event_id,
                "source_id": source_id,
                "event": event,
                "line": line_number(source, method_match.start()),
                "binding_count": len(completed),
            }
        )

    if seen_events != expected_events:
        raise ValueError(f"{input_path.name} pointer methods differ from expected: {sorted(seen_events)}")
    event_ids = [entry["event_id"] for entry in events]
    binding_ids = [entry["binding"] for entry in bindings]
    if len(event_ids) != len(set(event_ids)) or len(binding_ids) != len(set(binding_ids)):
        raise ValueError(f"{input_path.name} produced duplicate normalized pointer input")
    return {
        "id": source_id,
        "source": relative_path(input_path, legacy_root),
        "active_pointer_events": len(events),
        "active_pointer_bindings": len(bindings),
        "events": events,
        "bindings": bindings,
    }


def collect_input_cases(legacy_root: Path) -> dict[str, Any]:
    sources = [
        collect_switch_key_source(legacy_root, source_id, source_path)
        for source_id, source_path in INPUT_KEY_SOURCES
    ]
    sources.extend(
        collect_conditional_key_source(
            legacy_root, source_id, source_path, expected_event, method_ordinal
        )
        for source_id, source_path, expected_event, method_ordinal in INPUT_CONDITIONAL_KEY_SOURCES
    )
    cases = [entry for source in sources for entry in source["cases"]]
    bindings = [entry for source in sources for entry in source["bindings"]]
    source_summaries = [
        {key: value for key, value in source.items() if key not in {"cases", "bindings"}}
        for source in sources
    ]
    for source_path in FULL_POINTER_COVERAGE_PATHS:
        selected_pairs: list[tuple[str, int]] = []
        for source in INPUT_POINTER_SOURCES:
            if source[1] != source_path:
                continue
            if len(source) not in {4, 5}:
                raise ValueError(f"{source_path} full pointer coverage requires method ordinals")
            expected_events, method_ordinals = source[2], source[3]
            selected_pairs.extend((event, method_ordinals[event]) for event in expected_events)
        input_path = legacy_root / source_path
        source_text = strip_java_comments(
            input_path.read_text(encoding="utf-8", errors="replace")
        )
        actual_counts: dict[str, int] = {}
        actual_pairs: set[tuple[str, int]] = set()
        for method_match in INPUT_POINTER_METHOD.finditer(source_text):
            event = method_match.group("event")
            actual_counts[event] = actual_counts.get(event, 0) + 1
            actual_pairs.add((event, actual_counts[event]))
        if len(selected_pairs) != len(set(selected_pairs)) or set(selected_pairs) != actual_pairs:
            raise ValueError(f"{input_path.name} pointer method coverage differs from expected")

    pointer_sources = [
        collect_pointer_source(legacy_root, *source)
        for source in INPUT_POINTER_SOURCES
    ]
    pointer_events = [entry for source in pointer_sources for entry in source["events"]]
    pointer_bindings = [entry for source in pointer_sources for entry in source["bindings"]]
    pointer_source_summaries = [
        {key: value for key, value in source.items() if key not in {"events", "bindings"}}
        for source in pointer_sources
    ]
    case_ids = [entry["case"] for entry in cases] + [
        entry["event_id"] for entry in pointer_events
    ]
    binding_ids = [entry["binding"] for entry in bindings + pointer_bindings]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Legacy key sources produced duplicate normalized cases")
    if len(binding_ids) != len(set(binding_ids)):
        raise ValueError("Legacy key sources produced duplicate normalized bindings")
    return {
        "sources": source_summaries,
        "active_key_cases": len(cases),
        "active_key_bindings": len(bindings),
        "events": {
            event: sum(entry["event"] == event for entry in cases)
            for event in ("keyPressed", "keyReleased")
        },
        "cases": cases,
        "bindings": bindings,
        "pointer_sources": pointer_source_summaries,
        "active_pointer_events": len(pointer_events),
        "active_pointer_bindings": len(pointer_bindings),
        "pointer_events": pointer_events,
        "pointer_bindings": pointer_bindings,
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
    input_bindings: dict[str, str],
    fingerprint: str,
) -> tuple[
    dict[str, list[str]],
    dict[str, list[str]],
    dict[str, list[str]],
    dict[str, list[str]],
    dict[str, list[str]],
    dict[str, list[str]],
]:
    if matrix.get("schema_version") != 34:
        raise ValueError("Matrix schema_version must be 34")
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
    matrix_ids_by_input_binding: dict[str, list[str]] = defaultdict(list)
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
            "legacy_input_bindings",
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
            "legacy_input_bindings",
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
            "legacy_input_bindings",
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
        implied_input_cases: set[str] = set()
        for binding in row["legacy_input_bindings"]:
            if binding not in input_bindings:
                raise ValueError(
                    f"{row_id}: input binding is outside the normalized legacy input inventory: {binding}"
                )
            implied_input_cases.add(input_bindings[binding])
            matrix_ids_by_input_binding[binding].append(row_id)
        if set(row["legacy_input_cases"]) != implied_input_cases:
            raise ValueError(
                f"{row_id}: legacy_input_cases must equal the cases implied by legacy_input_bindings"
            )
        for input_case in implied_input_cases:
            if input_case not in input_cases:
                raise ValueError(
                    f"{row_id}: input case is outside the active legacy input inventory: {input_case}"
                )
            matrix_ids_by_input_case[input_case].append(row_id)
    return (
        {key: sorted(ids) for key, ids in matrix_ids_by_config_key.items()},
        {key: sorted(ids) for key, ids in matrix_ids_by_menu_key.items()},
        {label: sorted(ids) for label, ids in matrix_ids_by_menu_label.items()},
        {key: sorted(ids) for key, ids in matrix_ids_by_shortcut.items()},
        {case: sorted(ids) for case, ids in matrix_ids_by_input_case.items()},
        {binding: sorted(ids) for binding, ids in matrix_ids_by_input_binding.items()},
    )


def build_inventory(legacy_root: Path, matrix_path: Path) -> dict[str, Any]:
    validate_comment_stripper()
    validate_input_parser()
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
        matrix_ids_by_input_binding,
    ) = validate_matrix(
        matrix,
        legacy_root,
        set(config_references),
        {entry["key"] for entry in menu["keys"]},
        {entry["label"] for entry in menu["literal_labels"]},
        {entry["shortcut"] for entry in menu["accelerators"]},
        {entry["case"] for entry in input_inventory["cases"]}
        | {entry["event_id"] for entry in input_inventory["pointer_events"]},
        {entry["binding"]: entry["case"] for entry in input_inventory["bindings"]}
        | {
            entry["binding"]: entry["event_id"]
            for entry in input_inventory["pointer_bindings"]
        },
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
    input_inventory["bindings"] = [
        {
            **entry,
            "matrix_ids": matrix_ids_by_input_binding.get(entry["binding"], []),
        }
        for entry in input_inventory["bindings"]
    ]
    input_inventory["pointer_events"] = [
        {
            **entry,
            "matrix_ids": matrix_ids_by_input_case.get(entry["event_id"], []),
        }
        for entry in input_inventory["pointer_events"]
    ]
    input_inventory["pointer_bindings"] = [
        {
            **entry,
            "matrix_ids": matrix_ids_by_input_binding.get(entry["binding"], []),
        }
        for entry in input_inventory["pointer_bindings"]
    ]
    mapped_menu_keys = sum(bool(entry["matrix_ids"]) for entry in menu["keys"])
    mapped_menu_labels = sum(bool(entry["matrix_ids"]) for entry in menu["literal_labels"])
    mapped_shortcuts = sum(bool(entry["matrix_ids"]) for entry in menu["accelerators"])
    mapped_input_cases = sum(bool(entry["matrix_ids"]) for entry in input_inventory["cases"])
    mapped_input_bindings = sum(
        bool(entry["matrix_ids"]) for entry in input_inventory["bindings"]
    )
    mapped_pointer_events = sum(
        bool(entry["matrix_ids"]) for entry in input_inventory["pointer_events"]
    )
    mapped_pointer_bindings = sum(
        bool(entry["matrix_ids"]) for entry in input_inventory["pointer_bindings"]
    )
    if (
        mapped_input_cases != len(input_inventory["cases"])
        or mapped_input_bindings != len(input_inventory["bindings"])
        or mapped_pointer_events != len(input_inventory["pointer_events"])
        or mapped_pointer_bindings != len(input_inventory["pointer_bindings"])
    ):
        raise ValueError("Every normalized legacy input path must map to the matrix")

    return {
        "schema_version": 34,
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
            "Input key bindings symbolically expand Input.java, InputIndependentMainBoard.java, InputIndependentSubboard.java, InputSubboard.java, FloatBoard.java, AnalysisFrame table/window, DrawPainting.java, ChooseMoreEngine.java, LoadEngine.java, OtherPrograms.java, TencentKifuDownload.java, FoxKifuDownload.java, BrowserFrame.java, and CaptureTsumeGoFrame.java key dispatch, condition evaluations, executed statements, empty-listener and empty-statement paths, and switch fall-through; controlIsPressed means Control on every platform plus Meta on macOS, and BrowserFrame dispatches Enter through getKeyChar.",
            "Pointer bindings symbolically expand the main Input listener, the two indexed subboard listeners, FloatBoard, AnalysisFrame, DrawPainting, ChooseMoreEngine, LoadEngine, OtherPrograms, TencentKifuDownload, FoxKifuDownload, BrowserFrame load/stop/label listeners, JFontTextArea, JFontTextField, JIMSendTextPane, the two DemoScrollBarUI2 arrow-button listeners, JPaintTextPane, WindowMenuStrip, YikeLiveDialog, IndependentSubBoard and IndependentMainBoard lock/close/top-button plus window listeners, BlunderListPanel, SidebarHeaderPanel, BottomToolbar, ConfigDialog2 sidebar-nav/toggle-row/color-label listeners, MoreEngines, the 33 indexed LizzieFrame listeners, the 5 indexed Menu komi text/hold/hover listeners, and the 7 indexed MoveListFrame table/match-panel/header groups across mouse, motion, drag, wheel, and release condition evaluations, early returns, executed statements, and explicit no-action paths; data-dependent loops and click try/catch handlers are preserved as normalized atomic statements, local boolean tracking retains a known value across loops that can only assign the same literal, and direct variable-to-integer comparisons prune contradictory paths.",
            "Other key-listener and pointer-listener classes remain T-003 work.",
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
            "active_input_key_bindings": len(input_inventory["bindings"]),
            "mapped_input_key_bindings": mapped_input_bindings,
            "unmapped_input_key_bindings": len(input_inventory["bindings"])
            - mapped_input_bindings,
            "active_input_pointer_events": len(input_inventory["pointer_events"]),
            "mapped_input_pointer_events": mapped_pointer_events,
            "unmapped_input_pointer_events": len(input_inventory["pointer_events"])
            - mapped_pointer_events,
            "active_input_pointer_bindings": len(input_inventory["pointer_bindings"]),
            "mapped_input_pointer_bindings": mapped_pointer_bindings,
            "unmapped_input_pointer_bindings": len(input_inventory["pointer_bindings"])
            - mapped_pointer_bindings,
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
