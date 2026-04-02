from pathlib import Path
import numpy as np
from ultralytics.models import YOLO
from PySide6.QtCore import QThread, Signal
from .utils import to_rgb
import cv2


class YoloWorker(QThread):
    """QThread for processing YOLO model predictions to prevent GUI freezing."""

    result_ready = Signal(
        list
    )  # Prediction results (Results)        # Comparison result and camera ID
    error = Signal(str)  # Error messages

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True

        self._model = None
        self._frame = None
        self._conf = 0.5

    def on_frame_ready(self, frame: np.ndarray):
        """Set frame for processing."""
        # Chỉ copy và lưu frame nếu worker đang rảnh (None)
        if self._frame is None:
            self._frame = frame.copy()

    def set_model(self, model: str | Path) -> YOLO:
        self._model = YOLO(model)
        return self._model

    def clear_model(self):
        self._frame = None
        self._model = None
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.synchronize()
                torch.cuda.empty_cache()
        except Exception:
            pass

    def set_conf(self, conf: float):
        self._conf = conf

    def run(self):
        while self._running and not self.isInterruptionRequested():
            if self._frame is None:
                self.msleep(10)
                continue
            try:
                frame = self._frame
                model = self._model
                conf = self._conf

                if model is None:
                    self.msleep(100) # Nghỉ lâu hơn nếu không có model
                    continue
                else:
                    # Tiền xử lý RGB trong luồng worker để giảm tải cho Main UI
                    input_frame = to_rgb(frame) 
                    # Log kích thước ảnh lần đầu hoặc khi đổi model
                    # if not hasattr(self, "_logged_once") or self._logged_once != frame.shape:
                    #     h, w, c = frame.shape
                    #     print(f"\n[AI Debug] Camera Frame Resolution: {w}x{h} (Channels: {c})")
                    #     self._logged_once = frame.shape

                    # Tăng imgsz=1280 để nhận diện vật thể nhỏ/xa tốt hơn
                    # result = model.predict(input_frame, conf=conf, verbose=False, imgsz=640)
                    result = model.predict(input_frame, conf=conf, verbose=False)
                    self.result_ready.emit(result)
            except Exception as e:
                import traceback
                self.error.emit(f"Prediction error: {str(e)}\n{traceback.format_exc()}")
            finally:
                self._frame = None
            
            # GIỚI HẠN TỐC ĐỘ AI (100ms = 10 FPS) để giảm tải CPU
            self.msleep(100)

        # điểm dọn dẹp cuối thread
        self._cleanup()

    def _cleanup(self):
        try:
            # Giải phóng model để cắt threads nội bộ của Torch/Ultralytics
            self._model = None
            # Nếu dùng CUDA, có thể cân nhắc:
            # import torch; torch.cuda.empty_cache()
        except Exception:
            pass

    def stop(self):
        """Gracefully stop the thread."""
        self._running = False
        self.requestInterruption()
        self.quit()
        self.wait() # Đảm bảo thread kết thúc hẳn

