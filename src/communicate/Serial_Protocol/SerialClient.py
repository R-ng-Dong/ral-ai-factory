import time
from datetime import datetime
from PySide6.QtCore import QByteArray, Signal, Slot, QIODevice
from PySide6.QtWidgets import QApplication, QWidget, QMessageBox
from PySide6.QtSerialPort import QSerialPort, QSerialPortInfo

from .Serial_Protocol_ui import Ui_SerialForm
from ..base_protocol import BaseProtocol

class SerialClient(Ui_SerialForm, BaseProtocol):
    def __init__(self, parent=None, port_name=None, baud_rate=9600, auto=False):
        super().__init__(parent)
        self.setupUi(self)
        
        self.port = QSerialPort(self)
        self.started = False
        
        self.__init_ports()
        
        if port_name: self.port_name.setCurrentText(port_name)
        self.baud_rate.setCurrentText(str(baud_rate))
        
        self.gridLayout_2.replaceWidget(self.holderAutoConnect, self.toggleAutoConnect)
        self.holderAutoConnect.deleteLater()
        
        # Connections
        self.bnSend.clicked.connect(self.send)
        self.bnClearRx.clicked.connect(self.term_rx.clear)
        self.bnClearTx.clicked.connect(self.term_tx.clear)
        
        self.port.readyRead.connect(self.on_port_rx)
        self.port.errorOccurred.connect(self.on_error)
        
        self.toggleAutoConnect.setChecked(auto)

    def __init_ports(self):
        ports = QSerialPortInfo.availablePorts()
        for p in ports:
            self.port_name.addItem(p.portName())

    def start(self):
        if not self.started:
            self.port.setPortName(self.port_name.currentText())
            self.port.setBaudRate(int(self.baud_rate.currentText()))
            self.port.setDataBits(QSerialPort.DataBits.Data8)
            self.port.setParity(QSerialPort.Parity.NoParity)
            self.port.setStopBits(QSerialPort.StopBits.OneStop)
            self.port.setFlowControl(QSerialPort.FlowControl.NoFlowControl)
            
            if self.port.open(QIODevice.OpenModeFlag.ReadWrite):
                self.started = True
                self.labelStatus.setText('<font color="#4CAF50">Connected</font>')
                self.curr_connect_notify.emit(2)
            else:
                self.labelStatus.setText('<font color="red">Open Failed</font>')
                self.toggleAutoConnect.setChecked(False)

    def stop(self):
        if self.started:
            self.started = False
            self.port.close()
            self.labelStatus.setText('<font color="#C62828">Disconnected</font>')
            self.curr_connect_notify.emit(0)

    @Slot()
    def send(self):
        if self.started:
            data = self.any_field.text()
            if data:
                self.port.write(data.encode('utf-8'))
                self._log_tx(data)

    def send_data(self, tx_data: str):
        if self.started:
            self.port.write(str(tx_data).encode('utf-8'))

    def on_port_rx(self):
        data = self.port.readAll().data().decode('utf-8', errors='ignore')
        if data:
            self.rx_data.emit(data)
            self._log_rx(data)

    def on_error(self, error):
        if error != QSerialPort.SerialPortError.NoError:
            print(f"[Serial Error] {error}")
            if self.started:
                self.stop()

    def _log_rx(self, data):
        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.term_rx.insertHtml(f'<span style="color:black">[{now}] </span>'
                                f'<span style="color:green">{data}</span><br>')
        self.term_rx.ensureCursorVisible()

    def _log_tx(self, data):
        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.term_tx.insertHtml(f'<span style="color:black">[{now}] </span>'
                                f'<span style="color:blue">{data}</span><br>')
        self.term_tx.ensureCursorVisible()

    def restart(self):
        self.stop()
        if self.toggleAutoConnect.isChecked():
            self.start()

    @property
    def settings(self):
        return {
            "port_name": self.port_name.currentText(),
            "baud_rate": int(self.baud_rate.currentText()),
            "auto": self.toggleAutoConnect.isChecked()
        }
