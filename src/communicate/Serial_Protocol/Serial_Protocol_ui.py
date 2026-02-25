# -*- coding: utf-8 -*-

from PySide6.QtCore import (QCoreApplication, QMetaObject, QSize, Qt)
from PySide6.QtWidgets import (QAbstractSpinBox, QComboBox, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, 
    QSpacerItem, QSpinBox, QTabWidget, QTextEdit, QVBoxLayout, QWidget)
from PySide6.QtGui import QFont

class Ui_SerialForm(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(400, 500)
        self.gridLayout = QGridLayout(Form)
        self.gridLayout.setContentsMargins(5, 5, 5, 5)
        
        # --- Settings Group ---
        self.groupBox = QGroupBox(Form)
        self.groupBox.setTitle("Thông số Serial")
        self.groupBox.setFlat(True)
        self.gridLayout_2 = QGridLayout(self.groupBox)
        
        # Port
        self.label = QLabel("Cổng COM")
        self.gridLayout_2.addWidget(self.label, 0, 0)
        self.port_name = QComboBox(self.groupBox)
        self.port_name.setEditable(True)
        self.gridLayout_2.addWidget(self.port_name, 0, 1)
        
        # Baud
        self.label_2 = QLabel("Baud Rate")
        self.gridLayout_2.addWidget(self.label_2, 1, 0)
        self.baud_rate = QComboBox(self.groupBox)
        self.baud_rate.addItems(["9600", "14400", "19200", "38400", "57600", "115200"])
        self.baud_rate.setCurrentText("9600")
        self.gridLayout_2.addWidget(self.baud_rate, 1, 1)
        
        # Status
        self.labelStatus = QLabel("<font color=\"red\">Disconnected</font>")
        font = QFont("Consolas", 8, QFont.Weight.Normal, True)
        self.labelStatus.setFont(font)
        self.gridLayout_2.addWidget(self.labelStatus, 2, 0)
        
        # Auto Connect
        self.label_3 = QLabel("Tự động kết nối")
        self.gridLayout_2.addWidget(self.label_3, 2, 1, Qt.AlignmentFlag.AlignRight)
        self.holderAutoConnect = QFrame(self.groupBox)
        self.gridLayout_2.addWidget(self.holderAutoConnect, 2, 2)
        
        self.gridLayout.addWidget(self.groupBox, 0, 0)
        
        # --- Terminal Tabs ---
        self.tabWidget = QTabWidget(Form)
        
        # RX Tab
        self.tab_rx = QWidget()
        self.layout_rx = QVBoxLayout(self.tab_rx)
        self.term_rx = QTextEdit()
        self.term_rx.setReadOnly(True)
        self.term_rx.setFont(QFont("Courier New", 10))
        self.layout_rx.addWidget(self.term_rx)
        self.bnClearRx = QPushButton("Xoá logs")
        self.layout_rx.addWidget(self.bnClearRx, 0, Qt.AlignmentFlag.AlignRight)
        self.tabWidget.addTab(self.tab_rx, "Nhận")
        
        # TX Tab
        self.tab_tx = QWidget()
        self.layout_tx = QVBoxLayout(self.tab_tx)
        self.term_tx = QTextEdit()
        self.term_tx.setReadOnly(True)
        self.term_tx.setFont(QFont("Courier New", 10))
        self.layout_tx.addWidget(self.term_tx)
        
        self.layout_send = QHBoxLayout()
        self.any_field = QLineEdit()
        self.layout_send.addWidget(self.any_field)
        self.bnSend = QPushButton("Gửi")
        self.layout_send.addWidget(self.bnSend)
        self.layout_tx.addLayout(self.layout_send)
        
        self.bnClearTx = QPushButton("Xoá logs")
        self.layout_tx.addWidget(self.bnClearTx, 0, Qt.AlignmentFlag.AlignRight)
        self.tabWidget.addTab(self.tab_tx, "Gửi")
        
        self.gridLayout.addWidget(self.tabWidget, 1, 0)
        
        self.retranslateUi(Form)
        QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate("Form", u"Serial Raw", None))
