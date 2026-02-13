# -*- coding: utf-8 -*-

from PySide6.QtCore import (QCoreApplication, QMetaObject, QSize, Qt)
from PySide6.QtWidgets import (QAbstractSpinBox, QCheckBox, QComboBox,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QSizePolicy, QSpinBox, QVBoxLayout,
    QWidget)
from PySide6.QtGui import QFont

class Ui_ModbusRTUForm(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(380, 550) # Adjusted for narrow width
        self.mainLayout = QVBoxLayout(Form)
        self.mainLayout.setContentsMargins(5, 5, 5, 5)
        self.mainLayout.setSpacing(10)
        
        # --- Serial Settings Group ---
        self.groupBox = QGroupBox(Form)
        self.groupBox.setObjectName(u"groupBox")
        self.groupBox.setFlat(True)
        self.gridLayout_2 = QGridLayout(self.groupBox)
        self.gridLayout_2.setSpacing(5)
        
        # Row 0: COM Port
        self.labelPort = QLabel("Cổng COM")
        self.labelPort.setMinimumWidth(100)
        self.gridLayout_2.addWidget(self.labelPort, 0, 0)
        self.port_name = QComboBox(self.groupBox)
        self.port_name.setEditable(True)
        self.gridLayout_2.addWidget(self.port_name, 0, 1)

        # Row 1: Baud Rate
        self.labelBaud = QLabel("Baud Rate")
        self.gridLayout_2.addWidget(self.labelBaud, 1, 0)
        self.baud_rate = QComboBox(self.groupBox)
        self.baud_rate.addItems(["9600", "14400", "19200", "38400", "57600", "115200"])
        self.baud_rate.setCurrentText("9600")
        self.gridLayout_2.addWidget(self.baud_rate, 1, 1)

        # Row 2: Parity
        self.labelParity = QLabel("Parity")
        self.gridLayout_2.addWidget(self.labelParity, 2, 0)
        self.parity = QComboBox(self.groupBox)
        self.parity.addItems(["None", "Even", "Odd", "Space", "Mark"])
        self.gridLayout_2.addWidget(self.parity, 2, 1)

        # Row 3: Stop Bits
        self.labelStopBits = QLabel("Stop Bits")
        self.gridLayout_2.addWidget(self.labelStopBits, 3, 0)
        self.stop_bits = QComboBox(self.groupBox)
        self.stop_bits.addItems(["1", "1.5", "2"])
        self.gridLayout_2.addWidget(self.stop_bits, 3, 1)

        # Row 4: Slave ID
        self.labelSlaveId = QLabel("Slave ID")
        self.gridLayout_2.addWidget(self.labelSlaveId, 4, 0)
        self.slave_id = QSpinBox(self.groupBox)
        self.slave_id.setMinimum(1)
        self.slave_id.setMaximum(255)
        self.slave_id.setValue(1)
        self.gridLayout_2.addWidget(self.slave_id, 4, 1)

        # Row 5: Polling Interval
        self.label_5 = QLabel("Đọc (ms)")
        self.gridLayout_2.addWidget(self.label_5, 5, 0)
        self.polling_interval = QSpinBox(self.groupBox)
        self.polling_interval.setMaximum(65535)
        self.polling_interval.setValue(100)
        self.gridLayout_2.addWidget(self.polling_interval, 5, 1)

        # Row 6: Auto Connect & Status
        self.label_3 = QLabel("Tự động kết nối")
        self.gridLayout_2.addWidget(self.label_3, 6, 0)
        
        self.connectLayout = QHBoxLayout()
        self.holderAutoConnect = QFrame(self.groupBox)
        self.connectLayout.addWidget(self.holderAutoConnect)
        self.connectLayout.addStretch()
        self.gridLayout_2.addLayout(self.connectLayout, 6, 1)

        self.labelStatus = QLabel("<font color=\"red\">Disconnected</font>")
        font = QFont("Consolas", 8, QFont.Weight.Normal, True)
        self.labelStatus.setFont(font)
        self.gridLayout_2.addWidget(self.labelStatus, 7, 0, 1, 2)

        self.mainLayout.addWidget(self.groupBox)

        # --- Separator ---
        self.line = QFrame(Form)
        self.line.setFrameShape(QFrame.Shape.HLine)
        self.line.setFrameShadow(QFrame.Shadow.Sunken)
        self.mainLayout.addWidget(self.line)

        # --- Registers Group ---
        self.groupBox_2 = QGroupBox("Thanh ghi")
        self.mainLayout.addWidget(self.groupBox_2)
        self.gridReg = QGridLayout(self.groupBox_2)
        self.gridReg.setSpacing(5)

        # Read Register Section
        self.gridReg.addWidget(QLabel("<b>Đọc thanh ghi:</b>"), 0, 0, 1, 2)
        
        self.gridReg.addWidget(QLabel("Loại"), 1, 0)
        self.reg_read_type = QComboBox()
        self.gridReg.addWidget(self.reg_read_type, 1, 1)
        
        self.gridReg.addWidget(QLabel("Địa chỉ"), 2, 0)
        self.reg_read_addr = QSpinBox()
        self.reg_read_addr.setMaximum(65535)
        self.gridReg.addWidget(self.reg_read_addr, 2, 1)
        
        self.gridReg.addWidget(QLabel("Giá trị"), 3, 0)
        self.reg_read_value = QLineEdit()
        self.reg_read_value.setReadOnly(True)
        self.gridReg.addWidget(self.reg_read_value, 3, 1)
        
        self.chkAutoClear = QCheckBox("Tự động xoá")
        self.gridReg.addWidget(self.chkAutoClear, 4, 0, 1, 2)

        # Write Register Section
        self.gridReg.addWidget(QLabel("<b>Ghi trạng thái:</b>"), 5, 0, 1, 2)
        
        self.gridReg.addWidget(QLabel("Loại"), 6, 0)
        self.reg_wr_state_type = QComboBox()
        self.gridReg.addWidget(self.reg_wr_state_type, 6, 1)
        
        self.gridReg.addWidget(QLabel("Địa chỉ"), 7, 0)
        self.reg_wr_state_addr = QSpinBox()
        self.reg_wr_state_addr.setMaximum(65535)
        self.gridReg.addWidget(self.reg_wr_state_addr, 7, 1)

        self.mainLayout.addStretch()

        self.retranslateUi(Form)
        QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate("Form", u"Modbus RTU", None))
        self.groupBox.setTitle(QCoreApplication.translate("Form", u"Thông số RS485", None))
