"""Module chứa dialog quản lý các giao thức (ProtocolMain).

Cung cấp giao diện để thêm/xóa và quản lý kết nối các giao thức (ví dụ: TCP, MODBUS).
Module giữ logic tạo widget giao thức, menu ngữ cảnh, và chuyển tiếp dữ liệu RX/TX giữa dialog và các protocol widget.
"""

from PySide6.QtCore import Signal, Qt, QSize, QPoint

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QDialog,
    QMenu,
    QHBoxLayout,
    QListWidgetItem,
    QLabel,
    QToolButton,
)
from pathlib import Path

from .ui.animation.toggleButton import ToggleButton
from .ui import protocol_main_ui

from . import MODBUS, TCPClient, MODBUS_RTU

# from ..config import PROTOCOL_PATH

# from TCP_Protocol.TCPClient import TCPClient
# from Modbus_Protocol.MODBUS import MODBUS
# from ui.animation.toggleButton import ToggleButton
# from ui import protocol_main_ui

# PROTOCOL_PATH = Path(r"F:/WORK SPACE/2025/6. Solder_joint/runtime/protocol.json")

style = """
    QlistWidget::item QWidget#protocol_widget QLabel#item_label {
        
    }
"""

AVAILABLE_PROTOCOLS = {
    "TCPClient": TCPClient, 
    "MODBUS_TCP": MODBUS,
    "MODBUS_RTU": MODBUS_RTU
}


class CustomWidget(QWidget):
    def __init__(self, text=""):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # Remove margins for compact layout

        self.label = QLabel(text)
        self.label.setObjectName("item_label")

        layout2 = QHBoxLayout(self.label)
        layout2.setContentsMargins(0, 0, 0, 0)  # Remove margins for compact layout

        self.toggle = ToggleButton(height=28)
        layout.addWidget(self.label)
        layout2.addStretch()
        layout2.addWidget(self.toggle)

        self.setMinimumHeight(20)
        self.is_auto = False

    def auto_connect(self, state: int) -> None:
        self.toggle.setDisabled(bool(state))
        self.is_auto = state


class ProtocolMain(protocol_main_ui.Ui_Dialog, QDialog):
    rx_data = Signal(str)
    tx_data = Signal(str)

    def __init__(self, parent=None):
        super(ProtocolMain, self).__init__(parent)
        self.setupUi(self)

        item = QListWidgetItem()
        item.setSizeHint(QSize(36, 36))
        self.listProtocol.addItem(item)

        add_button = QToolButton(self)
        add_button.setText("➕")
        add_button.setFixedSize(32, 32)
        add_button.setStyleSheet("background-color: transparent")
        add_button.clicked.connect(self.add_item)
        self.listProtocol.setItemWidget(item, add_button)

        self.listProtocol.itemPressed.connect(
            lambda item: self.stackedProtocol.setCurrentIndex(
                self.listProtocol.row(item)
            )
        )
        # BƯỚC 1 & 2: Thiết lập chính sách và kết nối tín hiệu cho context menu
        self.listProtocol.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.listProtocol.customContextMenuRequested.connect(self.show_context_menu)

        # self.load_protocols()

    def closeEvent(self, arg__1: QCloseEvent) -> None:
        for i in range(self.listProtocol.count() - 1):
            protocol_widget = self.stackedProtocol.widget(i)
            protocol_widget.close()
        return super().closeEvent(arg__1)

    def show_context_menu(self, pos: QPoint):
        # Lấy item tại vị trí con trỏ chuột
        item = self.listProtocol.itemAt(pos)
        if item is None or self.listProtocol.row(item) == self.listProtocol.count() - 1:
            return

        # BƯỚC 3: Tạo và hiển thị menu
        menu = QMenu(self)
        delete_action = menu.addAction("Xoá")
        action = menu.exec(self.listProtocol.mapToGlobal(pos))

        # BƯỚC 4: Xử lý hành động xóa
        if action == delete_action:
            self.delete_item(item)

    def add_item(self):
        obj = self.sender()
        if not isinstance(obj, QToolButton):
            raise TypeError("Expected QToolButton as sender")
        if obj is None:
            raise RuntimeError("Sender is null")

        pos = self.listProtocol.mapToGlobal(obj.pos()) + QPoint(0, obj.height())

        menu = QMenu(self)
        for name, ctor in AVAILABLE_PROTOCOLS.items():
            menu.addAction(name, lambda *, c=ctor: self.add_protocol(c(self)))
        menu.exec(pos)

    def delete_item(self, item: QListWidgetItem) -> None:
        """
        Delete the protocol item at the given row and its corresponding widget from the stacked widget.
        """
        row = self.listProtocol.row(item)
        if (
            row == self.listProtocol.count() - 1
        ):  # Prevent deletion of the add button item
            return

        # Remove item from listProtocol
        self.listProtocol.takeItem(row)

        # Remove corresponding widget from stackedProtocol
        widget = self.stackedProtocol.widget(row)
        self.stackedProtocol.removeWidget(widget)

        # Clean up widget to prevent memory leaks
        if widget:
            widget.deleteLater()

        # Update current index if necessary
        if self.stackedProtocol.count() > 0:
            self.stackedProtocol.setCurrentIndex(
                min(row, self.stackedProtocol.count() - 1)
            )
        else:
            self.stackedProtocol.setCurrentIndex(-1)

    def add_protocol(self, protocol_widget):
        item = QListWidgetItem("Protocol")
        item.setSizeHint(QSize(0, 50))

        custom_widget = CustomWidget(text=f"{protocol_widget.__class__.__name__}")

        # Connect signals
        custom_widget.toggle.stateChanged.connect(protocol_widget.toggle_signal.emit)
        protocol_widget.auto_connect_notify.connect(custom_widget.auto_connect)
        protocol_widget.curr_connect_notify.connect(
            lambda state: custom_widget.toggle.setChecked(state)
        )
        protocol_widget.curr_connect_notify.connect(
            lambda state: custom_widget.toggle.setEnabled(
                state != 1 and not custom_widget.is_auto
            )
        )

        protocol_widget.rx_data.connect(self.rx_data.emit)
        self.tx_data.connect(protocol_widget.tx_data.emit)

        self.listProtocol.insertItem(self.listProtocol.count() - 1, item)
        self.listProtocol.setItemWidget(item, custom_widget)

        self.stackedProtocol.addWidget(protocol_widget)

    def to_dict(self) -> dict:
        """Chuyển danh sách giao thức thành dict mapping tên -> cấu hình.

        Trả về:
            dict: Key là tên giao thức, value là dict chứa 'type' và 'settings'.
        """
        protocols = {}
        for row in range(self.listProtocol.count() - 1):  # Exclude add button
            item = self.listProtocol.item(row)
            widget = self.listProtocol.itemWidget(item)
            protocol_widget = self.stackedProtocol.widget(row)
            if isinstance(widget, CustomWidget) and protocol_widget:
                protocol_name = (
                    widget.label.text() or f"protocol_{row}"
                )  # Fallback if name is empty
                protocols[protocol_name] = {
                    "type": protocol_widget.__class__.__name__,
                    "settings": getattr(protocol_widget, "settings", {}),
                }

        return protocols

    def from_dict(self, protocols: dict) -> None:
        for protocol_name, protocol_data in protocols.items():
            protocol_class = AVAILABLE_PROTOCOLS.get(protocol_data["type"])
            if protocol_class is None:
                continue
            settings = protocol_data.get("settings", {})
            # TRUYỀN PARENT
            protocol_instance = protocol_class(parent=self, **settings)
            self.add_protocol(protocol_instance)

            # set tên hiển thị
            item = self.listProtocol.item(self.listProtocol.count() - 2)
            if item:
                w = self.listProtocol.itemWidget(item)
                if isinstance(w, CustomWidget):
                    w.label.setText(protocol_name)

        if self.listProtocol.count() > 1:
            self.listProtocol.setCurrentRow(0)


if __name__ == "__main__":
    import sys
    from pathlib import Path
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QFile, QTextStream

    STYLE_PATH = Path(
        r"F:\WORK SPACE\2025\6. Solder_joint\resources\style\corporate.qss"
    )

    def apply_stylesheet(window):
        file = QFile(STYLE_PATH)
        if file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
            stream = QTextStream(file)
            stylesheet = stream.readAll()
            window.setStyleSheet(stylesheet)
            file.close()

    app = QApplication(sys.argv)

    dialog = ProtocolMain()
    apply_stylesheet(dialog)
    dialog.show()
    sys.exit(app.exec())
