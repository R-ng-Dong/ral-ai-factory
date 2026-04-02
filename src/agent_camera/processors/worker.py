"""
Module quản lý luồng thu nhận hình ảnh (Acquisition Thread).

Cung cấp lớp Worker chạy trên một luồng riêng biệt để liên tục lấy dữ liệu từ
Camera Processor và đẩy về luồng chính xử lý, giúp tối ưu hóa hiệu năng và
đảm bảo tính mượt mà của giao diện.
"""

import numpy as np
import time
from PySide6.QtCore import QThread, Signal
from .base import Processor


class Worker(QThread):
    """Thread worker lấy khung ảnh từ một Processor.

    Vòng đời:
        - `run` liên tục gọi `camera_instance.get_frame()` và phát `frame_ready` khi có khung.
        - `stop` dừng vòng lặp và chờ kết thúc thread an toàn.
    """

    frame_ready = Signal(np.ndarray)

    def __init__(self, camera_instance: Processor):
        super().__init__()
        self.camera_instance = camera_instance
        self._running = True

    def run(self):
        """Vòng lặp chính: lấy frame bằng `camera_instance.get_frame()` và phát `frame_ready`.

        Nếu `get_frame()` trả None thì tạm ngủ một khoảng ngắn để tránh busy-loop.
        """
        while self._running:
            try:
                frame = self.camera_instance.get_frame()
                if frame is None:
                    time.sleep(0.03) # Tăng lên 30ms cho camera thường
                    continue
                self.frame_ready.emit(frame)
                time.sleep(0.03) # Khớp với tốc độ 30fps phổ biến
            except Exception as e:
                print(f"[Worker Error] {e}")
                time.sleep(0.1)

    def stop(self):
        """Yêu cầu dừng worker, gọi quit() và chờ thread kết thúc bằng wait()."""
        self._running = False
        self.quit()
        self.wait()
