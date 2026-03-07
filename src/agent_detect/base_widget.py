"""
Module cung cấp lớp BaseYoloAgent - Trái tim xử lý AI của hệ thống.

Lớp này quản lý vòng đời của mô hình YOLO, điều phối luồng dữ liệu hình ảnh
giữa camera và worker, đồng thời tích hợp các bộ hậu xử lý (Post-processors)
để đưa ra kết luận cuối cùng (OK/NG, ...).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import numpy as np
from ultralytics.engine.results import Results

from PySide6.QtWidgets import QWidget, QFileDialog, QApplication, QMenu
from PySide6.QtCore import Signal, QTimer, Qt, QPoint
from PySide6.QtGui import QAction

from .ui.yolo_agent_ui import Ui_Form
from .utils import ShowResultsDialog
from .utils.common import plot, put_status, draw_info_box
from .worker import YoloWorker

from .processors._thresh_Check import ThreshCheck

from .processors.base import Processor, ConfigPanel, ProcessResult
from .processors.color_check import ColorCheckProcessor
from .processors.solder_check import SoilderCheckProcessor
from .processors.screw_check import ScrewCheckProcessor


class BaseYoloAgent(QWidget, Ui_Form):
    """
    Widget quản lý luồng xử lý YOLO và các bộ hậu xử lý pluggable.

    BaseYoloAgent đóng vai trò là một trung tâm điều phối (Coordinator):
    1. Nhận Frame từ camera.
    2. Kiểm tra điều kiện ánh sáng (ThreshCheck).
    3. Gửi Frame vào luồng Worker để nhận diện đối tượng bằng YOLO.
    4. Nhận kết quả YOLO và đẩy qua bộ lọc Post-processor đang được chọn (Color, Solder...).
    5. Phát tín hiệu kết quả để hiển thị trên GUI hoặc điều khiển Robot/PLC.

    Attributes:
        processorChanged (Signal): Phát ra khi có sự thay đổi thông số trên giao diện
            (thường dùng để hiển thị dấu '*' báo hiệu chưa lưu).
        frame_ready (Signal): Phát ra ảnh đã được vẽ kết quả nhận diện (annotated frame).
        result_ready (Signal): Phát ra đối tượng ProcessResult chứa kết quả phân tích cuối cùng.
    """

    processorChanged = Signal(
        object
    )  # Phát ra khi UI của processor có thay đổi (hiển thị dấu * - chưa lưu)
    frame_ready = Signal(np.ndarray)  # Frame đã (hoặc chưa) được vẽ kết quả
    result_ready = Signal(ProcessResult)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setupUi(self)

        # Initialize UI elements
        self.comboMode.clear()

        # Connect signals to slots
        self.processorChanged.connect(self._on_processor_changed)
        self.comboMode.currentIndexChanged.connect(self._sêlect_processor)
        self.btnComfirm.clicked.connect(self._on_confirm)
        self.btnSelectModel.clicked.connect(self._select_model)
        self.btnSelectModel.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.btnSelectModel.customContextMenuRequested.connect(self._show_model_menu)

        # Start worker after event loop starts (prevents race at construction time)
        QTimer.singleShot(0, self._start)

        # Ensure we stop cleanly when the app is quitting
        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self._stop)

        # Initialize active processor
        self.active_name: str | None = None

        # Initialize worker state
        self._worker_thread: YoloWorker | None = None
        self._model_path: str | None = None
        self._model_name: dict[int, str] = {}

        # Initialize threshold settings
        self.thresh_config = ThreshCheck(self)
        self.bnThreshConfig.clicked.connect(
            self.thresh_config.show
        )  # lambda: self.thresh_config.show)

        # Initialize Results dialog
        self.plot_config = ShowResultsDialog(self)
        self.bnResultShow.clicked.connect(self.plot_config.show)

        # Initialize default processors
        self.add_processor(ColorCheckProcessor())
        self.add_processor(SoilderCheckProcessor())
        self.add_processor(ScrewCheckProcessor())

    # ----------------------------- Properties -----------------------------
    @property
    def _model_conf(self) -> int:
        return self.spinConf.value()

    @_model_conf.setter
    def _model_conf(self, value: int):
        self.spinConf.setValue(value)

    @property
    def _active_proc(self) -> Processor:
        proc = self.comboMode.currentData()
        return proc

    @_active_proc.setter
    def _active_proc(self, index: int):
        if self.comboMode.count() <= 0:
            return
        self.comboMode.setCurrentIndex(index)
        self.stackPanel.setCurrentIndex(index)

    # ----------------------------- Qt Events -----------------------------

    def closeEvent(self, e) -> None:
        """
        Ensure worker is stopped before the widget is destroyed.
        """
        self._stop()
        super().closeEvent(e)

    # ----------------------------- Public API -----------------------------

    def on_frame_ready(self, frame: np.ndarray) -> None:
        """Điểm nhập cho khung hình vào pipeline (ví dụ: từ camera).

        Nếu có worker đang xử lý thì gửi khung cho worker; nếu không sẽ phát khung thô ra ngoài.
        """
        result = self.thresh_config.run(frame)
        if not result:
            f = put_status(
                frame,
                f"KHONG PHAT HIEN. DO SANG TRUNG BINH: {self.thresh_config._avg_brightness}",
                1.2,
            )
            result = ProcessResult(status="N/A", yolo_results=[])
            self.frame_ready.emit(f)
            self.result_ready.emit(result)
            return

        if self._worker_thread and self._worker_thread._model:
            self._worker_thread.on_frame_ready(frame)
        else:
            self.frame_ready.emit(frame)

    # ----------------------------- Worker Hooks ---------------------------

    def _on_yolo_result(self, results: list[Results]) -> None:
        """
        Receive YOLO results and pass through the current processor.
        """
        if self._active_proc is None:
            return
        try:
            frame = plot(results[0], **self.plot_config.to_dict())

            output = self._active_proc.process(results)

            frame = put_status(frame, output.status, 1.2)
            
            # Nếu có thông tin meta (như trong ScrewCheck), vẽ overlay
            if output.meta:
                frame = draw_info_box(frame, output.meta)

            self.frame_ready.emit(frame)
            self.result_ready.emit(output)
        except Exception as e:
            print("\rLỗi xử lý processor:", e, end="", flush=True)

    def _show_model_menu(self, pos: QPoint) -> None:
        """
        Hiện context menu khi right-click lên nút chọn model.
        """
        if not hasattr(self, "btnSelectModel"):
            return

        menu = QMenu(self)
        act_clear = QAction("Xoá model", self)
        act_clear.triggered.connect(self.__clear_model)
        # Vô hiệu hoá nếu chưa có model nào được nạp
        # act_clear.setEnabled(self._model_path is not None)

        menu.addAction(act_clear)

        # Hiển thị menu tại vị trí global của con trỏ trên nút
        global_pos = self.btnSelectModel.mapToGlobal(pos)
        menu.exec(global_pos)

    # ----------------------------- Lifecycle -----------------------------

    def _start(self) -> None:
        """
        Create and start the worker thread, and wire connections.
        """
        if self._worker_thread is not None:
            print("⚠️ Worker đã tồn tại, không tạo mới")
            return  # already started

        self._worker_thread = YoloWorker(self)

        # self._worker_thread.frame_ready.connect(
        #     self.frame_ready, Qt.ConnectionType.QueuedConnection
        # )
        self._worker_thread.result_ready.connect(
            self._on_yolo_result, Qt.ConnectionType.QueuedConnection
        )
        self._worker_thread.start()

        # Confidence spin box (0-100 UI → 0.0-1.0 model)
        if hasattr(self, "spinConf"):
            self.spinConf.valueChanged.connect(
                lambda v: self._worker_thread.set_conf(v / 100.0)
                if self._worker_thread
                else None
            )

    def _stop(self) -> None:
        """
        Gracefully stop the worker thread and free resources.
        """
        wt = self._worker_thread
        if wt is None:
            return

        try:
            wt.requestInterruption()  # ask run() loop to stop
            wt.stop()  # set _running False & quit()
            wt.wait()  # block until finished
        except Exception:
            pass
        finally:
            try:
                wt.deleteLater()
            except Exception:
                pass
            self._worker_thread = None

    # ----------------------------- UI Actions ----------------------------

    def _select_model(self) -> None:
        """
        Let the user pick a .pt file and set it on the worker.
        """
        f, _ = QFileDialog.getOpenFileName(
            self, "Chọn model file", "", "Model Files (*.pt)"
        )
        self.__load_model(f)

    def __load_model(self, f: str | Path | None) -> None:
        if f and self._worker_thread:
            self._model_path = Path(f).as_posix()
            m = self._worker_thread.set_model(Path(f))
            self._model_name = m.names
            if self._active_proc and hasattr(self._active_proc, "panel"):
                self._active_proc.panel.set_class_names(self._model_name)
            try:
                self.btnSelectModel.setText(Path(f).name)
            except Exception:
                pass

    def __clear_model(self) -> None:
        """Xoá model đang chạy khỏi worker và reset UI."""
        self._model_path = None
        # gọi slot clear_model trong worker thread bằng QueuedConnection
        if self._worker_thread:
            self._worker_thread.clear_model()
        # Cập nhật nút hiển thị tên file
        if hasattr(self, "btnSelectModel"):
            try:
                self.btnSelectModel.setText("Chọn mô hình")
            except Exception:
                pass

    def add_processor(self, processor: Processor) -> None:
        """
        Register a processor and its config panel into the UI.
        """
        self.comboMode.addItem(processor.name, processor)
        self.stackPanel.addWidget(processor.panel)  # Attach the processor's panel

    def _sêlect_processor(self, index: int) -> None:
        self._active_proc = index

        for i in range(self.comboMode.count()):
            text = self.comboMode.itemText(i)
            self.comboMode.setItemText(i, text.removesuffix("*"))

        self.processorChanged.emit(1)
        self.active_name = self._active_proc.name
        self._active_proc.panel.set_class_names(self._model_name)
        self._active_proc.panel.configChanged.connect(
            self._on_processor_changed, Qt.ConnectionType.UniqueConnection
        )

    def _on_processor_changed(self) -> None:
        """
        UI decoration: add '*' to current combo item to indicate unsaved changes.
        """
        current_index = self.comboMode.currentIndex()
        if current_index < 0:
            return
        current_text = self.comboMode.itemText(current_index)
        if not current_text.endswith("*"):
            self.comboMode.setItemText(current_index, current_text + "*")

    def _on_confirm(self) -> None:
        """
        Apply current panel settings to the active processor and clear the '*'.
        """
        current_index = self.comboMode.currentIndex()
        if current_index < 0:
            print("Error: No processor selected in combo")
            return

        # Remove asterisk from the current item
        current_text = self.comboMode.itemText(current_index)
        self.comboMode.setItemText(current_index, current_text.removesuffix("*"))

        # Extract settings from current panel
        config_panel = self.stackPanel.currentWidget()
        if config_panel is None:
            print("Error: No config panel selected")
            return
        if not isinstance(config_panel, ConfigPanel):
            print(f"Error: Invalid panel type: {type(config_panel).__name__}")
            return
        if self._active_proc is None:
            print("Error: No processor selected")
            return

        # Apply settings
        settings = config_panel.dump_settings()
        self._active_proc.configure(settings)
        print("Applied settings:", settings) if self.sender() else None

    def dump_settings(self) -> dict[str, Any]:
        """
        Lưu cả:
          - đường dẫn model (nếu có)
          - độ tự tin conf (0..1)
          - processor đang chọn
          - cấu hình panel hiện tại (nếu có)
        """
        panel_cfg: dict[str, Any] = {}
        if self._active_proc and isinstance(self._active_proc.panel, ConfigPanel):
            try:
                panel_cfg = self._active_proc.panel.dump_settings()
            except Exception:
                panel_cfg = {}

        data: dict[str, Any] = {
            "model_path": self._model_path,
            "model_conf": self._model_conf,
            "active_index": self.comboMode.currentIndex(),
            "active_name": self._active_proc.name if self._active_proc else None,
            "panel": panel_cfg,
            "thresh_config": self.thresh_config.to_dict(),
            "plot_config": self.plot_config.to_dict(),
        }
        return data

    def load_settings(self, settings: dict[str, Any]):
        if not settings:
            return
        self.__load_model(settings.get("model_path"))
        self._model_conf = settings.get("model_conf", 50)
        self._active_proc = settings.get("active_index", 0)
        self._active_proc.load_settings(settings.get("panel", {}))

        self.plot_config.from_dict(settings.get("plot_config", {}))
        self.thresh_config.from_dict(settings.get("thresh_config", {}))

        # if "processor_index" in settings:
        #     self._switch_processor(settings["processor_index"])
        # if "model_path" in settings:
        #     self.__load_model(settings["model_path"])
        # if "model_conf" in settings:
        #     self.spinConf.setValue(settings["model_conf"])
        # if "panel" in settings:
        #     self._active_proc.panel.load_settings(settings["panel"]) if self._active_proc else None
        # if "thresh_config" in settings:
        #     self.thresh_config.from_dict(settings["thresh_config"])
        # if "plot_config" in settings:
        #     self.plot_config.from_dict(settings["plot_config"])
        self._on_confirm()


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    w = BaseYoloAgent()
    w.show()
    sys.exit(app.exec())
