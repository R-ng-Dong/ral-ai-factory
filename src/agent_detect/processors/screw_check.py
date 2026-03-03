from typing import Any
from PySide6.QtWidgets import QVBoxLayout
from ultralytics.engine.results import Results

from .base import Processor, ConfigPanel, ProcessResult

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QTableWidgetItem,
    QTableWidget,
    QInputDialog,
    QMessageBox,
    QHeaderView,
    QHBoxLayout,
    QPushButton,
    QCheckBox,
    QSpinBox,
    QWidget,
)
from PySide6.QtCore import Qt


def compare_object_counts(
    results: list[Results], required_counts: dict[int, int]
) -> dict[int, dict[str, Any]]:
    """
    So sánh số lượng vít phát hiện từ YOLO (theo class_id) với số lượng yêu cầu.

    Tham số:
        results: Danh sách kết quả từ YOLO.
        required_counts: Dict[class_id -> required_count].

    Trả về:
        Dict[class_id -> {'required', 'detected', 'match', 'difference'}]
    """
    detected_counts = {cid: 0 for cid in required_counts}

    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        for cls_val in boxes.cls:
            class_id = int(getattr(cls_val, "item", lambda: cls_val)())
            if class_id in required_counts:
                detected_counts[class_id] += 1

    return {
        cid: {
            "required": required_counts[cid],
            "detected": detected_counts[cid],
            "match": required_counts[cid] == detected_counts[cid],
            "difference": detected_counts[cid] - required_counts[cid],
        }
        for cid in required_counts
    }


class ScrewCheckProcessor(Processor):
    """Kiểm tra bắt vít dựa trên YOLO Results."""

    name = "Kiểm tra bắt vít"

    def __init__(self):
        self.settings: dict[str, Any] = {}
        self.panel = ScrewCheckConfigPanel()

    def configure(self, settings: dict[str, Any]) -> None:
        self.settings = settings or {}

    def reset(self) -> None:
        self.settings.clear()

    def dump_settings(self) -> dict[str, Any]:
        return self.panel.dump_settings()

    def load_settings(self, s: dict[str, Any]) -> None:
        self.panel.load_settings(s)

    def process(self, yolo_results: list[Results]) -> ProcessResult:
        if not yolo_results:
            return ProcessResult(status="ERR", yolo_results=[])

        screws = self.settings.get("screws")
        qtys = self.settings.get("quantity")
        if not screws or not qtys or len(screws) != len(qtys):
            return ProcessResult(status="ERR", yolo_results=yolo_results)

        try:
            cid_list = [int(x) for x in screws]
            qty_list = [int(x) for x in qtys]
        except Exception:
            return ProcessResult(status="ERR", yolo_results=yolo_results)

        required_counts = dict(zip(cid_list, qty_list))
        comparison = compare_object_counts(yolo_results, required_counts)
        status = "OK" if all(v["match"] for v in comparison.values()) else "NG"
        return ProcessResult(status=status, yolo_results=yolo_results)


TEST_SCREW = {0: "Vít loại 1", 1: "Vít loại 2"}


class ScrewCheckConfigPanel(ConfigPanel):
    configChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._screws: dict[int, str] = TEST_SCREW
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table_widget = QTableWidget(self)
        self._table_widget.setColumnCount(3)
        self._table_widget.setHorizontalHeaderLabels(["Loại vít", "Số lượng", "Chọn"])
        self._table_widget.cellDoubleClicked.connect(self._on_cell_double_clicked)

        header = self._table_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._table_widget.setColumnWidth(1, 80)
        self._table_widget.setColumnWidth(2, 40)
        self._table_widget.setMinimumSize(200, 100)

        button_layout = QHBoxLayout()
        add_button = QPushButton("Thêm")
        add_button.clicked.connect(self._show_add_dialog)

        delete_button = QPushButton("Xóa")
        delete_button.clicked.connect(self._delete_selected_rows)
        delete_button.setStyleSheet(
            "QPushButton {background-color: #e74c3c;color: white;border: none;}"
            "QPushButton:hover {background-color: #c0392b;}"
            "QPushButton:pressed {background-color: #a93226;}"
        )
        button_layout.addWidget(add_button)
        button_layout.addWidget(delete_button)

        layout.addWidget(self._table_widget)
        layout.addLayout(button_layout)

    def _show_add_dialog(self):
        if not self._screws:
            QMessageBox.warning(self, "Cảnh báo", "Danh sách phân loại vít trống!")
            return

        names = list(self._screws.values())
        name, ok = QInputDialog.getItem(
            self, "Chọn loại vít", "Chọn một loại:", names, 0, False
        )
        if ok and name:
            cid = next((k for k, v in self._screws.items() if v == name), None)
            if cid is not None:
                self._add_row(cid, 0)

    def _add_row(self, cid: int, quantity: int) -> None:
        if cid is None or cid not in self._screws:
            return

        row = self._table_widget.rowCount()
        self._table_widget.insertRow(row)

        name = self._screws[cid]
        item = QTableWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, cid)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self._table_widget.setItem(row, 0, item)

        container_qty = QWidget()
        spinbox = QSpinBox()
        spinbox.setRange(0, 100)
        spinbox.setValue(int(quantity))
        spinbox.setStyleSheet("QSpinBox::up-button, QSpinBox::down-button { width: 0; }")
        spinbox.valueChanged.connect(lambda _v: self.configChanged.emit())
        lay_qty = QHBoxLayout(container_qty)
        lay_qty.setContentsMargins(0, 0, 0, 0)
        lay_qty.addWidget(spinbox)
        self._table_widget.setCellWidget(row, 1, container_qty)

        container_chk = QWidget()
        checkbox = QCheckBox()
        lay_chk = QHBoxLayout(container_chk)
        lay_chk.setContentsMargins(0, 0, 0, 0)
        lay_chk.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay_chk.addWidget(checkbox)
        self._table_widget.setCellWidget(row, 2, container_chk)

        self.configChanged.emit()

    def _on_cell_double_clicked(self, row: int, column: int) -> None:
        if column != 0:
            return
        item = self._table_widget.item(row, 0)
        if not item:
            return
        names = list(self._screws.values())
        new_name, ok = QInputDialog.getItem(
            self, "Đổi loại vít", "Tên mới:", names, 0, False
        )
        if not ok:
            return
        item.setText(new_name)
        self.configChanged.emit()

    def _delete_selected_rows(self):
        rows_to_delete = []
        for row in range(self._table_widget.rowCount()):
            container = self._table_widget.cellWidget(row, 2)
            checkbox = container.findChild(QCheckBox) if container else None
            if checkbox and checkbox.isChecked():
                rows_to_delete.append(row)

        if not rows_to_delete:
            QMessageBox.information(self, "Thông báo", "Không có hàng nào được chọn để xóa!")
            return

        for row in reversed(rows_to_delete):
            self._table_widget.removeRow(row)
        self.configChanged.emit()

    def set_class_names(self, class_names: dict[int, str]) -> None:
        if not class_names:
            return
        self._screws = class_names
        for r in range(self._table_widget.rowCount()):
            item = self._table_widget.item(r, 0)
            if not item:
                continue
            cid = int(item.data(Qt.ItemDataRole.UserRole))
            if cid is not None:
                item.setText(class_names[cid])

    def load_settings(self, s: dict[str, Any]) -> None:
        self._screws = s.get("name", TEST_SCREW)
        screws = s.get("screws", [])
        qtys = s.get("quantity", [])
        for cid, q in zip(screws, qtys):
            self._add_row(int(cid), int(q) or 0)

    def dump_settings(self) -> dict[str, Any]:
        settings = {"name": self._screws, "screws": [], "quantity": []}
        for row in range(self._table_widget.rowCount()):
            item = self._table_widget.item(row, 0)
            cid = int(item.data(Qt.ItemDataRole.UserRole)) if item else None
            qty_container = self._table_widget.cellWidget(row, 1)
            spinbox = qty_container.findChild(QSpinBox) if qty_container else None
            qv = int(spinbox.value()) if spinbox else 0
            if cid is not None:
                settings["screws"].append(cid)
                settings["quantity"].append(qv)
        return settings
