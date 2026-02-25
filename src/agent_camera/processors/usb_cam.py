"""Module xử lý camera USB sử dụng OpenCV (VideoCapture).

Cung cấp lớp `UsbCameraProcessor` và bảng cấu hình `UsbCameraConfigPanel` phục vụ
việc quét thiết bị USB, điều khiển phơi sáng, trigger-mode và các tuỳ chọn nâng cao.
"""



from dataclasses import dataclass
from typing import Optional, Any, Tuple, Union, Sequence, List
# from collections.abc import Sequence
import sys

import cv2
import numpy as np
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtWidgets import (
    QToolButton,
    QMenu,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QMessageBox,
    QWidget,
)

from .base import Processor, ConfigPanel, CamSettings
from .worker import Worker


@dataclass
class _OpenCvCaps:
    # Một số backend/property phổ biến
    CAP_DSHOW: int = getattr(cv2, "CAP_DSHOW", 700)  # Windows DirectShow
    CAP_MSMF: int = getattr(cv2, "CAP_MSMF", 1400)  # Windows Media Foundation
    CAP_V4L2: int = getattr(cv2, "CAP_V4L2", 200)  # Linux V4L2

    PROP_EXPOSURE: int = getattr(cv2, "CAP_PROP_EXPOSURE", 15)
    PROP_AUTO_EXPOSURE: int = getattr(cv2, "CAP_PROP_AUTO_EXPOSURE", 21)
    PROP_FRAME_WIDTH: int = getattr(cv2, "CAP_PROP_FRAME_WIDTH", 3)
    PROP_FRAME_HEIGHT: int = getattr(cv2, "CAP_PROP_FRAME_HEIGHT", 4)
    PROP_FPS: int = getattr(cv2, "CAP_PROP_FPS", 5)


CAPS = _OpenCvCaps()
_PREFERRED_RES = [(2560, 1440)]


class UsbCameraProcessor(Processor):
    """
    Processor cho USB cam dùng OpenCV. Giả lập trigger-mode bằng cờ _want_shot:
    - trigger_mode=False: trả khung liên tục (continuous).
    - trigger_mode=True: chỉ trả khung sau khi gọi trigger_once().
    """

    name = "USBCamera"

    # An toàn với numpy
    frame_ready = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.settings: CamSettings = CamSettings()
        self._panel = UsbCameraConfigPanel()
        self._worker: Optional[Worker] = None
        self._cap: Optional[cv2.VideoCapture] = None
        self.is_open: bool = False

        # config
        self._invert_rgb: bool = False
        self._cap_size = None

        # trigger emulate flag
        self._want_shot: bool = False

        # Wiring
        self.triggerSignal.connect(self.trigger_once)
        self._panel.settings_changed.connect(self.configure)
        self._panel.btn_capture.clicked.connect(self.trigger_once)
        self._panel.btn_toggle_connect.clicked.connect(
            self._on_toggle_connection_clicked
        )
        self._panel.menu_changed.connect(self._on_adv_changed)

    # -----------------
    # Lifecycle / config
    # -----------------
    def configure(self, s: CamSettings) -> None:
        # Lưu lại settings trước, một số property cần cap mở sẵn
        s = s or CamSettings()
        old = self.settings
        self.settings = s

        if not self._cap:
            return

        # Auto exposure (backend phụ thuộc nền tảng)
        if s.exposure_auto != old.exposure_auto:
            self._set_auto_exposure(s.exposure_auto)

        # Manual exposure
        if not s.exposure_auto and (s.exposure != old.exposure):
            self._set_exposure(s.exposure)

        # Trigger mode không có ở OpenCV, ta chỉ lưu để get_frame biết hành vi
        # (đã được cập nhật ở self.settings)

    def reset(self) -> None:
        self.settings = CamSettings()
        self._want_shot = False

    def connect_camera(self) -> bool:
        dev_index = self._panel.device_index
        if dev_index is None:
            self._panel.show_error("Chưa chọn thiết bị USB.")
            return False

        self.disconnect_camera()

        # Thử danh sách các backends theo thứ tự ưu tiên trên Windows
        # 0 (CAP_ANY) thường là tốt nhất để driver tự chọn
        # Ưu tiên CAP_DSHOW trên Windows vì nó ổn định hơn CAP_MSMF với nhiều loại camera
        backends = [CAPS.CAP_DSHOW, CAPS.CAP_MSMF, 0] if sys.platform == "win32" else [0, CAPS.CAP_V4L2]

        last_error = ""
        for backend in backends:
            try:
                print(f"   -> Thử mở USB Camera index {dev_index} với backend {backend}...")
                cap = cv2.VideoCapture(int(dev_index), backend)
                
                if cap and cap.isOpened():
                    # Thử đọc 1 frame để chắc chắn
                    ok, _ = cap.read()
                    if ok:
                        self._cap = cap
                        print(f"   ✓ USB Camera kết nối thành công (backend {backend})")
                        break
                    else:
                        print(f"   ⚠ Backend {backend} mở được nhưng không đọc được frame.")
                        cap.release()
                else:
                    if cap: cap.release()
            except Exception as e:
                last_error = str(e)
                continue
        
        if not self._cap or not self._cap.isOpened():
            self._panel.show_error(f"Không thể mở USB Camera (index={dev_index}).\n{last_error}")
            return False

        try:
            # ↓ giảm độ trễ: cố gắng đặt buffer size về 1 (nếu driver hỗ trợ)
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Đặt độ phân giải mặc định/ưu tiên
            self._ensure_default_resolution()
            
            # Áp settings hiện tại (auto/manual exposure…)
            # Dùng try-except cục bộ để lỗi set property không làm tèo connection
            try:
                self._apply_all_settings()
            except Exception as se:
                print(f"   ⚠ Không thể thiết lập thông số ban đầu: {se}")

            self._worker = Worker(self)
            self._worker.frame_ready.connect(
                self.__on_frame, Qt.ConnectionType.UniqueConnection
            )
            self._worker.start()

            self.is_open = True
            return True

        except Exception as e:
            print(f"❌ Lỗi khởi tạo sau khi kết nối USB cam: {e}")
            self.disconnect_camera()
            return False


    def disconnect_camera(self) -> bool:
        """Dừng worker trước, rồi giải phóng camera."""
        if self._worker:
            try:
                self._worker.stop()
            except Exception:
                pass
            finally:
                self._worker = None

        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            finally:
                self._cap = None

        self.is_open = False
        self.reset()
        return True

    # -------------
    # Frame piping
    # -------------
    def grab_frame(self, enabled: bool) -> bool:
        # Worker của bạn sẽ gọi get_frame theo chu kỳ có sẵn
        return True

    def _read_latest_frame(self, flush_count: int = 3) -> Optional[np.ndarray]:
        """
        Lấy khung mới nhất bằng cách 'flush' buffer:
        - gọi grab() flush_count-1 lần (bỏ khung cũ)
        - sau đó read() lấy khung cuối
        """
        if not self._cap or not self._cap.isOpened():
            return None

        # flush bớt khung cũ để tránh delay
        # Dùng grab() thay vì read() để nhanh hơn và giảm thiểu rủi ro memory allocation lỗi
        for _ in range(max(0, flush_count - 1)):
            try:
                if not self._cap.grab():
                    break
            except Exception:
                break

        try:
            ok, frame = self._cap.read()
            if not ok or frame is None:
                return None
            return frame
        except cv2.error as e:
            print(f"   ⚠ OpenCV Read Error: {e}")
            return None
        except Exception as e:
            print(f"   ⚠ Unexpected Read Error: {e}")
            return None

    def get_frame(self) -> Optional[np.ndarray]:
        """
        Continuous: trả frame ngay (sau khi flush nhẹ).
        Trigger mode: chỉ trả frame khi _want_shot = True rồi reset cờ.
        Luôn chuyển BGR -> RGB trước khi trả về.
        """
        if not self._cap:
            return None

        if self.settings.trigger_mode and not self._want_shot:
            return None

        # Đọc khung mới nhất (flush nhẹ để tránh chậm 1 frame)
        frame = self._read_latest_frame(flush_count=3)
        if frame is None:
            return None

        # Nếu ở trigger mode: một shot -> một frame
        if self.settings.trigger_mode:
            self._want_shot = False

        # ↓ Chuyển BGR → RGB để không bị ngược màu
        if self._invert_rgb:
            try:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            except Exception:
                pass

        return frame

    def trigger_once(self) -> None:
        """
        Với USB cam, ta giả lập trigger bằng cách đặt cờ cho phép get_frame trả 1 frame.
        """
        if self._cap and self.settings.trigger_mode:
            self._want_shot = True

    # -------------
    # Helpers
    # -------------
    def _apply_all_settings(self) -> None:
        # Auto exposure trước
        self._set_auto_exposure(bool(self.settings.exposure_auto))

        # Manual exposure sau
        if not self.settings.exposure_auto:
            self._set_exposure(int(self.settings.exposure))

    def _set_auto_exposure(self, enabled: bool) -> None:
        if not self._cap:
            return
        # Lưu ý: cv2 backend khác nhau dùng convention khác:
        # - V4L2: CAP_PROP_AUTO_EXPOSURE = 1: manual, 3: auto
        # - DirectShow/MSMF: đôi khi dùng 0=manual, 1=auto (hoặc ngược)
        try:
            if sys.platform.startswith("linux"):
                self._cap.set(CAPS.PROP_AUTO_EXPOSURE, 3 if enabled else 1)
            else:
                # Nhiều driver Windows dùng 0.25 (manual) và 0.75 (auto). Thử cả hai nhánh.
                val = 0.75 if enabled else 0.25
                self._cap.set(CAPS.PROP_AUTO_EXPOSURE, val)
        except Exception:
            pass

    def _set_exposure(self, value: int) -> None:
        if not self._cap:
            return
        # Thang đo exposure tuỳ driver (ms, log2, hay EV). Ta chỉ set trực tiếp:
        try:
            self._cap.set(CAPS.PROP_EXPOSURE, float(value))
        except Exception:
            pass

    def _on_toggle_connection_clicked(self) -> None:
        if self.is_open:
            ok = self.disconnect_camera()
        else:
            ok = self.connect_camera()
            # Sau khi connect xong, đọc ngay setting hiện tại từ panel
            self.configure(self._panel.dump_settings())

        if ok:
            self.panel.ui_update(self.is_open)

    def set_frame_size(self, w: int, h: int) -> None:
        if self._cap:
            self._cap.set(CAPS.PROP_FRAME_WIDTH, float(w))
            self._cap.set(CAPS.PROP_FRAME_HEIGHT, float(h))

    def _on_adv_changed(self, cfg: dict):
        # cfg = {"invert_rgb": bool, "frame_size": (w,h)|None}
        self._invert_rgb = cfg.get("invert_rgb", False)
        fs = cfg.get("frame_size")
        self._cap_size = fs
        # -> cập nhật processor: đảo màu + set frame size (nếu đang connected)
        if fs:
            self.set_frame_size(*fs)

    def __on_frame(self, frame: np.ndarray) -> None:
        self.frame_ready.emit(frame)
        # USB cam không có auto exposure query thống nhất, bỏ qua polling.

    def _ensure_default_resolution(self) -> Optional[Tuple[int, int]]:
        """
        Thử đặt độ phân giải 2K theo thứ tự ưu tiên. Trả về (w,h) nếu thành công, None nếu không đổi.
        """
        if not self._cap:
            return None

        size = self._cap_size
        if size:
            self.set_frame_size(*size)
            return size

        for w, h in _PREFERRED_RES:
            try:
                self._cap.set(CAPS.PROP_FRAME_WIDTH, float(w))
                self._cap.set(CAPS.PROP_FRAME_HEIGHT, float(h))
                # Một số driver cần 1 nhịp nhỏ để áp dụng
                try:
                    import time as _t

                    _t.sleep(0.05)
                except Exception:
                    pass
                got_w = int(self._cap.get(CAPS.PROP_FRAME_WIDTH) or 0)
                got_h = int(self._cap.get(CAPS.PROP_FRAME_HEIGHT) or 0)
                # chấp nhận sai số nhỏ do rounding/step của driver
                if abs(got_w - w) <= 16 and abs(got_h - h) <= 16:
                    return (got_w, got_h)
            except Exception:
                continue
        return None

    # -------------
    # UI plumbing
    # -------------
    @property
    def panel(self) -> ConfigPanel:
        return self._panel


class UsbCameraConfigPanel(ConfigPanel):
    """
    Panel điều khiển chuyên biệt cho các dòng Camera chuẩn USB (UVC).

    Sử dụng lại `Ui_Form` nhưng tùy biến logic cho phù hợp với OpenCV VideoCapture.
    Hỗ trợ cơ chế tự động quét cổng (Enumeration) và lọc index thiết bị.

    Attributes:
        settings_changed (Signal): Phát ra đối tượng CamSettings khi có bất kỳ thay đổi nào trên UI.
        menu_changed (Signal): Phát ra dictionary cấu hình nâng cao (invert_rgb, frame_size).
    """

    settings_changed = Signal(CamSettings)
    menu_changed = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setupUi(self)

        # Debounce phát settings
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(150)
        self._debounce.timeout.connect(self._emit_settings)

        self._setup_signals()

        # Nút capture phụ thuộc trigger mode
        self.trigger_mode_gui.toggled.connect(self.btn_capture.setEnabled)
        self.cbExposureAuto.currentIndexChanged.connect(self.leExposure.setDisabled)

        self.btnAdvanced = _AdvancedButton(self)
        self.btnAdvanced.menu_changed.connect(self.menu_changed.emit)
        self.gridLayout.addWidget(self.btnAdvanced, 6, 0, 1, 2)

    # -----------------
    # Properties
    # -----------------
    @property
    def device_index(self) -> Optional[int]:
        """
        Lấy index từ boxEnum (dạng 'USB#<n>').
        """
        txt = (self.boxEnum.currentText() or "").strip()
        if txt.startswith("USB#"):
            try:
                return int(txt.split("#", 1)[1])
            except ValueError:
                return None
        # fallback: nếu người dùng gõ số trực tiếp
        try:
            return int(txt)
        except ValueError:
            return None

    # override exposure/exposure_auto/trigger_mode của ConfigPanel đã đủ
    @property
    def exposure(self) -> int:
        text = (self.leExposure.text() or "").strip()
        try:
            return int(text)
        except ValueError:
            return 0

    @exposure.setter
    def exposure(self, value: int) -> None:
        self.leExposure.setText(str(int(value)))

    @property
    def exposure_auto(self) -> bool:
        """Trả về True nếu chế độ phơi sáng đang ở chế độ tự động.

        Hàm này chấp nhận cả các chuỗi hiển thị bằng tiếng Anh và tiếng Việt,
        ví dụ: "continuous", "auto", "on", hoặc "liên tục", "tự động", "bật".
        """
        txt = (self.cbExposureAuto.currentText() or "").strip().lower()
        return txt in {
            "continuous",
            "auto",
            "on",
        }

    @exposure_auto.setter
    def exposure_auto(self, enabled: bool) -> None:
        # Nếu combo của bạn có "Off"/"Continuous", ta map như Hik
        self.cbExposureAuto.setCurrentText("Continuous" if enabled else "Off")

    @property
    def trigger_mode(self) -> bool:
        return self.trigger_mode_gui.isChecked()

    @trigger_mode.setter
    def trigger_mode(self, mode: bool) -> None:
        self.trigger_mode_gui.setChecked(mode)

    # -----------------
    # Settings I/O
    # -----------------
    def dump_settings(self) -> CamSettings:
        # dev dùng cho USB index, ip không dùng
        txt = self.boxEnum.currentText() or ""
        dev = txt if txt else None
        return CamSettings(
            dev=dev,
            ip=None,
            exposure=self.exposure,
            exposure_auto=self.exposure_auto,
            trigger_mode=self.trigger_mode,
            advanced=self.btnAdvanced.to_dict(),
        )

    def load_settings(self, s: CamSettings) -> None:
        if not s:
            return
        if s.dev:
            if all(
                self.boxEnum.itemText(i) != s.dev for i in range(self.boxEnum.count())
            ):
                self.boxEnum.addItem(s.dev)
            self.boxEnum.setCurrentText(s.dev)
        self.exposure = s.exposure
        self.exposure_auto = s.exposure_auto
        self.trigger_mode = s.trigger_mode
        self.btnAdvanced.from_dict(s.advanced)

    # -----------------
    # UI behavior
    # -----------------
    def _setup_signals(self) -> None:
        widgets_and_signals: list[tuple[Any, str]] = [
            (self.leExposure, "editingFinished"),
            (self.cbExposureAuto, "currentIndexChanged"),
            (self.trigger_mode_gui, "toggled"),
            (self.boxEnum, "currentIndexChanged"),
        ]
        for w, sig in widgets_and_signals:
            s = getattr(w, sig, None)
            if s:
                s.connect(self._on_changed_and_blur, Qt.ConnectionType.UniqueConnection)

        self.btn_enum_device.clicked.connect(
            self.enum_devices, Qt.ConnectionType.UniqueConnection
        )

    def _on_changed_and_blur(self, *args):
        """Xử lý khi có thay đổi: Kích hoạt debounce và giải phóng focus khỏi widget."""
        # 1) phát debounce
        self._debounce.start()
        # 2) bỏ focus khỏi widget gửi signal
        w = self.sender()
        if isinstance(w, QWidget):
            # chuyển focus sang widget kế tiếp; nếu không chuyển được thì clearFocus
            QTimer.singleShot(0, lambda: (w.clearFocus()))

    def _emit_settings(self) -> None:
        self.settings_changed.emit(self.dump_settings())

    def enum_devices(self) -> Sequence[str]:
        """
        Quét index 0..9; luôn clear() trước rồi chỉ add danh sách mới.
        Dùng backend ít ồn nhất để quét.
        """
        found: list[str] = []
        self.boxEnum.clear()

        # Trên Windows, DSHOW thường ít ồn hơn MSMF khi quét index không tồn tại
        backend = CAPS.CAP_DSHOW if sys.platform == "win32" else CAPS.CAP_V4L2
        
        for idx in range(0, 5): # Giảm xuống 5 để quét nhanh hơn, thường cam chỉ ở index 0-2
            cap = None
            try:
                cap = cv2.VideoCapture(idx, backend)
                if cap and cap.isOpened():
                    label = f"USB#{idx}"
                    found.append(label)
                    cap.release()
                else:
                    if cap: cap.release()
            except Exception:
                if cap: cap.release()

        # Chỉ add kết quả mới tìm được
        for label in found:
            self.boxEnum.addItem(label)

        if not found:
            print("   -> Không tìm thấy thiết bị USB nào qua backend chính.")

        return found


    def _add_devices(self, labels: Sequence[str]) -> None:
        self.boxEnum.clear()
        for label in labels or ():
            self.boxEnum.addItem(label)

    def ui_update(self, connected: bool) -> None:
        self.btn_toggle_connect.setText("Ngắt kết nối" if connected else "Kết nối")
        self.boxEnum.setEnabled(not connected)
        self.btn_enum_device.setEnabled(not connected)
        self.trigger_mode_gui.setEnabled(connected)
        self.btn_capture.setEnabled(connected and self.trigger_mode_gui.isChecked())

    def show_error(self, msg: str) -> None:
        QMessageBox.critical(self, "Lỗi", msg)


class _AdvancedButton(QToolButton):
    """Nút menu nâng cao cho cấu hình USB camera.

    Cung cấp menu để:
        - Đảo màu RGB (invert)
        - Chọn kích thước khung hình (preset hoặc tuỳ chỉnh)

    Phát `menu_changed` mỗi khi có thay đổi cấu hình (invert_rgb/frame_size).
    """

    menu_changed = Signal(dict)  # emit {"invert_rgb": bool, "frame_size": (w,h)|None}

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._frame_size: Optional[tuple[int, int]] = (
            None  # None = không ép size (dùng mặc định)
        )
        self._build_ui()
        self._wire()

    # ---------- UI ----------
    def _build_ui(self):
        self.setText("Thêm")
        self.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self._add_style()

        self.mnuAdvanced = QMenu(self)

        # 1) Đảo màu
        self.actInvert = self.mnuAdvanced.addAction("Đảo màu RGB")
        self.actInvert.setCheckable(True)
        self.mnuAdvanced.addSeparator()

        # 2) Kích thước khung hình
        self.mnuSize = QMenu("Kích thước khung hình", self.mnuAdvanced)
        # Presets
        self._add_size_action(self.mnuSize, "2560 × 1440 (2K)", 2560, 1440)
        self._add_size_action(self.mnuSize, "2048 × 1080 (DCI-2K)", 2048, 1080)
        self._add_size_action(self.mnuSize, "1920 × 1080 (FHD)", 1920, 1080)
        self._add_size_action(self.mnuSize, "1280 × 720 (HD)", 1280, 720)
        self.mnuSize.addSeparator()
        # Custom
        self.actCustomSize = self.mnuSize.addAction("Tùy chỉnh…")
        self.mnuAdvanced.addMenu(self.mnuSize)

        self.setMenu(self.mnuAdvanced)

    def _add_style(self):
        # mũi tên lớn, chừa chỗ bên phải
        self.setStyleSheet("""
            QToolButton { padding-right: 28px; border-radius:6px; }
            QToolButton::menu-button {
                width: 16px
            }
        """)

    # ---------- Wiring ----------
    def _wire(self):
        # Click phần nút chính -> mở menu mặc định (hoặc bạn có thể mở dialog khác)
        # self.clicked.connect(self._open_something)
        self.actInvert.toggled.connect(lambda _on: self._emit_changed())
        self.actCustomSize.triggered.connect(self._on_custom_size)

    def _add_size_action(self, menu: QMenu, text: str, w: int, h: int):
        act = menu.addAction(text)
        act.triggered.connect(lambda _=False, W=w, H=h: self._on_size_preset(W, H))

    # ---------- Actions ----------
    def _on_size_preset(self, w: int, h: int):
        self._frame_size = (int(w), int(h))
        self._emit_changed()

    def _on_custom_size(self):
        dlg = _SizeDialog(self._frame_size, self)
        if dlg.exec():
            w, h = dlg.values()
            self._frame_size = (w, h)
            self._emit_changed()

    def _emit_changed(self):
        self.menu_changed.emit(self.to_dict())

    # ---------- Public API / Persist ----------
    def set_invert_checked(self, on: bool):
        """Set trạng thái checkbox đảo màu (không phát sự kiện).

        Args:
            on (bool): True để đánh dấu 'Đảo màu RGB'.
        """
        self.actInvert.setChecked(bool(on))

    def to_dict(self) -> dict:
        """Trả về dict cấu hình hiện tại để lưu/đọc nhanh.

        Returns:
            dict: {'invert_rgb': bool, 'frame_size': [w, h] | None}
        """
        return {
            "invert_rgb": self.actInvert.isChecked(),
            "frame_size": list(self._frame_size) if self._frame_size else None,
        }

    def from_dict(self, data: dict):
        """Áp dữ liệu cấu hình đã lưu lên nút menu (khởi tạo trạng thái).

        Args:
            data (dict): Dict có thể chứa 'invert_rgb' và 'frame_size'.
        """
        fs = (data or {}).get("frame_size")
        self.actInvert.setChecked(bool((data or {}).get("invert_rgb", False)))

        if isinstance(fs, (list, tuple)) and len(fs) == 2:
            try:
                self._frame_size = (int(fs[0]), int(fs[1]))
            except Exception:
                self._frame_size = None
        else:
            self._frame_size = None
        self._emit_changed()
        # không emit ở đây để tránh vòng lặp; nếu muốn, gọi self._emit_changed()


# ======= Dialog nhập W×H =======
class _SizeDialog(QDialog):
    """Dialog nhỏ cho nhập kích thước khung hình tuỳ chỉnh (W × H)."""

    def __init__(self, current: Optional[tuple[int, int]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kích thước tùy chỉnh")
        self.setModal(True)

        self.spinW = QSpinBox(self)
        self.spinH = QSpinBox(self)
        for sp in (self.spinW, self.spinH):
            sp.setRange(160, 7680)
            sp.setSingleStep(16)
        if current:
            self.spinW.setValue(int(current[0]))
            self.spinH.setValue(int(current[1]))
        else:
            self.spinW.setValue(2560)
            self.spinH.setValue(1440)

        row = QHBoxLayout()
        row.addWidget(QLabel("Rộng (W):"))
        row.addWidget(self.spinW)
        row.addSpacing(10)
        row.addWidget(QLabel("Cao (H):"))
        row.addWidget(self.spinH)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addLayout(row)
        lay.addWidget(btns)

    def values(self) -> tuple[int, int]:
        return int(self.spinW.value()), int(self.spinH.value())
