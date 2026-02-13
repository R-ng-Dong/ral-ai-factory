import sys
from PySide6.QtWidgets import QApplication
from src.communicate import MODBUS_RTU

def test_rtu():
    app = QApplication(sys.argv)
    try:
        widget = MODBUS_RTU()
        print("MODBUS_RTU widget created successfully!")
        return True
    except Exception as e:
        print(f"Failed to create MODBUS_RTU widget: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_rtu()
