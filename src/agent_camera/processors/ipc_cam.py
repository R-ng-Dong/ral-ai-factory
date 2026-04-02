"""
IPC Camera Processor.
Kết nối tới service_dvp.py chạy trên Python 3.6 để nhận hình ảnh qua Shared Memory.
"""
from __future__ import annotations

import sys
import os
import time
import subprocess
import threading
from typing import Optional

import numpy as np
import cv2

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox
)

from .base import Processor, ConfigPanel, CamSettings

# Assume running from root, so shared_memory_utils is available
try:
    from shared_memory_utils import SharedMemoryManager
except ImportError:
    # Fallback if path issues, though unlikely if running main.py from root
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
    from shared_memory_utils import SharedMemoryManager

class IpcCameraProcessor(Processor):
    name = "DVPCamera"
    frame_ready = Signal(object)
    
    def __init__(self):
        super().__init__()
        self._panel = IpcConfigPanel()
        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._shm: Optional[SharedMemoryManager] = None
        
        self.triggerSignal.connect(self.trigger_once)
        self._panel.btn_toggle.clicked.connect(self._toggle_connection)
        
    def _toggle_connection(self):
        if self.is_open:
            self.disconnect_camera()
        else:
            self.connect_camera()
        self._panel.update_ui(self.is_open)

    def connect_camera(self) -> bool:
        """Launch the subprocess and connect via Shared Memory."""
        if self.is_open: return True
        
        # 1. Find Python 3.6 Executable
        venv_py = os.path.abspath(os.path.join("venv36", "Scripts", "python.exe"))
        service_script = os.path.abspath("service_dvp.py")
        
        if not os.path.exists(venv_py):
            QMessageBox.critical(self.panel, "Lỗi", f"Không tìm thấy Python 3.6 tại:\n{venv_py}")
            return False
            
        if not os.path.exists(service_script):
            QMessageBox.critical(self.panel, "Lỗi", f"Không tìm thấy script dịch vụ:\n{service_script}")
            return False

        try:
            # 2. Start Subprocess
            print(f"[IPC] Launching: {venv_py} {service_script}")
            cmd = [venv_py, service_script]
            
            # Create Process (Hide window on Windows)
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            self._process = subprocess.Popen(
                cmd,
                cwd=os.getcwd(),
                startupinfo=startupinfo
            )
            
            # Wait a bit for server to start and create SHM
            # We can just start polling in the thread, no need to sleep long here
            time.sleep(1.0)
            
            # 3. Connect Shared Memory
            self._shm = SharedMemoryManager(create=False)
            
            self._running = True
            self._thread = threading.Thread(target=self._recv_loop, daemon=True)
            self._thread.start()
            
            self.is_open = True
            print("[IPC] Connected successfully.")
            return True
            
        except Exception as e:
            print(f"[IPC] Error connecting: {e}")
            self.disconnect_camera()
            QMessageBox.critical(self.panel, "Lỗi kết nối", str(e))
            return False

    def disconnect_camera(self) -> bool:
        self._running = False
        self.is_open = False
        
        # Wait for thread
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

        # Close Shared Memory
        if self._shm:
            self._shm.close()
            self._shm = None
            
        # Kill Process
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=1)
            except:
                self._process.kill()
            self._process = None
            
        return True

    def _recv_loop(self):
        """Poll shared memory for new frames."""
        print("[IPC] Starting Receive Loop (Shared Memory)")
        last_frame_id = -1
        
        while self._running:
            try:
                if not self._shm:
                    time.sleep(0.1)
                    continue

                frame, frame_id = self._shm.read_frame()
                
                if frame is not None and frame_id is not None:
                    # Check if new frame
                    if frame_id != last_frame_id:
                        last_frame_id = frame_id
                        self.frame_ready.emit(frame)
                        # Nghỉ một chút để Camera DVP nạp frame tiếp theo
                        time.sleep(0.01) # 10ms
                    else:
                        # Same frame, sleep to save CPU
                        time.sleep(0.005) # 5ms
                else:
                    # SHM not ready yet or read failed
                    time.sleep(0.033) # Match 30fps
                    
            except Exception as e:
                print(f"[IPC] Loop error: {e}")
                time.sleep(1.0)
        
        print("[IPC] Loop finished")
        
    def configure(self, s: CamSettings) -> None:
        pass 

    def trigger_once(self) -> None:
        pass 

    @property
    def panel(self) -> ConfigPanel:
        return self._panel


class IpcConfigPanel(ConfigPanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("<b>DVP Camera (Service Mode)</b>"))
        layout.addWidget(QLabel("Chạy process riêng trên Python 3.6<br>Giao tiếp: Shared Memory (mmap)"))
        
        self.btn_toggle = QPushButton("Kết nối")
        layout.addWidget(self.btn_toggle)
        layout.addStretch()

    def update_ui(self, connected: bool):
        self.btn_toggle.setText("Ngắt kết nối" if connected else "Kết nối")

    def enum_devices(self): return []
    def dump_settings(self): return CamSettings()
    def load_settings(self, s): pass
