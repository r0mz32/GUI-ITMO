from psf_wrapper import PSFCalculator, compute_psf
import sys
import os
import numpy as np
import time
import logging
import json
import random
from typing import Optional, List, Tuple
from dataclasses import dataclass, asdict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGroupBox, QLabel, QPushButton, QRadioButton,
    QButtonGroup, QProgressDialog, QComboBox, QDoubleSpinBox,
    QFormLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMenu, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QBrush


logger = logging.getLogger(__name__)


sys.path.insert(0, os.path.join(
    os.path.dirname(__file__), '..', '..', 'backend'))


# data class for one row in the optical system table
@dataclass
class OpticalSystemRow:
    # input params
    wavelength: float = 0.555
    back_aperture: float = 1.2
    magnification: float = 100.0
    defocus: float = 0.0
    astigmatism: float = 0.0
    sample_size: int = 512

    # computed params
    step_obj_can: float = 0.0
    step_obj_microns: float = 0.0
    step_im_can: float = 0.0
    step_im_microns: float = 0.0
    diam_pupil: float = 7.5
    step_pupil: float = 0.0

    # results
    psf_data: Optional[np.ndarray] = None
    strehl_ratio: float = 0.0
    status: str = "not_computed"
    error_message: str = ""
    compute_time: float = 0.0

    def get_params(self) -> dict:
        """returns params for PSFCalculator"""
        return {
            'size': self.sample_size,
            'wavelength': self.wavelength,
            'back_aperture': self.back_aperture,
            'magnification': self.magnification,
            'defocus': self.defocus,
            'astigmatism': self.astigmatism,
            'diam_pupil': self.diam_pupil
        }

    def to_dict(self) -> dict:
        """save to json (without psf_data)"""
        return {
            'wavelength': self.wavelength,
            'back_aperture': self.back_aperture,
            'magnification': self.magnification,
            'defocus': self.defocus,
            'astigmatism': self.astigmatism,
            'sample_size': self.sample_size
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'OpticalSystemRow':
        """load from json"""
        return cls(
            wavelength=data.get('wavelength', 0.555),
            back_aperture=data.get('back_aperture', 1.2),
            magnification=data.get('magnification', 100.0),
            defocus=data.get('defocus', 0.0),
            astigmatism=data.get('astigmatism', 0.0),
            sample_size=data.get('sample_size', 512)
        )


class PSFComputeThread(QThread):

    result_ready = pyqtSignal(np.ndarray, float, dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, params):
        super().__init__()
        self.params = params

    def run(self):
        try:
            start_time = time.time()

            logger.info(f"Starting PSF computation with params: {self.params}")

            calc = PSFCalculator()
            psf_data = calc.compute(**self.params)

            elapsed_time = time.time() - start_time

            step_microns = calc.get_step_microns()

            logger.info(
                f"PSF computation completed: {psf_data.shape}, {elapsed_time:.3f}s")

            self.result_ready.emit(psf_data, elapsed_time, {
                                   'step_microns': step_microns})
        except Exception as e:
            logger.error(f"PSF computation failed: {e}", exc_info=True)
            self.error_occurred.emit(str(e))


class PSFTab(QWidget):

    psf_computed = pyqtSignal(np.ndarray)

    def __init__(self, parent=None):
        super().__init__(parent)
        logger.info("Initializing Optical System Analyzer tab...")

        self.psf_calculator = PSFCalculator()
        logger.info("PSF Calculator backend initialized")

        # table data
        self.table_rows: List[OpticalSystemRow] = []
        self.selected_row_idx: int = -1

        # current displayed PSF
        self.current_psf = None
        self.current_params = None
        self.current_step_microns = None
        self.current_compute_time = None

        # system PSF (convolution of all rows)
        self.system_psf = None
        self.system_psf_valid = False
        self.system_compute_time = 0.0

        # computation state
        self.compute_thread = None
        self.computing_rows: List[int] = []
        self.computation_cancelled = False
        self.compute_system_after = False  # flag to compute system PSF after all rows

        self.current_units = 'microns'

        # column indices for table (without # column)
        self.COL_LAMBDA = 0
        self.COL_NA = 1
        self.COL_MAG = 2
        self.COL_DEFOC = 3
        self.COL_ASTIG = 4
        self.COL_STEP_OBJ_CAN = 5
        self.COL_STEP_OBJ_UM = 6
        self.COL_STEP_IM_CAN = 7
        self.COL_STEP_IM_UM = 8
        self.COL_DIAM_PUP = 9
        self.COL_STEP_PUP = 10
        self.COL_STREHL = 11
        self.COL_STATUS = 12

        self._create_ui()
        logger.info("Optical System Analyzer tab UI created")

        # init with 3 default rows and auto-compute first
        self._initialize_default_rows()

    def _create_ui(self):
        main_layout = QVBoxLayout()

        # row 1: plots (largest)
        plots_widget = self._create_visualization_panel()
        main_layout.addWidget(plots_widget, stretch=5)

        # row 2: compact control bar
        control_bar = self._create_control_bar()
        main_layout.addWidget(control_bar, stretch=0)

        # row 3: table buttons
        button_toolbar = self._create_button_toolbar()
        main_layout.addWidget(button_toolbar, stretch=0)

        # row 4: table
        table_widget = self._create_table_widget()
        main_layout.addWidget(table_widget, stretch=3)

        self.setLayout(main_layout)

    def _create_visualization_panel(self):
        """row 1: two plots side by side"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        from frontend.widgets.plot_widget import PlotWidget
        self.plot_cross_sections = PlotWidget(toolbar=True)
        layout.addWidget(self.plot_cross_sections, stretch=1)

        self.plot_2d_psf = PlotWidget(toolbar=True)
        layout.addWidget(self.plot_2d_psf, stretch=1)

        widget.setLayout(layout)
        return widget

    def _create_control_bar(self):
        """row 2: full-width bar: units (1/4) | info (1/4) | source param (2/4)"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(5, 5, 5, 5)

        # 1/4: units group
        units_group = QGroupBox("Units")
        units_layout = QHBoxLayout()

        self.units_group = QButtonGroup()
        self.radio_microns = QRadioButton("μm")
        self.radio_canonical = QRadioButton("Can")
        self.radio_pixels = QRadioButton("Pix")

        self.radio_microns.setChecked(True)

        self.units_group.addButton(self.radio_microns, 0)
        self.units_group.addButton(self.radio_canonical, 1)
        self.units_group.addButton(self.radio_pixels, 2)

        self.radio_microns.toggled.connect(self._on_units_changed)
        self.radio_canonical.toggled.connect(self._on_units_changed)
        self.radio_pixels.toggled.connect(self._on_units_changed)

        units_layout.addWidget(self.radio_microns)
        units_layout.addWidget(self.radio_canonical)
        units_layout.addWidget(self.radio_pixels)
        units_group.setLayout(units_layout)
        layout.addWidget(units_group, stretch=1)

        # 1/4: information group
        info_group = QGroupBox("Information")
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        # combine max and time in one line
        self.info_label = QLabel("Max: N/A | Time: N/A")
        self.info_label.setWordWrap(True)

        info_layout.addWidget(self.info_label)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group, stretch=1)

        # 2/4: source parameter group (param | units | value)
        source_group = QGroupBox("Source Parameter")
        source_layout = QHBoxLayout()

        # parameter selection
        source_layout.addWidget(QLabel("Param:"))
        self.param_choice_combo = QComboBox()
        self.param_choice_combo.addItems([
            'Diam pupil',
            'Step pupil',
            'Step object',
            'Step image'
        ])
        self.param_choice_combo.currentTextChanged.connect(
            self._on_param_choice_changed)
        source_layout.addWidget(self.param_choice_combo, stretch=1)

        # units selection
        source_layout.addWidget(QLabel("Units:"))
        self.source_param_units_combo = QComboBox()
        self.source_param_units_combo.addItems(['c.u.', 'μm'])
        self.source_param_units_combo.currentTextChanged.connect(
            self._on_source_param_units_changed)
        source_layout.addWidget(self.source_param_units_combo)

        # value input
        source_layout.addWidget(QLabel("Value:"))
        self.source_param_spin = QDoubleSpinBox()
        self.source_param_spin.setRange(0.001, 1000.0)
        self.source_param_spin.setValue(7.5)
        self.source_param_spin.setDecimals(6)
        self.source_param_spin.setSingleStep(0.1)
        self.source_param_spin.setMinimumWidth(100)
        self.source_param_spin.valueChanged.connect(
            self._on_source_param_value_changed)
        source_layout.addWidget(self.source_param_spin, stretch=1)

        source_group.setLayout(source_layout)
        layout.addWidget(source_group, stretch=2)

        widget.setLayout(layout)
        return widget

    def _create_button_toolbar(self):
        """row 3: table control buttons"""
        widget = QWidget()
        main_layout = QHBoxLayout()
        main_layout.setSpacing(5)

        # group 1: computation (centered)
        group1_layout = QHBoxLayout()
        group1_layout.addStretch()
        btn_compute_all = QPushButton("Compute All")
        btn_compute_all.clicked.connect(self._on_compute_all_clicked)
        group1_layout.addWidget(btn_compute_all)
        btn_compute_selected = QPushButton("Compute Selected")
        btn_compute_selected.clicked.connect(self._on_compute_selected_clicked)
        group1_layout.addWidget(btn_compute_selected)
        group1_layout.addStretch()

        # group 2: system and clear (centered)
        group2_layout = QHBoxLayout()
        group2_layout.addStretch()
        btn_compute_system = QPushButton("Compute System PSF")
        btn_compute_system.clicked.connect(self._on_compute_system_clicked)
        group2_layout.addWidget(btn_compute_system)
        btn_clear = QPushButton("Clear All")
        btn_clear.clicked.connect(self._on_clear_table_clicked)
        group2_layout.addWidget(btn_clear)
        group2_layout.addStretch()

        # group 3: file operations (centered)
        group3_layout = QHBoxLayout()
        group3_layout.addStretch()
        btn_save = QPushButton("Save Config")
        btn_save.clicked.connect(self._on_save_config_clicked)
        group3_layout.addWidget(btn_save)
        btn_load = QPushButton("Load Config")
        btn_load.clicked.connect(self._on_load_config_clicked)
        group3_layout.addWidget(btn_load)
        btn_export = QPushButton("Export Plots")
        btn_export.clicked.connect(self._on_export_plots_clicked)
        group3_layout.addWidget(btn_export)
        group3_layout.addStretch()

        # add groups to main layout with equal spacing
        main_layout.addLayout(group1_layout, stretch=1)

        separator1 = QLabel("|")
        separator1.setStyleSheet("color: #555; font-size: 20px;")
        main_layout.addWidget(separator1)

        main_layout.addLayout(group2_layout, stretch=1)

        separator2 = QLabel("|")
        separator2.setStyleSheet("color: #555; font-size: 20px;")
        main_layout.addWidget(separator2)

        main_layout.addLayout(group3_layout, stretch=1)

        widget.setLayout(main_layout)
        return widget

    def _create_table_widget(self):
        """row 4: table with all parameters"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(13)
        self.table.setHorizontalHeaderLabels([
            'λ [μm]', 'NA', 'Mag', 'Defoc [λ]', 'Astig [λ]',
            'Step Obj [c.u.]', 'Step Obj [μm]',
            'Step Im [c.u.]', 'Step Im [μm]',
            'Diam Pup [c.u.]', 'Step Pup [c.u.]',
            'Strehl', 'Status'
        ])

        # column widths
        self.table.setColumnWidth(0, 65)
        self.table.setColumnWidth(1, 50)
        self.table.setColumnWidth(2, 50)
        self.table.setColumnWidth(3, 70)
        self.table.setColumnWidth(4, 70)
        self.table.setColumnWidth(11, 60)
        self.table.setColumnWidth(12, 90)

        header = self.table.horizontalHeader()
        for i in range(5, 11):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        # dark theme for table
        self.table.setStyleSheet("""
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

        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)

        self.table.itemSelectionChanged.connect(
            self._on_table_selection_changed)
        self.table.itemChanged.connect(self._on_table_item_changed)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(
            self._on_table_context_menu)

        layout.addWidget(self.table)
        widget.setLayout(layout)
        return widget

    # ===== VALIDATION =====

    def _validate_row(self, row: OpticalSystemRow) -> Tuple[bool, str]:
        """validate row parameters"""

        if row.wavelength <= 0 or row.wavelength > 5.0:
            return False, "Wavelength must be in range (0, 5.0] μm"

        if row.back_aperture <= 0 or row.back_aperture > 5.0:
            return False, "Back aperture must be in range (0, 5.0]"

        if row.magnification <= 0 or row.magnification > 1000.0:
            return False, "Magnification must be in range (0, 1000.0]"

        if row.diam_pupil <= 0:
            return False, "Diameter pupil must be positive"

        if row.step_pupil <= 0:
            return False, "Step pupil must be positive"

        if row.sample_size not in [128, 256, 512, 1024, 2048]:
            return False, "Invalid sample size"

        return True, ""

    # ===== TABLE MANAGEMENT =====

    def _get_source_param_column(self) -> int:
        """get column index of current source parameter"""
        choice = self.param_choice_combo.currentText()
        units = self.source_param_units_combo.currentText()

        if choice == 'Diam pupil':
            return self.COL_DIAM_PUP  # always c.u.
        elif choice == 'Step pupil':
            return self.COL_STEP_PUP  # always c.u.
        elif choice == 'Step object':
            return self.COL_STEP_OBJ_CAN if units == 'c.u.' else self.COL_STEP_OBJ_UM
        elif choice == 'Step image':
            return self.COL_STEP_IM_CAN if units == 'c.u.' else self.COL_STEP_IM_UM
        return -1

    def _add_row(self, row: OpticalSystemRow) -> int:
        """add row to table and data"""
        idx = len(self.table_rows)
        self.table_rows.append(row)

        self._recalculate_row_params(idx)
        self._insert_table_row(idx)

        # invalidate system PSF when rows change
        self.system_psf_valid = False

        return idx

    def _insert_table_row(self, idx: int):
        """insert row into QTableWidget"""
        row_data = self.table_rows[idx]

        self.table.blockSignals(True)
        self.table.insertRow(idx)

        source_col = self._get_source_param_column()

        # editable: basic params
        self.table.setItem(idx, self.COL_LAMBDA, QTableWidgetItem(
            f"{row_data.wavelength:.3f}"))
        self.table.setItem(idx, self.COL_NA, QTableWidgetItem(
            f"{row_data.back_aperture:.2f}"))
        self.table.setItem(idx, self.COL_MAG, QTableWidgetItem(
            f"{row_data.magnification:.1f}"))
        self.table.setItem(idx, self.COL_DEFOC,
                           QTableWidgetItem(f"{row_data.defocus:.2f}"))
        self.table.setItem(idx, self.COL_ASTIG, QTableWidgetItem(
            f"{row_data.astigmatism:.2f}"))

        # computed columns - all read-only and gray
        for col in range(self.COL_STEP_OBJ_CAN, self.COL_STEP_PUP + 1):
            item = QTableWidgetItem("")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            # highlight source parameter column
            if col == source_col:
                item.setBackground(QBrush(QColor(100, 150, 200)))  # blue
            else:
                item.setBackground(QBrush(QColor(80, 80, 80)))  # dark gray

            self.table.setItem(idx, col, item)

        # strehl (read-only)
        item = QTableWidgetItem("—")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(idx, self.COL_STREHL, item)

        # status (read-only)
        item = QTableWidgetItem(row_data.status)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(idx, self.COL_STATUS, item)

        self._update_table_row(idx)
        self.table.blockSignals(False)

    def _update_table_row(self, idx: int):
        """update table display from row data"""
        if idx < 0 or idx >= len(self.table_rows):
            return

        row_data = self.table_rows[idx]

        self.table.blockSignals(True)

        # update computed params
        self.table.item(idx, self.COL_STEP_OBJ_CAN).setText(
            f"{row_data.step_obj_can:.6f}")
        self.table.item(idx, self.COL_STEP_OBJ_UM).setText(
            f"{row_data.step_obj_microns:.6f}")
        self.table.item(idx, self.COL_STEP_IM_CAN).setText(
            f"{row_data.step_im_can:.6f}")
        self.table.item(idx, self.COL_STEP_IM_UM).setText(
            f"{row_data.step_im_microns:.6f}")
        self.table.item(idx, self.COL_DIAM_PUP).setText(
            f"{row_data.diam_pupil:.3f}")
        self.table.item(idx, self.COL_STEP_PUP).setText(
            f"{row_data.step_pupil:.6f}")

        # update strehl
        if row_data.status == "complete":
            self.table.item(idx, self.COL_STREHL).setText(
                f"{row_data.strehl_ratio:.4f}")
        else:
            self.table.item(idx, self.COL_STREHL).setText("—")

        # update status
        self.table.item(idx, self.COL_STATUS).setText(row_data.status)

        # color code by status (dark theme colors)
        if row_data.status == "not_computed":
            color = QColor(60, 60, 60)  # dark gray
        elif row_data.status == "computing":
            color = QColor(100, 100, 50)  # dark yellow
        elif row_data.status == "complete":
            color = QColor(50, 100, 50)  # dark green
        elif row_data.status == "error":
            color = QColor(100, 50, 50)  # dark red
        else:
            color = QColor(60, 60, 60)

        # apply color to editable cells
        for col in [self.COL_LAMBDA, self.COL_NA, self.COL_MAG, self.COL_DEFOC, self.COL_ASTIG]:
            self.table.item(idx, col).setBackground(QBrush(color))

        self.table.blockSignals(False)

    def _recalculate_row_params(self, idx: int):
        """recalculate computed parameters for one row"""
        if idx < 0 or idx >= len(self.table_rows):
            return

        row = self.table_rows[idx]
        sample_size = row.sample_size

        choice = self.param_choice_combo.currentText()
        units = self.source_param_units_combo.currentText()

        # prevent division by zero
        wavelength = max(row.wavelength, 0.001)
        back_aperture = max(row.back_aperture, 0.001)
        magnification = max(row.magnification, 0.001)
        aperture = magnification * back_aperture

        if choice == 'Diam pupil':
            diam_pupil = max(row.diam_pupil, 0.001)
            step_pupil = diam_pupil / max(sample_size, 1)
            step_im_can = 1 / max(step_pupil * sample_size, 0.001)
            step_obj_can = step_im_can
        elif choice == 'Step pupil':
            step_pupil = max(row.step_pupil, 0.001)
            diam_pupil = step_pupil * sample_size
            step_im_can = 1 / max(step_pupil * sample_size, 0.001)
            step_obj_can = step_im_can
        elif choice == 'Step object':
            if units == 'c.u.':
                step_obj_can = max(row.step_obj_can, 0.001)
            else:  # μm
                step_obj_microns = max(row.step_obj_microns, 0.001)
                step_obj_can = step_obj_microns * aperture / wavelength
            step_pupil = 1 / max(step_obj_can * sample_size, 0.001)
            diam_pupil = step_pupil * sample_size
            step_im_can = step_obj_can
        elif choice == 'Step image':
            if units == 'c.u.':
                step_im_can = max(row.step_im_can, 0.001)
            else:  # μm
                step_im_microns = max(row.step_im_microns, 0.001)
                step_im_can = step_im_microns * back_aperture / wavelength
            step_obj_can = step_im_can
            step_pupil = 1 / max(step_im_can * sample_size, 0.001)
            diam_pupil = step_pupil * sample_size
        else:
            return

        row.diam_pupil = diam_pupil
        row.step_pupil = step_pupil
        row.step_obj_can = step_obj_can
        row.step_im_can = step_im_can
        row.step_obj_microns = step_obj_can * wavelength / aperture
        row.step_im_microns = step_im_can * wavelength / back_aperture

    def _recalculate_all_rows_params(self):
        """recalculate params for all rows"""
        for idx in range(len(self.table_rows)):
            self._recalculate_row_params(idx)
            self._update_table_row(idx)

    def _refresh_table_column_colors(self):
        """refresh column colors after source param change"""
        source_col = self._get_source_param_column()

        for row_idx in range(len(self.table_rows)):
            for col in range(self.COL_STEP_OBJ_CAN, self.COL_STEP_PUP + 1):
                item = self.table.item(row_idx, col)
                if item:
                    if col == source_col:
                        item.setBackground(
                            QBrush(QColor(100, 150, 200)))  # blue
                    else:
                        item.setBackground(
                            QBrush(QColor(80, 80, 80)))  # dark gray

    # ===== TABLE EVENTS =====

    def _on_table_selection_changed(self):
        """row selection changed"""
        selected = self.table.selectedIndexes()
        if not selected:
            self.selected_row_idx = -1
            return

        row_idx = selected[0].row()
        self.selected_row_idx = row_idx

        if 0 <= row_idx < len(self.table_rows):
            row = self.table_rows[row_idx]

            # sync source param input with selected row
            choice = self.param_choice_combo.currentText()
            units = self.source_param_units_combo.currentText()

            self.source_param_spin.blockSignals(True)
            if choice == 'Diam pupil':
                self.source_param_spin.setValue(row.diam_pupil)
            elif choice == 'Step pupil':
                self.source_param_spin.setValue(row.step_pupil)
            elif choice == 'Step object':
                if units == 'c.u.':
                    self.source_param_spin.setValue(row.step_obj_can)
                else:
                    self.source_param_spin.setValue(row.step_obj_microns)
            elif choice == 'Step image':
                if units == 'c.u.':
                    self.source_param_spin.setValue(row.step_im_can)
                else:
                    self.source_param_spin.setValue(row.step_im_microns)
            self.source_param_spin.blockSignals(False)

            # show PSF if computed
            if row.status == "complete" and row.psf_data is not None:
                self.current_psf = row.psf_data
                self.current_params = row.get_params()
                self.current_step_microns = row.step_obj_microns
                self.current_compute_time = row.compute_time
                logger.info(
                    f"Displaying PSF for row {row_idx + 1}: defocus={row.defocus}, max={np.max(row.psf_data):.6f}")
                self._update_plots()
                self._update_info()
            else:
                self.plot_cross_sections.clear()
                self.plot_2d_psf.clear()
                self.info_label.setText("Max: N/A | Time: N/A")

        logger.info(f"Selected row {row_idx + 1}")

    def _on_table_item_changed(self, item: QTableWidgetItem):
        """cell edited"""
        if self.table.signalsBlocked():
            return

        row_idx = item.row()
        col_idx = item.column()

        if row_idx < 0 or row_idx >= len(self.table_rows):
            return

        row = self.table_rows[row_idx]

        # validate input is a number
        try:
            value = float(item.text())
        except ValueError:
            # restore original value
            self.table.blockSignals(True)
            self._update_table_row(row_idx)
            self.table.blockSignals(False)

            QMessageBox.warning(
                self, "Invalid Input",
                f"Cannot convert '{item.text()}' to a number.\n\n"
                f"Please enter a valid numeric value (e.g., 0.555, 1.2, 100).")
            logger.warning(
                f"Invalid input in table: '{item.text()}' at row {row_idx+1}, col {col_idx}")
            return

        # apply value to corresponding field
        if col_idx == self.COL_LAMBDA:
            row.wavelength = value
        elif col_idx == self.COL_NA:
            row.back_aperture = value
        elif col_idx == self.COL_MAG:
            row.magnification = value
        elif col_idx == self.COL_DEFOC:
            row.defocus = value
        elif col_idx == self.COL_ASTIG:
            row.astigmatism = value
        else:
            return

        row.status = "not_computed"
        row.strehl_ratio = 0.0
        row.psf_data = None

        # invalidate system PSF when any row changes
        self.system_psf_valid = False

        self._recalculate_row_params(row_idx)
        self._update_table_row(row_idx)

        logger.info(f"Row {row_idx + 1} modified")

    def _on_table_context_menu(self, pos):
        """right-click context menu"""
        index = self.table.indexAt(pos)
        if not index.isValid():
            return

        row_idx = index.row()

        menu = QMenu()

        # add row before
        act_add_before = menu.addAction("Add Row Before")
        act_add_before.triggered.connect(
            lambda: self._insert_row_before(row_idx))

        # add row after
        act_add_after = menu.addAction("Add Row After")
        act_add_after.triggered.connect(
            lambda: self._insert_row_after(row_idx))

        menu.addSeparator()

        # randomize
        act_randomize = menu.addAction("Randomize")
        act_randomize.triggered.connect(lambda: self._randomize_row(row_idx))

        # reset to default
        act_reset = menu.addAction("Reset to Default")
        act_reset.triggered.connect(lambda: self._reset_row(row_idx))

        menu.addSeparator()

        # delete row
        act_delete = menu.addAction("Delete Row")
        act_delete.triggered.connect(lambda: self._delete_row(row_idx))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ===== CONTROL BAR EVENTS =====

    def _on_param_choice_changed(self):
        """source parameter choice changed"""
        choice = self.param_choice_combo.currentText()

        # update units combo availability
        if choice in ['Diam pupil', 'Step pupil']:
            # these are always in c.u.
            self.source_param_units_combo.setCurrentText('c.u.')
            self.source_param_units_combo.setEnabled(False)
        else:
            # Step object and Step image can be c.u. or μm
            self.source_param_units_combo.setEnabled(True)

        # update spin box range and value
        self.source_param_spin.blockSignals(True)
        if choice == 'Diam pupil':
            self.source_param_spin.setRange(0.1, 100.0)
            self.source_param_spin.setValue(7.5)
            self.source_param_spin.setDecimals(3)
        elif choice == 'Step pupil':
            self.source_param_spin.setRange(0.001, 1.0)
            self.source_param_spin.setValue(0.015)
            self.source_param_spin.setDecimals(6)
        elif choice == 'Step object':
            if self.source_param_units_combo.currentText() == 'c.u.':
                self.source_param_spin.setRange(0.001, 10.0)
                self.source_param_spin.setValue(0.133)
            else:
                self.source_param_spin.setRange(0.001, 100.0)
                self.source_param_spin.setValue(0.073)
            self.source_param_spin.setDecimals(6)
        elif choice == 'Step image':
            if self.source_param_units_combo.currentText() == 'c.u.':
                self.source_param_spin.setRange(0.001, 10.0)
                self.source_param_spin.setValue(0.133)
            else:
                self.source_param_spin.setRange(0.001, 100.0)
                self.source_param_spin.setValue(0.462)
            self.source_param_spin.setDecimals(6)
        self.source_param_spin.blockSignals(False)

        # recalc all rows
        self._recalculate_all_rows_params()
        self._refresh_table_column_colors()

        logger.info(f"Source parameter changed to: {choice}")

    def _on_source_param_units_changed(self, units: str):
        """source parameter units changed"""
        choice = self.param_choice_combo.currentText()

        if choice not in ['Step object', 'Step image']:
            return

        # update spin box range
        self.source_param_spin.blockSignals(True)
        if units == 'c.u.':
            self.source_param_spin.setRange(0.001, 10.0)
            if choice == 'Step object':
                self.source_param_spin.setValue(0.133)
            else:
                self.source_param_spin.setValue(0.133)
        else:  # μm
            self.source_param_spin.setRange(0.001, 100.0)
            if choice == 'Step object':
                self.source_param_spin.setValue(0.073)
            else:
                self.source_param_spin.setValue(0.462)
        self.source_param_spin.blockSignals(False)

        # recalc all rows and refresh colors
        self._recalculate_all_rows_params()
        self._refresh_table_column_colors()

        logger.info(f"Source parameter units changed to: {units}")

    def _on_source_param_value_changed(self, value: float):
        """source parameter value changed in spin box - apply to ALL rows"""
        if not self.table_rows:
            return

        choice = self.param_choice_combo.currentText()
        units = self.source_param_units_combo.currentText()

        # apply to all rows
        for idx, row in enumerate(self.table_rows):
            if choice == 'Diam pupil':
                row.diam_pupil = value
            elif choice == 'Step pupil':
                row.step_pupil = value
            elif choice == 'Step object':
                if units == 'c.u.':
                    row.step_obj_can = value
                else:
                    row.step_obj_microns = value
            elif choice == 'Step image':
                if units == 'c.u.':
                    row.step_im_can = value
                else:
                    row.step_im_microns = value

            row.status = "not_computed"
            row.strehl_ratio = 0.0
            row.psf_data = None

            self._recalculate_row_params(idx)
            self._update_table_row(idx)

        # invalidate system PSF when source parameter changes
        self.system_psf_valid = False

        logger.info(
            f"Source parameter '{choice}' set to {value} {units} for all {len(self.table_rows)} rows")

    def _on_units_changed(self):
        """units changed"""
        if self.radio_microns.isChecked():
            self.current_units = 'microns'
        elif self.radio_canonical.isChecked():
            self.current_units = 'canonical'
        else:
            self.current_units = 'pixels'

        if self.current_psf is not None:
            self._update_plots()

    # ===== BUTTON ACTIONS =====

    def _on_compute_all_clicked(self):
        """compute all rows"""
        if not self.table_rows:
            QMessageBox.information(self, "No Rows", "No rows to compute.")
            return

        indices = list(range(len(self.table_rows)))
        self._compute_multiple_rows(indices)

    def _on_compute_selected_clicked(self):
        """compute selected rows"""
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(
                self, "No Selection", "Please select rows to compute.")
            return

        indices = [idx.row() for idx in selected]
        self._compute_multiple_rows(indices)

    def _on_compute_system_clicked(self):
        """compute system PSF (convolution of all rows)"""
        if not self.table_rows:
            QMessageBox.information(
                self, "No Rows", "No rows to compute system PSF.")
            return

        # check if system PSF is already valid
        if self.system_psf_valid:
            # just display it
            self._display_system_psf()
            logger.info("Displayed cached system PSF")
            return

        # check if all rows are computed
        uncomputed = []
        for idx, row in enumerate(self.table_rows):
            if row.status != "complete" or row.psf_data is None:
                uncomputed.append(idx)

        if uncomputed:
            # compute missing rows first automatically
            logger.info(
                f"Computing {len(uncomputed)} uncomputed rows for system PSF...")
            self.compute_system_after = True  # set flag
            self._compute_multiple_rows(uncomputed)
        else:
            # all rows computed, compute system PSF immediately
            self._compute_system_psf()

    def _compute_system_psf(self):
        """compute system PSF by convolving all row PSFs"""
        from scipy.signal import fftconvolve
        import time

        start_time = time.time()

        # start with first row PSF
        result_psf = self.table_rows[0].psf_data.copy()

        # convolve with each subsequent row
        for idx in range(1, len(self.table_rows)):
            row = self.table_rows[idx]
            result_psf = fftconvolve(result_psf, row.psf_data, mode='same')
            # normalize after each convolution
            result_psf = result_psf / np.sum(result_psf)

        self.system_psf = result_psf
        self.system_psf_valid = True
        self.system_compute_time = time.time() - start_time

        logger.info(
            f"System PSF computed from {len(self.table_rows)} rows in {self.system_compute_time:.3f}s")

        # display system PSF
        self._display_system_psf()

    def _display_system_psf(self):
        """display system PSF on plots"""
        if self.system_psf is None:
            return

        # use parameters from first row for display
        first_row = self.table_rows[0]
        self.current_psf = self.system_psf
        self.current_params = first_row.get_params()
        self.current_step_microns = first_row.step_obj_microns
        self.current_compute_time = self.system_compute_time

        self._update_plots()
        self._update_info()

        logger.info("System PSF displayed")

    def _on_clear_table_clicked(self):
        """clear all rows and reset to single default row"""
        if not self.table_rows:
            return

        reply = QMessageBox.question(
            self, "Clear Table",
            "Reset table to default?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.table_rows.clear()
            self.table.setRowCount(0)
            self.selected_row_idx = -1
            self._clear_plots()

            # add one default row
            default_row = OpticalSystemRow()
            self._add_row(default_row)
            self.table.selectRow(0)
            self.selected_row_idx = 0

            logger.info("Cleared table and reset to default row")

    def _on_save_config_clicked(self):
        """save configuration to JSON"""
        if not self.table_rows:
            QMessageBox.information(self, "No Data", "No rows to save.")
            return

        # default filename with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"optical_system_config_{timestamp}.json"

        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration", default_filename, "JSON Files (*.json)"
        )

        if not filename:
            return

        try:
            config = {
                'version': '1.0',
                'source_param': self.param_choice_combo.currentText(),
                'source_param_value': self.source_param_spin.value(),
                'source_param_units': self.source_param_units_combo.currentText(),
                'rows': [row.to_dict() for row in self.table_rows]
            }

            with open(filename, 'w') as f:
                json.dump(config, f, indent=2)

            logger.info(f"Saved configuration to {filename}")
            QMessageBox.information(
                self, "Saved", f"Configuration saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to save configuration:\n{e}")

    def _on_load_config_clicked(self):
        """load configuration from JSON"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Configuration", "", "JSON Files (*.json)"
        )

        if not filename:
            return

        try:
            with open(filename, 'r') as f:
                config = json.load(f)

            # validate config format
            if 'version' not in config:
                raise ValueError("Missing 'version' field in config file")
            if 'rows' not in config:
                raise ValueError("Missing 'rows' field in config file")
            if not isinstance(config['rows'], list):
                raise ValueError("'rows' must be a list")
            if len(config['rows']) == 0:
                raise ValueError("Config file contains no rows")

            # validate each row has required fields
            required_fields = ['wavelength', 'back_aperture',
                               'magnification', 'sample_size']
            for i, row_dict in enumerate(config['rows']):
                for field in required_fields:
                    if field not in row_dict:
                        raise ValueError(
                            f"Row {i+1} missing required field '{field}'")

            # if validation passed, load config
            self.table_rows.clear()
            self.table.setRowCount(0)

            # restore source parameter settings (block signals to prevent premature updates)
            self.param_choice_combo.blockSignals(True)
            self.source_param_units_combo.blockSignals(True)
            self.source_param_spin.blockSignals(True)

            if 'source_param' in config:
                self.param_choice_combo.setCurrentText(config['source_param'])
            if 'source_param_units' in config:
                self.source_param_units_combo.setCurrentText(
                    config['source_param_units'])
            if 'source_param_value' in config:
                self.source_param_spin.setValue(config['source_param_value'])

            self.param_choice_combo.blockSignals(False)
            self.source_param_units_combo.blockSignals(False)
            self.source_param_spin.blockSignals(False)

            # load rows - _add_row will recalculate parameters for each row
            for row_dict in config['rows']:
                row = OpticalSystemRow.from_dict(row_dict)
                self._add_row(row)

            # select first row if available
            if self.table_rows:
                self.table.selectRow(0)

            logger.info(
                f"Loaded configuration from {filename}: {len(self.table_rows)} rows")
            QMessageBox.information(
                self, "Loaded",
                f"Configuration loaded successfully:\n"
                f"File: {filename}\n"
                f"Rows: {len(self.table_rows)}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON file: {e}")
            QMessageBox.critical(
                self, "Invalid File",
                f"Failed to parse JSON file:\n{e}")
        except ValueError as e:
            logger.error(f"Invalid config format: {e}")
            QMessageBox.critical(
                self, "Invalid Configuration",
                f"Configuration file validation failed:\n{e}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to load configuration:\n{e}")

    def _on_export_plots_clicked(self):
        """export plots to PNG"""
        # check if there's data to export
        if self.current_psf is None:
            QMessageBox.warning(
                self, "No Data",
                "No PSF data to export.\n\n"
                "Please compute PSF for at least one row or select a computed row.")
            logger.warning("Export plots attempted with no PSF data")
            return

        # default filename with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"psf_plot_{timestamp}.png"

        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Plots", default_filename, "PNG Files (*.png)"
        )

        if not filename:
            return

        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg

            fig = Figure(figsize=(16, 8), dpi=100)

            # add title with parameters
            if self.selected_row_idx >= 0 and self.selected_row_idx < len(self.table_rows):
                row = self.table_rows[self.selected_row_idx]
                title = (f"PSF: λ={row.wavelength:.3f}μm, NA={row.back_aperture:.2f}, "
                         f"Mag={row.magnification:.1f}x, Defoc={row.defocus:.2f}λ, "
                         f"Astig={row.astigmatism:.2f}λ, Strehl={row.strehl_ratio:.4f}")
                fig.suptitle(title, fontsize=14)

            psf = self.current_psf
            size = psf.shape[0]

            # normalize PSF for visualization
            psf_normalized = psf / np.max(psf) if np.max(psf) > 0 else psf

            # calculate coordinates
            if self.current_units == 'microns':
                coords = np.arange(size) * self.current_step_microns
                coords = coords - coords[size // 2]
                unit_label = 'μm'
            elif self.current_units == 'canonical':
                step_canonical = (
                    self.current_params['wavelength'] / self.current_params['back_aperture']) / size
                coords = np.arange(size) * step_canonical
                coords = coords - coords[size // 2]
                unit_label = 'canonical units'
            else:
                coords = np.arange(size)
                coords = coords - size // 2
                unit_label = 'pixels'

            # subplot 1: cross-sections
            ax1 = fig.add_subplot(1, 2, 1)
            center_idx = size // 2
            x_section = psf_normalized[center_idx, :]
            y_section = psf_normalized[:, center_idx]

            ax1.plot(coords, x_section, 'r-', label='X section', linewidth=2)
            ax1.plot(coords, y_section, 'b-', label='Y section', linewidth=2)
            ax1.set_xlabel(f'Position [{unit_label}]')
            ax1.set_ylabel('Normalized Intensity')
            ax1.set_title('PSF Cross-Sections')
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # subplot 2: 2D PSF
            ax2 = fig.add_subplot(1, 2, 2)
            extent = [coords[0], coords[-1], coords[0], coords[-1]]
            ax2.imshow(psf_normalized, cmap='gray', extent=extent,
                       origin='lower', aspect='equal', vmin=0, vmax=1)
            ax2.set_xlabel(f'X [{unit_label}]')
            ax2.set_ylabel(f'Y [{unit_label}]')
            ax2.set_title('2D PSF (Grayscale)')

            fig.tight_layout()

            canvas = FigureCanvasAgg(fig)
            canvas.print_figure(filename, dpi=100)

            logger.info(f"Plots exported to {filename}")
            QMessageBox.information(
                self, "Exported", f"Plots saved to:\n{filename}")
        except Exception as e:
            logger.error(f"Failed to export plots: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to export plots:\n{e}")

    # ===== ROW OPERATIONS =====

    def _randomize_row(self, idx: int):
        """randomize row parameters (only editable params, not source param)"""
        if idx < 0 or idx >= len(self.table_rows):
            return

        row = self.table_rows[idx]

        # randomize only basic editable parameters
        row.wavelength = random.uniform(0.4, 0.7)
        row.back_aperture = random.uniform(0.5, 1.5)
        row.magnification = random.uniform(50, 200)
        row.defocus = random.uniform(-2.0, 2.0)
        row.astigmatism = random.uniform(-2.0, 2.0)

        # do NOT randomize sample_size (stays as is)
        # do NOT randomize source parameter (diam_pupil, step_pupil, etc.)

        row.status = "not_computed"
        row.strehl_ratio = 0.0
        row.psf_data = None

        # invalidate system PSF when row changes
        self.system_psf_valid = False

        self._recalculate_row_params(idx)

        self.table.blockSignals(True)
        self.table.item(idx, self.COL_LAMBDA).setText(f"{row.wavelength:.3f}")
        self.table.item(idx, self.COL_NA).setText(f"{row.back_aperture:.2f}")
        self.table.item(idx, self.COL_MAG).setText(f"{row.magnification:.1f}")
        self.table.item(idx, self.COL_DEFOC).setText(f"{row.defocus:.2f}")
        self.table.item(idx, self.COL_ASTIG).setText(f"{row.astigmatism:.2f}")
        self.table.blockSignals(False)

        self._update_table_row(idx)
        logger.info(f"Randomized row {idx + 1} (basic params only)")

    def _reset_row(self, idx: int):
        """reset row to defaults"""
        if idx < 0 or idx >= len(self.table_rows):
            return

        defaults = OpticalSystemRow()
        row = self.table_rows[idx]
        row.wavelength = defaults.wavelength
        row.back_aperture = defaults.back_aperture
        row.magnification = defaults.magnification
        row.defocus = defaults.defocus
        row.astigmatism = defaults.astigmatism
        row.status = "not_computed"
        row.strehl_ratio = 0.0
        row.psf_data = None

        # invalidate system PSF when row changes
        self.system_psf_valid = False

        self._recalculate_row_params(idx)

        self.table.blockSignals(True)
        self.table.item(idx, self.COL_LAMBDA).setText(f"{row.wavelength:.3f}")
        self.table.item(idx, self.COL_NA).setText(f"{row.back_aperture:.2f}")
        self.table.item(idx, self.COL_MAG).setText(f"{row.magnification:.1f}")
        self.table.item(idx, self.COL_DEFOC).setText(f"{row.defocus:.2f}")
        self.table.item(idx, self.COL_ASTIG).setText(f"{row.astigmatism:.2f}")
        self.table.blockSignals(False)

        self._update_table_row(idx)
        logger.info(f"Reset row {idx + 1}")

    def _duplicate_row(self, idx: int):
        """duplicate a row"""
        if idx < 0 or idx >= len(self.table_rows):
            return

        original = self.table_rows[idx]
        new_row = OpticalSystemRow(
            wavelength=original.wavelength,
            back_aperture=original.back_aperture,
            magnification=original.magnification,
            defocus=original.defocus,
            astigmatism=original.astigmatism,
            sample_size=original.sample_size
        )

        self._add_row(new_row)
        logger.info(f"Duplicated row {idx + 1}")

    def _delete_row(self, idx: int, clear_plots: bool = True):
        """delete a row"""
        if idx < 0 or idx >= len(self.table_rows):
            return

        # remember if this is the selected row BEFORE deletion
        is_selected = (self.selected_row_idx == idx)
        logger.info(
            f"Deleting row {idx + 1}, is_selected={is_selected}, clear_plots={clear_plots}")

        del self.table_rows[idx]
        self.table.removeRow(idx)

        # invalidate system PSF when rows change
        self.system_psf_valid = False

        # use saved is_selected instead of checking again
        # (table signals may change selected_row_idx during removeRow)
        if is_selected:
            self.selected_row_idx = -1
            # clear plots when selected row is deleted
            if clear_plots:
                logger.info("Calling _clear_plots() from _delete_row")
                self._clear_plots()
        elif self.selected_row_idx > idx:
            self.selected_row_idx -= 1

        logger.info(f"Row {idx + 1} deleted")

    def _insert_row_before(self, idx: int):
        """insert new row before selected row"""
        if idx < 0 or idx >= len(self.table_rows):
            return

        new_row = OpticalSystemRow()

        # insert into data list
        self.table_rows.insert(idx, new_row)

        # recalculate parameters for new row
        self._recalculate_row_params(idx)

        # insert into table widget
        self._insert_table_row(idx)

        # update selected row index if needed
        if self.selected_row_idx >= idx:
            self.selected_row_idx += 1

        logger.info(f"Inserted row before position {idx + 1}")

    def _insert_row_after(self, idx: int):
        """insert new row after selected row"""
        if idx < 0 or idx >= len(self.table_rows):
            return

        new_row = OpticalSystemRow()
        insert_pos = idx + 1

        # insert into data list
        self.table_rows.insert(insert_pos, new_row)

        # recalculate parameters for new row
        self._recalculate_row_params(insert_pos)

        # insert into table widget
        self._insert_table_row(insert_pos)

        # update selected row index if needed
        if self.selected_row_idx > idx:
            self.selected_row_idx += 1

        logger.info(f"Inserted row after position {idx + 1}")

    # ===== COMPUTATION =====

    def _compute_row(self, idx: int):
        """compute PSF for one row"""
        if idx < 0 or idx >= len(self.table_rows):
            return

        row = self.table_rows[idx]

        is_valid, error_msg = self._validate_row(row)
        if not is_valid:
            row.status = "error"
            row.error_message = error_msg
            self._update_table_row(idx)
            QMessageBox.critical(self, "Validation Error", error_msg)
            logger.error(f"Row {idx + 1} validation failed: {error_msg}")
            return

        row.status = "computing"
        self._update_table_row(idx)

        params = row.get_params()

        thread = PSFComputeThread(params)
        thread.result_ready.connect(lambda psf, time, info:
                                    self._on_row_computed(idx, psf, time, info))
        thread.error_occurred.connect(lambda err:
                                      self._on_row_error(idx, err))

        self.compute_thread = thread
        thread.start()

    def _compute_multiple_rows(self, indices: List[int]):
        """compute multiple rows sequentially"""
        if not indices:
            return

        indices = [i for i in indices if 0 <= i < len(self.table_rows)]
        if not indices:
            return

        self.computing_rows = indices.copy()
        self.computation_cancelled = False

        self.progress_dialog = QProgressDialog(
            f"Computing PSF 0/{len(indices)}...",
            "Cancel",
            0, len(indices),
            self
        )
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.canceled.connect(self._on_computation_cancelled)
        self.progress_dialog.show()

        self._compute_next_in_queue()

    def _compute_next_in_queue(self):
        """compute next row in queue"""
        if self.computation_cancelled or not self.computing_rows:
            if hasattr(self, 'progress_dialog'):
                self.progress_dialog.close()
            logger.info("Computation queue finished")
            return

        idx = self.computing_rows.pop(0)

        if hasattr(self, 'progress_dialog'):
            total_rows = self.progress_dialog.maximum()
            current_row = total_rows - len(self.computing_rows)
            self.progress_dialog.setValue(current_row)
            self.progress_dialog.setLabelText(
                f"Computing PSF {current_row}/{total_rows}...")

        self._compute_row(idx)

    def _on_row_computed(self, idx: int, psf_data: np.ndarray, elapsed_time: float, info: dict):
        """callback when row computation finishes"""
        if idx < 0 or idx >= len(self.table_rows):
            return

        row = self.table_rows[idx]
        row.psf_data = psf_data
        row.compute_time = elapsed_time
        row.status = "complete"
        row.error_message = ""

        logger.info(
            f"Row {idx + 1} PSF computed: defocus={row.defocus}, max={np.max(psf_data):.6f}, center={psf_data[psf_data.shape[0]//2, psf_data.shape[0]//2]:.6f}")

        # calculate Strehl ratio: ratio of peak intensity to total energy
        # Note: this is a simplified approximation
        # True Strehl requires comparison with ideal PSF
        center_idx = psf_data.shape[0] // 2
        center_intensity = psf_data[center_idx, center_idx]
        total_energy = np.sum(psf_data)
        # Normalize center intensity by total energy and PSF size for comparison
        # This gives a measure of PSF quality (higher = better)
        row.strehl_ratio = center_intensity / \
            (total_energy / psf_data.size) if total_energy > 0 else 0.0

        self._update_table_row(idx)

        logger.info(
            f"Row {idx + 1} computed: Strehl={row.strehl_ratio:.4f}, time={elapsed_time:.3f}s")

        # update plots only if this is the selected row AND we're not computing for system PSF
        if idx == self.selected_row_idx and not self.compute_system_after:
            self.current_psf = psf_data
            self.current_params = row.get_params()
            self.current_step_microns = info['step_microns']
            self.current_compute_time = elapsed_time
            self._update_plots()
            self._update_info()

        if self.computing_rows:
            self._compute_next_in_queue()
        else:
            if hasattr(self, 'progress_dialog'):
                # disconnect canceled signal before closing to avoid false cancellation
                self.progress_dialog.canceled.disconnect()
                self.progress_dialog.close()
            # check if we need to compute system PSF after all rows
            if self.compute_system_after:
                self.compute_system_after = False
                logger.info("All rows computed, computing system PSF...")
                self._compute_system_psf()

    def _on_row_error(self, idx: int, error_msg: str):
        """callback when row computation fails"""
        if idx < 0 or idx >= len(self.table_rows):
            return

        row = self.table_rows[idx]
        row.status = "error"
        row.error_message = error_msg
        self._update_table_row(idx)

        logger.error(f"Row {idx + 1} computation error: {error_msg}")

        if self.computing_rows:
            self._compute_next_in_queue()
        else:
            if hasattr(self, 'progress_dialog'):
                # disconnect canceled signal before closing
                self.progress_dialog.canceled.disconnect()
                self.progress_dialog.close()

    def _on_computation_cancelled(self):
        """cancel computation"""
        self.computation_cancelled = True
        self.computing_rows.clear()
        self.compute_system_after = False  # reset flag
        logger.info("Computation cancelled by user")

    # ===== VISUALIZATION =====

    def _update_plots(self):
        """update PSF plots"""
        if self.current_psf is None:
            return

        psf = self.current_psf
        size = psf.shape[0]

        # normalize PSF to max=1 for better visualization
        psf_normalized = psf / np.max(psf) if np.max(psf) > 0 else psf

        if self.current_units == 'microns':
            coords = np.arange(size) * self.current_step_microns
            coords = coords - coords[size // 2]
            unit_label = 'μm'
        elif self.current_units == 'canonical':
            step_canonical = (
                self.current_params['wavelength'] / self.current_params['back_aperture']) / size
            coords = np.arange(size) * step_canonical
            coords = coords - coords[size // 2]
            unit_label = 'canonical units'
        else:
            coords = np.arange(size)
            coords = coords - size // 2
            unit_label = 'pixels'

        self.plot_cross_sections.clear()
        self.plot_2d_psf.clear()

        ax0 = self.plot_cross_sections.get_axes()
        center_idx = size // 2

        x_section = psf_normalized[center_idx, :]
        ax0.plot(coords, x_section, 'r-', label='X section', linewidth=2)

        y_section = psf_normalized[:, center_idx]
        ax0.plot(coords, y_section, 'b-', label='Y section', linewidth=2)

        ax0.set_xlabel(f'Position [{unit_label}]')
        ax0.set_ylabel('Normalized Intensity')
        ax0.set_title('PSF Cross-Sections')
        ax0.legend()
        ax0.grid(True, alpha=0.3)
        ax0.set_aspect('auto')

        ax1 = self.plot_2d_psf.get_axes()
        extent = [coords[0], coords[-1], coords[0], coords[-1]]

        ax1.imshow(psf_normalized, cmap='gray', extent=extent,
                   origin='lower', aspect='equal', vmin=0, vmax=1)
        ax1.set_xlabel(f'X [{unit_label}]')
        ax1.set_ylabel(f'Y [{unit_label}]')
        ax1.set_title('2D PSF (Grayscale)')
        ax1.set_aspect('equal', adjustable='box')

        self.plot_cross_sections.refresh()
        self.plot_2d_psf.refresh()

        # send PSF to image tab
        self.psf_computed.emit(self.current_psf)
        logger.debug(f"PSF data sent to Image Processing tab")

    def _clear_plots(self):
        """clear all plots and reset current data"""
        logger.info("Clearing plots...")

        self.current_psf = None
        self.current_params = {}
        self.current_step_microns = 0.0
        self.current_compute_time = 0.0

        # clear both plot widgets completely (no axes, just white background)
        self.plot_cross_sections.clear()
        self.plot_2d_psf.clear()

        # clear info (same as when selecting uncomputed row)
        self.info_label.setText("Max: N/A | Time: N/A")

        logger.info("Plots cleared successfully")

    def _update_info(self):
        """update info label"""
        if self.current_psf is None:
            return

        max_intensity = np.max(self.current_psf)
        self.info_label.setText(
            f"Max: {max_intensity:.6f} | Time: {self.current_compute_time:.3f} s")

    # ===== INITIALIZATION =====

    def _initialize_default_rows(self):
        """initialize with 3 default rows"""
        logger.info("Initializing with 3 default rows...")

        defocus_values = [-0.2, 0.0, 0.2]

        for defoc in defocus_values:
            row = OpticalSystemRow(defocus=defoc)
            self._add_row(row)

        self.table.selectRow(0)
        self.selected_row_idx = 0

        # auto-compute first row
        self._compute_row(0)

        logger.info("Default rows initialized, computing first row...")
