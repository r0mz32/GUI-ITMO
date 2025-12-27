# главное окно

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QMenuBar,
    QMenu, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction


class MainWindow(QMainWindow):

    status_message = pyqtSignal(str)
    computation_started = pyqtSignal()
    computation_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PSF Calculator & Optical System Analyzer")
        self.setMinimumSize(1200, 800)

        # вкладки
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # статус-бар
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # сигналы
        self.status_message.connect(self.status_bar.showMessage)

        # меню
        self._create_menu()

        # флаг вычислений
        self.is_computing = False
        self.computation_started.connect(self._on_computation_started)
        self.computation_finished.connect(self._on_computation_finished)

    def _create_menu(self):
        menubar = self.menuBar()

        # File
        file_menu = menubar.addMenu("&File")

        save_action = QAction("&Save Session...", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_session)
        file_menu.addAction(save_action)

        load_action = QAction("&Load Session...", self)
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(self._load_session)
        file_menu.addAction(load_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View
        view_menu = menubar.addMenu("&View")

        reset_action = QAction("&Reset Layout", self)
        reset_action.triggered.connect(self._reset_layout)
        view_menu.addAction(reset_action)

        # Help
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def add_tab(self, widget, title):
        self.tabs.addTab(widget, title)

    def _save_session(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Session",
            "",
            "Session Files (*.json);;All Files (*)"
        )
        if filename:
            # TODO: сохранение сессии
            self.status_message.emit(f"Session saving not implemented yet")

    def _load_session(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load Session",
            "",
            "Session Files (*.json);;All Files (*)"
        )
        if filename:
            # TODO: загрузка сессии
            self.status_message.emit(f"Session loading not implemented yet")

    def _reset_layout(self):
        self.status_message.emit("Layout reset")

    def _show_about(self):
        QMessageBox.about(
            self,
            "About PSF Calculator",
            "<h2>PSF Calculator & Optical System Analyzer</h2>"
            "<p>Какая-то прога для расчета PSF и обработки изображений.</p>"
            "<p>Сделана на Python + PyQt6 + NumPy + SciPy.</p>"
        )

    def _on_computation_started(self):
        self.is_computing = True
        self.status_message.emit("Computing...")

    def _on_computation_finished(self):
        self.is_computing = False
        self.status_message.emit("Ready")
