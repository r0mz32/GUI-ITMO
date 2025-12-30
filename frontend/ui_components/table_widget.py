# table widget setup

from PyQt6.QtWidgets import QTableWidget, QHeaderView, QAbstractItemView
from PyQt6.QtCore import Qt


def create_optical_table() -> QTableWidget:
    """creates and configures the optical system table"""

    table = QTableWidget()
    table.setColumnCount(13)
    table.setHorizontalHeaderLabels([
        'λ [μm]', 'NA', 'Mag', 'Defoc [λ]', 'Astig [λ]',
        'Step Obj [c.u.]', 'Step Obj [μm]',
        'Step Im [c.u.]', 'Step Im [μm]',
        'Diam Pup [c.u.]', 'Step Pup [c.u.]',
        'Strehl', 'Status'
    ])

    # column widths
    table.setColumnWidth(0, 65)   # λ
    table.setColumnWidth(1, 50)   # NA
    table.setColumnWidth(2, 50)   # Mag
    table.setColumnWidth(3, 70)   # Defoc
    table.setColumnWidth(4, 70)   # Astig
    table.setColumnWidth(11, 60)  # Strehl
    table.setColumnWidth(12, 90)  # Status

    # stretch the computed columns
    header = table.horizontalHeader()
    for i in range(5, 11):  # Step columns
        header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

    # dark theme for table
    table.setStyleSheet("""
        QTableWidget {
            background-color: #2b2b2b;
            alternate-background-color: #353535;
            color: #ffffff;
            gridline-color: #555555;
        }
        QTableWidget::item {
            padding: 5px;
        }
        QTableWidget::item:selected {
            background-color: #3a5f8f;
        }
        QHeaderView::section {
            background-color: #404040;
            color: #ffffff;
            padding: 5px;
            border: 1px solid #555555;
        }
    """)

    # selection behavior
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    return table
