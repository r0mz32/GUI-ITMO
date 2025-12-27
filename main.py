#!/usr/bin/env python3
# PSF Calculator

import sys
import os
import logging
from datetime import datetime

# пути
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
sys.path.insert(0, os.path.dirname(__file__))

WINDOW_TITLE = "PSF Calculator"
WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 800

# логи


def setup_logging():
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    log_filename = os.path.join(
        log_dir, f'psf_app_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info("="*60)
    logger.info("PSF Calculator Application Started")
    logger.info(f"Log file: {log_filename}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info("="*60)

    return logger


logger = setup_logging()

# импорты
try:
    logger.info("Importing PyQt6...")
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPalette, QColor
    logger.info("PyQt6 imported successfully")
except ImportError as e:
    logger.error(f"Failed to import PyQt6: {e}")
    sys.exit(1)

try:
    logger.info("Importing frontend modules...")
    from frontend.main_window import MainWindow
    from frontend.psf_tab import PSFTab
    from frontend.image_tab import ImageTab
    logger.info("Frontend modules imported successfully")
except ImportError as e:
    logger.error(f"Failed to import frontend modules: {e}")
    logger.exception("Full traceback:")
    sys.exit(1)


def setup_application_style(app):
    # темная тема
    app.setStyle("Fusion")
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(
        QPalette.ColorRole.HighlightedText, QColor(35, 35, 35))
    app.setPalette(dark_palette)

    stylesheet = """
    QToolTip {
        color: #ffffff;
        background-color: #2a82da;
        border: 1px solid white;
    }
    QPushButton {
        background-color: #2a82da;
        border: none;
        color: white;
        padding: 5px 15px;
        text-align: center;
        text-decoration: none;
        font-size: 12px;
        margin: 2px;
        border-radius: 3px;
    }
    QPushButton:hover {
        background-color: #1f6bb8;
    }
    QPushButton:pressed {
        background-color: #174d82;
    }
    QPushButton:disabled {
        background-color: #555555;
        color: #888888;
    }
    QGroupBox {
        border: 1px solid #555555;
        border-radius: 5px;
        margin-top: 10px;
        font-weight: bold;
        padding-top: 10px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px 0 5px;
    }
    QTabWidget::pane {
        border: 1px solid #555555;
        border-radius: 3px;
    }
    QTabBar::tab {
        background-color: #353535;
        border: 1px solid #555555;
        padding: 8px 20px;
        margin-right: 2px;
    }
    QTabBar::tab:selected {
        background-color: #2a82da;
    }
    QTabBar::tab:hover:!selected {
        background-color: #454545;
    }
    QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {
        background-color: #252525;
        border: 1px solid #555555;
        border-radius: 3px;
        padding: 3px;
        color: white;
    }
    QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QLineEdit:focus {
        border: 1px solid #2a82da;
    }
    QTableWidget {
        background-color: #252525;
        alternate-background-color: #2a2a2a;
        gridline-color: #555555;
    }
    QHeaderView::section {
        background-color: #353535;
        padding: 5px;
        border: 1px solid #555555;
        font-weight: bold;
    }
    QScrollBar:vertical {
        border: none;
        background: #353535;
        width: 12px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #555555;
        min-height: 20px;
        border-radius: 6px;
    }
    QScrollBar::handle:vertical:hover {
        background: #666666;
    }
    QScrollBar:horizontal {
        border: none;
        background: #353535;
        height: 12px;
        margin: 0px;
    }
    QScrollBar::handle:horizontal {
        background: #555555;
        min-width: 20px;
        border-radius: 6px;
    }
    QScrollBar::handle:horizontal:hover {
        background: #666666;
    }
    QScrollBar::add-line, QScrollBar::sub-line {
        border: none;
        background: none;
    }
    QStatusBar {
        background-color: #2a2a2a;
        color: white;
    }
    QMenuBar {
        background-color: #353535;
        color: white;
    }
    QMenuBar::item:selected {
        background-color: #2a82da;
    }
    QMenu {
        background-color: #353535;
        color: white;
        border: 1px solid #555555;
    }
    QMenu::item:selected {
        background-color: #2a82da;
    }
    """
    app.setStyleSheet(stylesheet)
    logger.info("Application style configured")


def main():
    logger.info("Initializing QApplication...")
    app = QApplication(sys.argv)
    app.setApplicationName(WINDOW_TITLE)
    logger.info(f"QApplication created: {WINDOW_TITLE}")

    setup_application_style(app)

    logger.info("Creating main window...")
    main_window = MainWindow()
    main_window.setWindowTitle(WINDOW_TITLE)
    main_window.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
    logger.info(
        f"Main window created (size: {WINDOW_MIN_WIDTH}x{WINDOW_MIN_HEIGHT})")

    try:
        # PSF Calculator
        logger.info("Creating PSF Calculator tab...")
        psf_tab = PSFTab()
        main_window.add_tab(psf_tab, "PSF Calculator")
        logger.info("PSF Calculator tab added")

        # Image Processing
        logger.info("Creating Image Processing tab...")
        image_tab = ImageTab()
        main_window.add_tab(image_tab, "Image Processing")
        logger.info("Image Processing tab added")

        # связываем
        psf_tab.psf_computed.connect(image_tab.set_psf)
        logger.info("PSF Calculator linked to Image Processing")

        main_window.status_message.emit("Application started successfully")
        logger.info("All tabs initialized successfully")

    except Exception as e:
        logger.error(f"Error creating tabs: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)

    logger.info("Showing main window...")
    main_window.show()
    logger.info("Main window visible")

    logger.info("Starting Qt event loop...")
    logger.info("="*60)
    exit_code = app.exec()

    logger.info(f"Application exited with code: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
