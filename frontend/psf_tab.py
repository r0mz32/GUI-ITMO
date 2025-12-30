# PSF Calculator Tab - Refactored Version

import sys
import os
import numpy as np
import logging
from typing import List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPushButton,
    QLabel, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QMarginsF, QRectF
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
from PyQt6.QtGui import QPageLayout, QPageSize
from psf_wrapper import PSFCalculator

# import new modular components
from frontend.models import OpticalSystemRow
from frontend.handlers import TableHandler, ComputeHandler, FileHandler
from frontend.ui_components import ControlPanel, create_optical_table
from frontend.utils import calculate_step_params
from frontend.widgets.plot_widget import PlotWidget

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(
    os.path.dirname(__file__), '..', '..', 'backend'))


class PSFTab(QWidget):
    """Main PSF Calculator Tab - Controller"""

    psf_computed = pyqtSignal(np.ndarray)

    def __init__(self, parent=None):
        super().__init__(parent)
        logger.info("Initializing Optical System Analyzer tab...")

        # backend
        self.psf_calculator = PSFCalculator()
        logger.info("PSF Calculator backend initialized")

        # data
        self.table_rows: List[OpticalSystemRow] = []
        self.selected_row_idx: int = -1

        # current displayed PSF
        self.current_psf = None
        self.current_params = None
        self.current_step_microns = None
        self.current_compute_time = None
        self.current_strehl_ratio = None

        # system PSF (convolution of all rows)
        self.system_psf = None
        self.system_psf_valid = False
        self.system_compute_time = 0.0
        self.system_strehl_ratio = None

        # computation state
        self.compute_system_after = False
        self.current_units = 'microns'

        # column indices
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

        # initialize handlers after UI is created
        self._initialize_handlers()

        # init with 3 default rows
        self._initialize_default_rows()

    def _create_ui(self):
        """create main UI layout"""
        main_layout = QVBoxLayout()

        # row 1: plots
        plots_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.plot_cross_sections = PlotWidget(toolbar=True)
        self.plot_cross_sections.figure.set_size_inches(8, 6)
        plots_splitter.addWidget(self.plot_cross_sections)

        self.plot_2d_psf = PlotWidget(toolbar=True)
        self.plot_2d_psf.figure.set_size_inches(6, 6)
        plots_splitter.addWidget(self.plot_2d_psf)

        plots_splitter.setSizes([550, 550])
        main_layout.addWidget(plots_splitter, stretch=10)

        # row 2: control panel (uses ControlPanel component)
        self.control_panel = ControlPanel()
        self.control_panel.units_changed.connect(self._on_units_changed)
        self.control_panel.source_param_changed.connect(
            self._on_param_choice_changed)
        self.control_panel.source_units_changed.connect(
            self._on_source_param_units_changed)
        self.control_panel.source_value_changed.connect(
            self._on_source_param_value_changed)
        self.control_panel.sample_size_changed.connect(
            self._on_sample_size_changed)

        # access widgets for compatibility
        self.param_choice_combo = self.control_panel.param_choice_combo
        self.source_param_units_combo = self.control_panel.source_param_units_combo
        self.source_param_spin = self.control_panel.source_param_spin
        self.info_label = self.control_panel.info_label

        main_layout.addWidget(self.control_panel)

        # row 3: button toolbar
        main_layout.addWidget(self._create_button_toolbar())

        # row 4: table (uses create_optical_table function)
        self.table = create_optical_table()
        self.table.itemSelectionChanged.connect(
            self._on_table_selection_changed)
        self.table.itemChanged.connect(self._on_table_item_changed)
        self.table.customContextMenuRequested.connect(
            self._on_table_context_menu)

        main_layout.addWidget(self.table, stretch=5)

        self.setLayout(main_layout)

    def _initialize_handlers(self):
        """initialize handler objects"""
        self.table_handler = TableHandler(self.table, self.table_rows, self)
        self.compute_handler = ComputeHandler(self.psf_calculator, self)
        self.file_handler = FileHandler(self)
        logger.info("Handlers initialized")

    def _create_button_toolbar(self):
        """create button toolbar"""
        widget = QWidget()
        main_layout = QHBoxLayout()
        main_layout.setSpacing(5)

        # group 1: computation
        group1_layout = QHBoxLayout()
        group1_layout.addStretch()
        btn_compute_all = QPushButton("Compute All")
        btn_compute_all.clicked.connect(self._on_compute_all_clicked)
        group1_layout.addWidget(btn_compute_all)
        btn_compute_selected = QPushButton("Compute Selected")
        btn_compute_selected.clicked.connect(self._on_compute_selected_clicked)
        group1_layout.addWidget(btn_compute_selected)
        group1_layout.addStretch()

        # group 2: system and clear
        group2_layout = QHBoxLayout()
        group2_layout.addStretch()
        btn_compute_system = QPushButton("Compute System PSF")
        btn_compute_system.clicked.connect(self._on_compute_system_clicked)
        group2_layout.addWidget(btn_compute_system)
        btn_clear = QPushButton("Clear All")
        btn_clear.clicked.connect(self._on_clear_table_clicked)
        group2_layout.addWidget(btn_clear)
        group2_layout.addStretch()

        # group 3: file operations
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

        # group 4: print operations
        group4_layout = QHBoxLayout()
        group4_layout.addStretch()
        btn_print = QPushButton("Print Report")
        btn_print.clicked.connect(self._on_print_clicked)
        group4_layout.addWidget(btn_print)
        btn_preview = QPushButton("Print Preview")
        btn_preview.clicked.connect(self._on_preview_clicked)
        group4_layout.addWidget(btn_preview)
        group4_layout.addStretch()

        # add groups with separators
        main_layout.addLayout(group1_layout, stretch=1)
        separator1 = QLabel("|")
        separator1.setStyleSheet("color: #555; font-size: 20px;")
        main_layout.addWidget(separator1)
        main_layout.addLayout(group2_layout, stretch=1)
        separator2 = QLabel("|")
        separator2.setStyleSheet("color: #555; font-size: 20px;")
        main_layout.addWidget(separator2)
        main_layout.addLayout(group3_layout, stretch=1)
        separator3 = QLabel("|")
        separator3.setStyleSheet("color: #555; font-size: 20px;")
        main_layout.addWidget(separator3)
        main_layout.addLayout(group4_layout, stretch=1)

        widget.setLayout(main_layout)
        return widget

    def _initialize_default_rows(self):
        """initialize with 3 default rows"""
        for _ in range(3):
            row = OpticalSystemRow()
            self.table_handler.add_row(row)

        # select first row
        if self.table_rows:
            self.table.selectRow(0)
            # compute first row
            self.compute_handler.compute_row(0)

    # ===== PARAMETER CALCULATIONS =====

    def _recalculate_row_params(self, idx: int):
        """recalculate computed parameters for one row"""
        if idx < 0 or idx >= len(self.table_rows):
            return

        row = self.table_rows[idx]
        choice = self.param_choice_combo.currentText()
        units = self.source_param_units_combo.currentText()

        # use calculations module
        result = calculate_step_params(row, choice, units)

        if result:
            row.diam_pupil = result['diam_pupil']
            row.step_pupil = result['step_pupil']
            row.step_obj_can = result['step_obj_can']
            row.step_im_can = result['step_im_can']
            row.step_obj_microns = result['step_obj_microns']
            row.step_im_microns = result['step_im_microns']

    # ===== EVENT HANDLERS - UI =====

    def _on_units_changed(self, units: str):
        """units changed"""
        self.current_units = units
        if self.current_psf is not None:
            self._update_plots()

    def _on_param_choice_changed(self, choice: str):
        """source parameter choice changed"""
        self._recalculate_all_rows_params()
        self.table_handler.refresh_column_colors()

    def _on_source_param_units_changed(self, units: str):
        """source parameter units changed"""
        # update spinbox range and default value based on new units
        self.control_panel.update_source_param_for_units_change(units)

        # apply the new default value to all rows
        new_value = self.source_param_spin.value()
        self._apply_source_param_to_all_rows(new_value, units)

        self.table_handler.refresh_column_colors()

    def _on_source_param_value_changed(self, value: float):
        """source parameter value changed - apply to ALL rows"""
        if not self.table_rows:
            return

        choice = self.param_choice_combo.currentText()
        units = self.source_param_units_combo.currentText()

        self._apply_source_param_to_all_rows(value, units)

    def _apply_source_param_to_all_rows(self, value: float, units: str):
        """apply source parameter value to all rows"""
        if not self.table_rows:
            return

        choice = self.param_choice_combo.currentText()

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
            self.table_handler.update_table_row(idx)

        self.system_psf_valid = False
        logger.info(
            f"Source parameter '{choice}' set to {value} {units} for all {len(self.table_rows)} rows")

    def _on_sample_size_changed(self, size: int):
        """sample size changed - apply to ALL rows"""
        if not self.table_rows:
            return

        for idx, row in enumerate(self.table_rows):
            row.sample_size = size
            row.status = "not_computed"
            row.strehl_ratio = 0.0
            row.psf_data = None

            self._recalculate_row_params(idx)
            self.table_handler.update_table_row(idx)

        self.system_psf_valid = False
        logger.info(f"Sample size set to {size} for all {len(self.table_rows)} rows")

    def _recalculate_all_rows_params(self):
        """recalculate params for all rows"""
        for idx in range(len(self.table_rows)):
            self._recalculate_row_params(idx)
            self.table_handler.update_table_row(idx)

    # ===== EVENT HANDLERS - TABLE =====

    def _on_table_selection_changed(self):
        """row selection changed"""
        selected = self.table.selectedIndexes()
        if not selected:
            return

        row_idx = selected[0].row()
        if row_idx == self.selected_row_idx:
            return

        self.selected_row_idx = row_idx

        # display PSF if computed
        if row_idx >= 0 and row_idx < len(self.table_rows):
            row = self.table_rows[row_idx]
            if row.status == "complete" and row.psf_data is not None:
                self.current_psf = row.psf_data
                self.current_params = row.get_params()
                self.current_step_microns = row.step_obj_microns
                self.current_compute_time = row.compute_time
                self.current_strehl_ratio = row.strehl_ratio
                self._update_plots()
                self._update_info()
            else:
                self._clear_plots()
                self.info_label.setText("Max: N/A | Time: N/A | Strehl: N/A")

        logger.info(f"Selected row {row_idx + 1}")

    def _on_table_item_changed(self, item):
        """cell edited"""
        if self.table.signalsBlocked():
            return

        row_idx = item.row()
        col_idx = item.column()

        if row_idx < 0 or row_idx >= len(self.table_rows):
            return

        row = self.table_rows[row_idx]

        # validate input
        from frontend.utils import validate_numeric_input
        is_valid, value, error_msg = validate_numeric_input(
            item.text(), "table value")

        if not is_valid:
            self.table.blockSignals(True)
            self.table_handler.update_table_row(row_idx)
            self.table.blockSignals(False)
            QMessageBox.warning(self, "Invalid Input", error_msg)
            logger.warning(
                f"Invalid input in table: '{item.text()}' at row {row_idx+1}, col {col_idx}")
            return

        # apply value
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
        self.system_psf_valid = False

        self._recalculate_row_params(row_idx)
        self.table_handler.update_table_row(row_idx)

        logger.info(f"Row {row_idx + 1} modified")

    def _on_table_context_menu(self, pos):
        """show context menu for table"""
        index = self.table.indexAt(pos)
        if not index.isValid():
            return

        row_idx = index.row()

        menu = QMenu(self)

        add_before_action = menu.addAction("Add Row Before")
        add_after_action = menu.addAction("Add Row After")
        menu.addSeparator()
        randomize_action = menu.addAction("Randomize")
        reset_action = menu.addAction("Reset to Default")
        menu.addSeparator()
        delete_action = menu.addAction("Delete Row")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))

        if action == add_before_action:
            self.table_handler.insert_row_before(row_idx)
        elif action == add_after_action:
            self.table_handler.insert_row_after(row_idx)
        elif action == randomize_action:
            self.table_handler.randomize_row(row_idx)
        elif action == reset_action:
            self.table_handler.reset_row(row_idx)
        elif action == delete_action:
            self.table_handler.delete_row(row_idx)

    # ===== EVENT HANDLERS - BUTTONS =====

    def _on_compute_all_clicked(self):
        """compute all rows"""
        indices = list(range(len(self.table_rows)))
        self.compute_handler.compute_multiple_rows(indices)

    def _on_compute_selected_clicked(self):
        """compute selected rows"""
        selected_rows = set(index.row()
                            for index in self.table.selectedIndexes())
        self.compute_handler.compute_multiple_rows(list(selected_rows))

    def _on_compute_system_clicked(self):
        """compute system PSF"""
        if not self.table_rows:
            QMessageBox.information(
                self, "No Rows", "No rows to compute system PSF.")
            return

        # check if system PSF is already valid
        if self.system_psf_valid:
            self.compute_handler.display_system_psf()
            logger.info("Displayed cached system PSF")
            return

        # check if all rows are computed
        uncomputed = []
        for idx, row in enumerate(self.table_rows):
            if row.status != "complete" or row.psf_data is None:
                uncomputed.append(idx)

        if uncomputed:
            # compute missing rows first
            logger.info(
                f"Computing {len(uncomputed)} uncomputed rows for system PSF...")
            self.compute_system_after = True
            self.compute_handler.compute_multiple_rows(uncomputed)
        else:
            self.compute_handler.compute_system_psf()

    def _on_clear_table_clicked(self):
        """reset table to default"""
        reply = QMessageBox.question(
            self, "Confirm", "Reset table to default?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.table_rows.clear()
            self.table.setRowCount(0)

            # add one default row
            row = OpticalSystemRow()
            self.table_handler.add_row(row)

            # select it
            self.table.selectRow(0)

            self._clear_plots()
            logger.info("Table reset to default")

    def _on_save_config_clicked(self):
        """save configuration"""
        self.file_handler.save_config()

    def _on_load_config_clicked(self):
        """load configuration"""
        self.file_handler.load_config()

    def _on_export_plots_clicked(self):
        """export plots"""
        self.file_handler.export_plots()

    def _on_print_clicked(self):
        """print report"""
        self._print_report()

    def _on_preview_clicked(self):
        """print preview"""
        self._print_preview()

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
        """clear all plots"""
        logger.info("Clearing plots...")

        self.current_psf = None
        self.current_params = {}
        self.current_step_microns = 0.0
        self.current_compute_time = 0.0
        self.current_strehl_ratio = None

        self.plot_cross_sections.clear()
        self.plot_2d_psf.clear()

        self.info_label.setText("Max: N/A | Time: N/A | Strehl: N/A")

        logger.info("Plots cleared successfully")

    def _update_info(self):
        """update info label"""
        if self.current_psf is None:
            return

        max_intensity = float(np.max(self.current_psf))

        # use stored Strehl ratio (set when PSF is displayed)
        self.control_panel.update_info(
            max_intensity, self.current_compute_time, self.current_strehl_ratio)

    # ===== PRINT OPERATIONS =====

    def _print_report(self):
        """print report using QPrintDialog"""
        try:
            from datetime import datetime
            import os

            # create printer with default settings
            printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
            printer.setPageOrientation(QPageLayout.Orientation.Portrait)
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            printer.setPageMargins(
                QMarginsF(20, 20, 20, 20), QPageLayout.Unit.Millimeter)

            # set default filename for PDF
            default_name = f"PSF_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            printer.setDocName(default_name)

            # set output file name (for "Print to PDF")
            default_path = os.path.join(os.path.expanduser("~"), default_name)
            printer.setOutputFileName(default_path)

            # create print dialog
            dialog = QPrintDialog(printer, self)
            if dialog.exec() == QPrintDialog.DialogCode.Accepted:
                self._do_print_report(printer)
        except Exception as e:
            logger.error(f"Print error: {e}")
            QMessageBox.critical(self, "Print Error", f"Failed to print:\n{e}")

    def _print_preview(self):
        """print preview using QPrintPreviewDialog"""
        try:
            from datetime import datetime
            import os

            # create printer with default settings
            printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
            printer.setPageOrientation(QPageLayout.Orientation.Portrait)
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            printer.setPageMargins(
                QMarginsF(20, 20, 20, 20), QPageLayout.Unit.Millimeter)

            # set default filename for PDF
            default_name = f"PSF_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            printer.setDocName(default_name)

            # set output file name (for "Print to PDF")
            default_path = os.path.join(os.path.expanduser("~"), default_name)
            printer.setOutputFileName(default_path)

            # create preview dialog
            preview = QPrintPreviewDialog(printer, self, Qt.WindowType.Window)
            preview.paintRequested.connect(self._do_print_report)
            preview.exec()
        except Exception as e:
            logger.error(f"Print preview error: {e}")
            QMessageBox.critical(
                self, "Print Preview Error", f"Failed to show preview:\n{e}")

    def _do_print_report(self, printer):
        """format and print the report"""
        from PyQt6.QtGui import QPainter, QFont, QTextDocument
        from datetime import datetime
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure

        # check if we have any computed data
        computed_rows = [i for i, row in enumerate(
            self.table_rows) if row.status == "complete"]
        if not computed_rows:
            QMessageBox.warning(
                self, "No Data", "No computed PSF data to print")
            return

        painter = QPainter(printer)
        page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
        font_height = painter.fontMetrics().ascent()
        page_num = 1

        # === PAGE 1: TABLE ===
        y_pos = self._print_header(painter, page_rect, font_height, page_num)

        # title
        title_font = QFont(painter.font())
        title_font.setPointSize(14)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(0, int(y_pos), "Optical System Analysis Report")
        y_pos += font_height * 2

        # restore normal font
        normal_font = QFont()
        normal_font.setPointSize(10)
        painter.setFont(normal_font)

        # parameters table
        html_table = self._generate_parameters_html()
        doc = QTextDocument()
        doc.setHtml(html_table)
        doc.setTextWidth(page_rect.width())
        doc.setDocumentMargin(0)

        painter.translate(0, int(y_pos))
        doc.drawContents(painter)
        table_height = doc.size().height()
        painter.translate(0, int(-y_pos))
        y_pos += table_height + font_height * 1

        # === PLOTS: FIT AS MANY AS POSSIBLE ON EACH PAGE ===
        plot_height_estimate = int(page_rect.height() * 0.28)
        footer_space = font_height * 2

        # prepare all plots to print
        plots_to_print = []
        for idx in computed_rows:
            row = self.table_rows[idx]
            plots_to_print.append({
                'type': 'row',
                'idx': idx,
                'row': row,
                'title': f"Row {idx + 1} PSF: λ={row.wavelength:.3f}μm, NA={row.back_aperture:.3f}, Mag={row.magnification:.1f}x",
                'info': f"Defocus: {row.defocus:.3f}λ | Astig: {row.astigmatism:.3f}λ | Strehl: {row.strehl_ratio:.4f} | Time: {row.compute_time:.3f}s"
            })

        # add system PSF if available
        if len(computed_rows) == len(self.table_rows) and self.system_psf_valid:
            from frontend.models.optical_row import OpticalSystemRow
            temp_row = OpticalSystemRow()
            temp_row.psf_data = self.system_psf
            temp_row.strehl_ratio = self.system_strehl_ratio
            temp_row.step_obj_microns = self.table_rows[0].step_obj_microns
            temp_row.wavelength = self.table_rows[0].wavelength
            temp_row.back_aperture = self.table_rows[0].back_aperture

            plots_to_print.append({
                'type': 'system',
                'row': temp_row,
                'title': f"System PSF (Convolution of {len(self.table_rows)} elements)",
                'info': f"Strehl: {self.system_strehl_ratio:.4f} | Time: {self.system_compute_time:.3f}s"
            })

        # print plots with optimal packing
        for plot_info in plots_to_print:
            # check if plot fits on current page
            space_needed = font_height * 3 + plot_height_estimate + footer_space
            space_available = page_rect.height() - y_pos - footer_space

            if space_available < space_needed:
                # new page needed
                self._print_footer(painter, page_rect, font_height, page_num)
                printer.newPage()
                page_num += 1
                y_pos = self._print_header(
                    painter, page_rect, font_height, page_num)

            # print plot title and info
            title_font.setPointSize(11)
            painter.setFont(title_font)
            painter.drawText(0, int(y_pos), plot_info['title'])
            y_pos += font_height * 1.2
            painter.setFont(normal_font)
            painter.drawText(0, int(y_pos), plot_info['info'])
            y_pos += font_height * 1.5

            # print plot
            actual_plot_height = self._print_single_psf(
                painter, int(y_pos), page_rect.width(), plot_info['row'])
            y_pos += actual_plot_height + font_height * 1

        self._print_footer(painter, page_rect, font_height, page_num)
        painter.end()
        logger.info(f"Report printed successfully ({page_num} pages)")

    def _print_header(self, painter, page_rect, font_height, page_num):
        """print page header, returns y_pos after header"""
        from datetime import datetime
        y_pos = 0
        painter.drawLine(0, y_pos, int(page_rect.width()), y_pos)
        painter.drawText(0, y_pos - int(font_height * 0.5),
                         "ITMO University - PSF Calculator Report")
        painter.drawText(int(page_rect.width() - 200), y_pos - int(font_height * 0.5),
                         datetime.now().strftime("%Y-%m-%d %H:%M"))
        return font_height * 2

    def _print_footer(self, painter, page_rect, font_height, page_num):
        """print page footer"""
        footer_y = int(page_rect.height() - font_height * 1.8)
        painter.drawLine(0, footer_y, int(page_rect.width()), footer_y)
        painter.drawText(0, int(page_rect.height() - font_height * 0.5),
                         f"Generated by PSF Calculator | Page {page_num}")

    def _generate_parameters_html(self):
        """generate HTML table with parameters"""
        html = "<h3 style='color: black;'>Optical System Parameters</h3>"
        html += "<table border='1' cellspacing='0' cellpadding='3' style='border-collapse: collapse; font-size: 9pt;'>"
        html += "<tr style='background-color: #4CAF50; color: white;'>"
        html += "<th>Row</th><th>λ [μm]</th><th>NA</th><th>Mag</th>"
        html += "<th>Defocus [λ]</th><th>Astig [λ]</th>"
        html += "<th>Step Obj [c.u.]</th><th>Step Obj [μm]</th>"
        html += "<th>Step Im [c.u.]</th><th>Step Im [μm]</th>"
        html += "<th>Diam Pup [c.u.]</th><th>Step Pup [c.u.]</th>"
        html += "<th>Strehl</th><th>Status</th>"
        html += "</tr>"

        for idx, row in enumerate(self.table_rows):
            status_color = {
                "complete": "#90EE90",
                "computing": "#FFFF99",
                "error": "#FFB6C1",
                "not_computed": "#FFFFFF"
            }.get(row.status, "#FFFFFF")

            html += f"<tr style='background-color: {status_color}; color: black;'>"
            html += f"<td>{idx + 1}</td>"
            html += f"<td>{row.wavelength:.3f}</td>"
            html += f"<td>{row.back_aperture:.3f}</td>"
            html += f"<td>{row.magnification:.1f}</td>"
            html += f"<td>{row.defocus:.3f}</td>"
            html += f"<td>{row.astigmatism:.3f}</td>"
            html += f"<td>{row.step_obj_can:.6f}</td>"
            html += f"<td>{row.step_obj_microns:.6f}</td>"
            html += f"<td>{row.step_im_can:.6f}</td>"
            html += f"<td>{row.step_im_microns:.6f}</td>"
            html += f"<td>{row.diam_pupil:.3f}</td>"
            html += f"<td>{row.step_pupil:.6f}</td>"
            if row.status == "complete":
                html += f"<td>{row.strehl_ratio:.4f}</td>"
            else:
                html += "<td>N/A</td>"
            html += f"<td>{row.status}</td>"
            html += "</tr>"

        html += "</table>"

        return html

    def _print_single_psf(self, painter, y_pos, width, row):
        """print PSF plots for a single row"""
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        from PyQt6.QtGui import QImage

        if row.psf_data is None:
            return 0

        psf = row.psf_data
        size = psf.shape[0]
        psf_normalized = psf / np.max(psf) if np.max(psf) > 0 else psf

        # create matplotlib figure
        fig = Figure(figsize=(10, 3.5), dpi=100)

        # plot 1: cross sections
        ax1 = fig.add_subplot(1, 2, 1)
        center_idx = size // 2

        # always use microns for print
        coords = np.arange(size) * row.step_obj_microns
        coords = coords - coords[size // 2]
        unit_label = 'μm'

        x_section = psf_normalized[center_idx, :]
        ax1.plot(coords, x_section, 'r-', label='X section', linewidth=2)
        y_section = psf_normalized[:, center_idx]
        ax1.plot(coords, y_section, 'b-', label='Y section', linewidth=2)
        ax1.set_xlabel(f'Position [{unit_label}]')
        ax1.set_ylabel('Normalized Intensity')
        ax1.set_title('PSF Cross-Sections')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # plot 2: 2D PSF
        ax2 = fig.add_subplot(1, 2, 2)
        extent = [coords[0], coords[-1], coords[0], coords[-1]]
        im = ax2.imshow(psf_normalized, cmap='gray', extent=extent,
                        origin='lower', aspect='equal', vmin=0, vmax=1)
        ax2.set_xlabel(f'X [{unit_label}]')
        ax2.set_ylabel(f'Y [{unit_label}]')
        ax2.set_title('2D PSF')
        fig.colorbar(im, ax=ax2, label='Normalized Intensity')

        fig.tight_layout()

        # render figure to QImage
        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        buf = canvas.buffer_rgba()
        width_px, height_px = canvas.get_width_height()
        qimage = QImage(buf, width_px, height_px,
                        QImage.Format.Format_RGBA8888)

        # scale to fit page width
        target_width = int(width * 0.9)
        target_height = int(height_px * target_width / width_px)

        painter.drawImage(
            QRectF(0, y_pos, target_width, target_height), qimage)

        return target_height
