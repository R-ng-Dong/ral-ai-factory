"""Package `communicate` chứa các module giao thức và tiện ích liên quan.

Bao gồm các lớp protocol (TCPClient, MODBUS, MODBUS_RTU) để dùng bởi ứng dụng.
"""

from .TCP_Protocol.TCPClient import TCPClient
from .Modbus_Protocol.MODBUS import MODBUS
from .Modbus_RTU_Protocol.MODBUS_RTU import MODBUS_RTU

__all__ = ["TCPClient", "MODBUS", "MODBUS_RTU"]
