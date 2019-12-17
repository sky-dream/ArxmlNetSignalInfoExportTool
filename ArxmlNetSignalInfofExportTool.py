#!/usr/bin/env python
# -*- coding: utf-8 -*-
# D:\000_Programs\Anaconda3\Scripts\pyinstaller.exe -F ArxmlNetSignalInfofExportTool.py -w -i Panda_001.ico
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QTableView, QApplication, QAction, QMessageBox, QMainWindow, QWidget, QDialog
from PyQt5.QtWidgets import QFileDialog, QTableWidgetItem, QHeaderView
from PyQt_NetSignalInfoExportTool import Ui_NetSignalInfoExportTool
import sys
#import xlrd
#import xlwt
#import os
import logging
import canmatrix.log
import Function_NetSignalInfofExport

__Author__ = "By: Xueming"
__Copyright__ = "Copyright (c) 2019 Xueming."
__Version__ = "Version 1.0"


logger = canmatrix.log.setup_logger()
canmatrix.log.set_log_level(logger, 0)


class MainWindow(QMainWindow, Ui_NetSignalInfoExportTool):
    """
    Class documentation goes here.
    """

    def __init__(self, parent=None):
        """
        Constructor

        @param parent reference to the parent widget
        @type QWidget
        """
        super(MainWindow, self).__init__(parent)
        self.ui = Ui_NetSignalInfoExportTool()
        self.setupUi(self)
        self.ArxmlInputFilePath = ""
        self.SignalInfoTableFolderPath = ""

    @pyqtSlot()
    def on_pushButton_DatabaseFileInputSelect_clicked(self):
        """
        Slot documentation goes here.
        """
        ArxmlInputFile, supported_fileKinds = QFileDialog.getOpenFileName(
            self, u'open the file', u'./')
        self.lineEdit_DatabaseFileInput.setText(ArxmlInputFile)
        filePathForWinOS = ArxmlInputFile.replace('/', '\\')
        if str(ArxmlInputFile)[-6:] == '.arxml':
            self.ArxmlInputFilePath = filePathForWinOS
            pass
        else:
            l_MessageBox = QMessageBox.information(
                self, u'Tips', 'The file opened is not an arxml file,pls open an arxml file.')
            pass

    @pyqtSlot()
    def on_pushButton_OutputFolderSelect_clicked(self):
        """
        Slot documentation goes here.
        """
        pass
        SignalInfoTableFolder = QFileDialog.getExistingDirectory(
            self, u'select the output file folder', u'./')
        self.SignalInfoTableFolderPath = SignalInfoTableFolder
        self.lineEdit_OutputFolder.setText(SignalInfoTableFolder)
        # l_MessageBox = QMessageBox.information(
        # self, u'Tips', 'Output Folder is Selected.')

    @pyqtSlot()
    def on_pushButton_GenerateSignalInfoTable_clicked(self):
        """
        Slot documentation goes here.
        """
        cluster, ns = Function_NetSignalInfofExport.arxml_file_load(
            self.ArxmlInputFilePath)
        Function_NetSignalInfofExport.dump_signal_info(
            cluster, self.ArxmlInputFilePath.split("\\")[-1], self.SignalInfoTableFolderPath)
        logger.info('pushButton_GenerateSignalInfoTable.')
        QMessageBox.information(
            self, u'Tips', 'Net Signal Info Table successfully generated based on arxml database.')


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    app.setApplicationName("Net Signal Info Export Tool")
    window = MainWindow()
    window.setWindowTitle('Net Signal Info Export Tool')
    window.show()
    sys.exit(app.exec_())
