from typing import TypedDict
import time
from PySide6.QtCore import Slot, QTimer, Qt
from PySide6.QtWidgets import QApplication, QWidget, QMessageBox
from PySide6.QtSerialBus import QModbusRtuSerialClient, QModbusDataUnit, QModbusReply, QModbusDevice
from PySide6.QtSerialPort import QSerialPort

from .MODBUS_RTU_ui import Ui_ModbusRTUForm
from ..base_protocol import BaseProtocol
from ..Modbus_Protocol.handler import state_changed, sock_error

class _Reg(TypedDict):
    reg_type: str
    reg_addr: int

class MODBUS_RTU(Ui_ModbusRTUForm, BaseProtocol):
    def __init__(self, parent=None, port_name=None, baud_rate=9600, parity="None", 
                 stop_bits="1", slave_id=1, polling_interval=100, auto=False,
                 auto_clear=False,
                 read_register = _Reg(reg_type="HoldingRegisters", reg_addr=0),
                 write_reg_state= _Reg(reg_type="HoldingRegisters", reg_addr=0), 
            ):
        super().__init__(parent)

        self.setupUi(self)
        self.__init_reg()
        self.__init_serial_ports()

        self.modbus_client = QModbusRtuSerialClient(self)

        self.__retry = 0
        self.started = False
        
        # Set initial values
        if port_name: self.port_name.setCurrentText(port_name)
        self.baud_rate.setCurrentText(str(baud_rate))
        self.parity.setCurrentText(parity)
        self.stop_bits.setCurrentText(str(stop_bits))
        self.slave_id.setValue(int(slave_id))
        self.polling_interval.setValue(int(polling_interval))
        self.chkAutoClear.setChecked(auto_clear)
        self.reg_read = read_register
        self.reg_wr_state = write_reg_state

        # Toggle button replacement
        self.gridLayout_2.replaceWidget(self.holderAutoConnect, self.toggleAutoConnect)
        self.holderAutoConnect.deleteLater()

        # Timer for polling
        self.read_timer = QTimer(self)
        self.read_timer.setInterval(int(polling_interval))
        self.read_timer.timeout.connect(self.read_input)

        # Signals
        self.polling_interval.editingFinished.connect(
            lambda: self.read_timer.setInterval(self.polling_interval.value())
        )
        self.modbus_client.stateChanged.connect(self.state_changed)
        self.modbus_client.errorOccurred.connect(self.sock_error)
        
        self.toggleAutoConnect.setChecked(auto)

    def __init_reg(self):
        register_types = ["DiscreteInputs", "Coils", "InputRegisters", "HoldingRegisters"]
        self.reg_read_type.addItems(register_types)
        self.reg_wr_state_type.addItems(register_types)

    def __init_serial_ports(self):
        from PySide6.QtSerialPort import QSerialPortInfo
        ports = QSerialPortInfo.availablePorts()
        for port in ports:
            self.port_name.addItem(port.portName())

    @property
    def reg_read(self) -> _Reg:
        return _Reg(
            reg_type=self.reg_read_type.currentText(),
            reg_addr=self.reg_read_addr.value(),
        )

    @reg_read.setter
    def reg_read(self, value: _Reg):
        self.reg_read_type.setCurrentText(value['reg_type'])
        self.reg_read_addr.setValue(value['reg_addr'])

    @property
    def reg_wr_state(self) -> _Reg:
        return _Reg(
            reg_type=self.reg_wr_state_type.currentText(),
            reg_addr=self.reg_wr_state_addr.value(),
        )

    @reg_wr_state.setter
    def reg_wr_state(self, value: _Reg):
        self.reg_wr_state_type.setCurrentText(value['reg_type'])
        self.reg_wr_state_addr.setValue(value['reg_addr'])

    @property
    def settings(self):
        return {
            "port_name": self.port_name.currentText(),
            "baud_rate": int(self.baud_rate.currentText()),
            "parity": self.parity.currentText(),
            "stop_bits": self.stop_bits.currentText(),
            "slave_id": self.slave_id.value(),
            "polling_interval": self.polling_interval.value(),
            "auto": self.toggleAutoConnect.isChecked(),
            "auto_clear": self.chkAutoClear.isChecked(),
            "read_register": self.reg_read,
            "write_reg_state": self.reg_wr_state
        }

    def start(self):
        if not self.started:
            self.started = True
            
            # COM Port
            self.modbus_client.setConnectionParameter(
                QModbusDevice.ConnectionParameter.SerialPortNameParameter, 
                self.port_name.currentText()
            )
            
            # Baud Rate
            self.modbus_client.setConnectionParameter(
                QModbusDevice.ConnectionParameter.SerialBaudRateParameter, 
                int(self.baud_rate.currentText())
            )
            
            # Parity
            parity_map = {
                "None": QSerialPort.Parity.NoParity,
                "Even": QSerialPort.Parity.EvenParity,
                "Odd": QSerialPort.Parity.OddParity,
                "Space": QSerialPort.Parity.SpaceParity,
                "Mark": QSerialPort.Parity.MarkParity
            }
            self.modbus_client.setConnectionParameter(
                QModbusDevice.ConnectionParameter.SerialParityParameter, 
                parity_map.get(self.parity.currentText(), QSerialPort.Parity.NoParity)
            )
            
            # Stop Bits
            stop_map = {
                "1": QSerialPort.StopBits.OneStop,
                "1.5": QSerialPort.StopBits.OneAndHalfStop,
                "2": QSerialPort.StopBits.TwoStop
            }
            self.modbus_client.setConnectionParameter(
                QModbusDevice.ConnectionParameter.SerialStopBitsParameter, 
                stop_map.get(self.stop_bits.currentText(), QSerialPort.StopBits.OneStop)
            )
            
            # Data Bits (Default 8)
            self.modbus_client.setConnectionParameter(
                QModbusDevice.ConnectionParameter.SerialDataBitsParameter, 
                QSerialPort.DataBits.Data8
            )

            self.modbus_client.disconnectDevice()
            if not self.modbus_client.connectDevice():
                self.started = False
                self.labelStatus.setText('<font color="red">Connect Failed</font>')

    def stop(self):
        if self.started:
            self.started = False
            self.read_timer.stop()
            self.modbus_client.disconnectDevice()

    @Slot()
    def state_changed(self, state) -> None:
        socket_state = state_changed(state)
        if socket_state == 'Connected':
            self.curr_connect_notify.emit(2)
            self.labelStatus.setText(f'<font color="#4CAF50">{socket_state}</font>')
            self.read_timer.start()
        elif socket_state == 'Disconnected':
            self.started = False
            self.read_timer.stop()
            self.labelStatus.setText(f'<font color="#C62828">{socket_state}</font>')
            self.curr_connect_notify.emit(0)
            if self.toggleAutoConnect.isChecked():
                self.start()
        else:
            self.labelStatus.setText(f'<font color="#29B6F6">{socket_state}</font>')

    @Slot()
    def sock_error(self, error) -> None:
        error_message = sock_error(error)
        if error != QModbusDevice.Error.NoError:
             print(f"[Modbus RTU Error] {error_message}")
             # Optional: handle auto-retry logic here

    def read_input(self):
        if self.started and self.modbus_client.state() == QModbusDevice.State.ConnectedState:
            read_address = self.reg_read['reg_addr']
            read_type = QModbusDataUnit.RegisterType.__members__[self.reg_read['reg_type']]
            data_unit = QModbusDataUnit(read_type, read_address, 1)
            reply = self.modbus_client.sendReadRequest(data_unit, self.slave_id.value())
            if reply:
                if not reply.isFinished():
                    reply.finished.connect(self.onReadReady)
                else:
                    reply.deleteLater()

    def onReadReady(self) -> None:
        reply = self.sender()
        if not isinstance(reply, QModbusReply):
            return

        try:
            if reply.error() == QModbusDevice.Error.NoError:
                unit = reply.result()
                if unit.isValid() and unit.valueCount() > 0:
                    val = unit.value(0)
                    new_value = str(val)
                    if self.reg_read_value.text() != new_value:
                        self.reg_read_value.setText(new_value)
                    
                    if new_value != "0" and self.chkAutoClear.isChecked():
                        self.send_to(self.reg_read, 0)
                    
                    self.rx_data.emit(new_value)
        finally:
            reply.deleteLater()

    def send_to(self, reg: _Reg, tx_data: int | str) -> None:
        if self.started and self.modbus_client.state() == QModbusDevice.State.ConnectedState:
            write_addr = reg['reg_addr']
            write_type = QModbusDataUnit.RegisterType.__members__[reg['reg_type']]
            write_unit = QModbusDataUnit(write_type, write_addr, 1)
            write_unit.setValue(0, int(tx_data))
            self.modbus_client.sendWriteRequest(write_unit, self.slave_id.value())

    def send_data(self, tx_data: str) -> None:
        # Simple string to int conversion for single values
        if tx_data.isdigit():
            self.send_to(self.reg_wr_state, int(tx_data))

    def restart(self):
        self.stop()
        if self.toggleAutoConnect.isChecked():
            self.start()
