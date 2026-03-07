# processors/base.py
from __future__ import annotations
from typing import Any, Protocol, ClassVar
from dataclasses import dataclass
from ultralytics.engine.results import Results
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal


@dataclass
class ProcessResult:
    status: str
    yolo_results: list[Results]
    meta: dict[str, Any] = None


class Processor(Protocol):
    """Giao diện plugin hậu xử lý."""

    name: str
    panel: ConfigPanel

    def configure(self, settings: dict[str, Any]) -> None: ...
    def reset(self) -> None: ...
    def process(self, yolo_results: list[Any]) -> ProcessResult: ...
    def dump_settings(self) -> dict[str, Any]: ...
    def load_settings(self, s: dict[str, Any]) -> None: ...

    # Khuyến nghị: trả {"result": "OK/NG/ERR/N/A", "meta": {...}}


class ConfigPanel(QWidget):
    """Panel cấu hình cho một processor."""

    configChanged: ClassVar[Signal]

    def set_class_names(self, class_names: dict[int, str]) -> None: ...
    def load_settings(self, s: dict[str, Any]) -> None: ...
    def dump_settings(self) -> dict[str, Any]: ...
