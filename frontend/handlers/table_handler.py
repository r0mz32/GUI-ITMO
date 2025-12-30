# table operations handler

import logging
import random
from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush

logger = logging.getLogger(__name__)


class TableHandler:
    """handles all table-related operations"""

    def __init__(self, table_widget, table_rows, psf_tab_ref):
        self.table = table_widget
        self.rows = table_rows
        self.parent = psf_tab_ref

    def get_source_param_column(self) -> int:
        """get column index of current source parameter"""
        choice = self.parent.param_choice_combo.currentText()
        units = self.parent.source_param_units_combo.currentText()

        if choice == 'Diam pupil':
            return self.parent.COL_DIAM_PUP
        elif choice == 'Step pupil':
            return self.parent.COL_STEP_PUP
        elif choice == 'Step object':
            return self.parent.COL_STEP_OBJ_CAN if units == 'c.u.' else self.parent.COL_STEP_OBJ_UM
        elif choice == 'Step image':
            return self.parent.COL_STEP_IM_CAN if units == 'c.u.' else self.parent.COL_STEP_IM_UM
        return -1

    def add_row(self, row) -> int:
        """add row to table and data"""
        idx = len(self.rows)
        self.rows.append(row)

        self.parent._recalculate_row_params(idx)
        self.insert_table_row(idx)

        # invalidate system PSF
        self.parent.system_psf_valid = False

        return idx

    def insert_table_row(self, idx: int):
        """insert row into QTableWidget"""
        from frontend.models.optical_row import OpticalSystemRow

        row_data = self.rows[idx]

        self.table.blockSignals(True)
        self.table.insertRow(idx)

        source_col = self.get_source_param_column()

        # editable: basic params
        self.table.setItem(idx, self.parent.COL_LAMBDA,
                          QTableWidgetItem(f"{row_data.wavelength:.3f}"))
        self.table.setItem(idx, self.parent.COL_NA,
                          QTableWidgetItem(f"{row_data.back_aperture:.2f}"))
        self.table.setItem(idx, self.parent.COL_MAG,
                          QTableWidgetItem(f"{row_data.magnification:.1f}"))
        self.table.setItem(idx, self.parent.COL_DEFOC,
                          QTableWidgetItem(f"{row_data.defocus:.2f}"))
        self.table.setItem(idx, self.parent.COL_ASTIG,
                          QTableWidgetItem(f"{row_data.astigmatism:.2f}"))

        # computed columns - all read-only and gray
        for col in range(self.parent.COL_STEP_OBJ_CAN, self.parent.COL_STEP_PUP + 1):
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
        self.table.setItem(idx, self.parent.COL_STREHL, item)

        # status (read-only)
        item = QTableWidgetItem(row_data.status)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(idx, self.parent.COL_STATUS, item)

        self.update_table_row(idx)
        self.table.blockSignals(False)

    def update_table_row(self, idx: int):
        """update table display from row data"""
        if idx < 0 or idx >= len(self.rows):
            return

        row_data = self.rows[idx]

        self.table.blockSignals(True)

        # update input params (editable columns)
        self.table.item(idx, self.parent.COL_LAMBDA).setText(
            f"{row_data.wavelength:.3f}")
        self.table.item(idx, self.parent.COL_NA).setText(
            f"{row_data.back_aperture:.2f}")
        self.table.item(idx, self.parent.COL_MAG).setText(
            f"{row_data.magnification:.1f}")
        self.table.item(idx, self.parent.COL_DEFOC).setText(
            f"{row_data.defocus:.2f}")
        self.table.item(idx, self.parent.COL_ASTIG).setText(
            f"{row_data.astigmatism:.2f}")

        # update computed params
        self.table.item(idx, self.parent.COL_STEP_OBJ_CAN).setText(
            f"{row_data.step_obj_can:.6f}")
        self.table.item(idx, self.parent.COL_STEP_OBJ_UM).setText(
            f"{row_data.step_obj_microns:.6f}")
        self.table.item(idx, self.parent.COL_STEP_IM_CAN).setText(
            f"{row_data.step_im_can:.6f}")
        self.table.item(idx, self.parent.COL_STEP_IM_UM).setText(
            f"{row_data.step_im_microns:.6f}")
        self.table.item(idx, self.parent.COL_DIAM_PUP).setText(
            f"{row_data.diam_pupil:.3f}")
        self.table.item(idx, self.parent.COL_STEP_PUP).setText(
            f"{row_data.step_pupil:.6f}")

        # update strehl
        if row_data.status == "complete":
            self.table.item(idx, self.parent.COL_STREHL).setText(
                f"{row_data.strehl_ratio:.4f}")
        else:
            self.table.item(idx, self.parent.COL_STREHL).setText("—")

        # update status
        self.table.item(idx, self.parent.COL_STATUS).setText(row_data.status)

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
        for col in [self.parent.COL_LAMBDA, self.parent.COL_NA, self.parent.COL_MAG,
                    self.parent.COL_DEFOC, self.parent.COL_ASTIG]:
            self.table.item(idx, col).setBackground(QBrush(color))

        # update colors for computed columns (source parameter highlighting)
        source_col = self.get_source_param_column()
        for col in range(self.parent.COL_STEP_OBJ_CAN, self.parent.COL_STEP_PUP + 1):
            item = self.table.item(idx, col)
            if item:
                if col == source_col:
                    item.setBackground(QBrush(QColor(100, 150, 200)))  # blue
                else:
                    item.setBackground(QBrush(QColor(80, 80, 80)))  # dark gray

        self.table.blockSignals(False)

    def delete_row(self, idx: int, clear_plots: bool = True):
        """delete a row"""
        if idx < 0 or idx >= len(self.rows):
            return

        # remember if selected before deletion
        is_selected = (self.parent.selected_row_idx == idx)
        logger.info(f"Deleting row {idx + 1}, is_selected={is_selected}, clear_plots={clear_plots}")

        del self.rows[idx]
        self.table.removeRow(idx)

        # invalidate system PSF
        self.parent.system_psf_valid = False

        # if deleted row was selected and clear_plots is True, clear plots
        if is_selected and clear_plots:
            self.parent._clear_plots()

    def insert_row_before(self, idx: int):
        """insert new row before selected row"""
        from frontend.models.optical_row import OpticalSystemRow

        if idx < 0 or idx >= len(self.rows):
            return

        new_row = OpticalSystemRow()

        # insert into data list
        self.rows.insert(idx, new_row)

        # recalculate parameters
        self.parent._recalculate_row_params(idx)

        # insert into table widget
        self.insert_table_row(idx)

        # invalidate system PSF
        self.parent.system_psf_valid = False

        logger.info(f"Inserted row before {idx + 1}")

    def insert_row_after(self, idx: int):
        """insert new row after selected row"""
        from frontend.models.optical_row import OpticalSystemRow

        if idx < 0 or idx >= len(self.rows):
            return

        new_row = OpticalSystemRow()
        insert_pos = idx + 1

        # insert into data list
        self.rows.insert(insert_pos, new_row)

        # recalculate parameters
        self.parent._recalculate_row_params(insert_pos)

        # insert into table widget
        self.insert_table_row(insert_pos)

        # invalidate system PSF
        self.parent.system_psf_valid = False

        logger.info(f"Inserted row after {idx + 1}")

    def randomize_row(self, idx: int):
        """randomize row parameters (only NA, Mag, Defocus, Astig)"""
        if idx < 0 or idx >= len(self.rows):
            return

        row = self.rows[idx]

        # randomize only NA, Magnification, Defocus, Astigmatism
        # wavelength stays the same
        row.back_aperture = random.uniform(0.5, 1.5)
        row.magnification = random.uniform(50, 200)
        row.defocus = random.uniform(-2.0, 2.0)
        row.astigmatism = random.uniform(-2.0, 2.0)

        # do NOT randomize wavelength, sample_size or source parameter

        row.status = "not_computed"
        row.strehl_ratio = 0.0
        row.psf_data = None

        # invalidate system PSF
        self.parent.system_psf_valid = False

        # recalculate dependent parameters
        self.parent._recalculate_row_params(idx)
        self.update_table_row(idx)

        logger.info(f"Randomized row {idx + 1} (NA, Mag, Defocus, Astig)")

    def reset_row(self, idx: int):
        """reset row to defaults"""
        from frontend.models.optical_row import OpticalSystemRow

        if idx < 0 or idx >= len(self.rows):
            return

        defaults = OpticalSystemRow()
        row = self.rows[idx]
        row.wavelength = defaults.wavelength
        row.back_aperture = defaults.back_aperture
        row.magnification = defaults.magnification
        row.defocus = defaults.defocus
        row.astigmatism = defaults.astigmatism
        row.status = "not_computed"
        row.strehl_ratio = 0.0
        row.psf_data = None

        # invalidate system PSF
        self.parent.system_psf_valid = False

        # recalculate dependent parameters
        self.parent._recalculate_row_params(idx)
        self.update_table_row(idx)

        logger.info(f"Reset row {idx + 1} to defaults")

    def refresh_column_colors(self):
        """refresh column colors after source param change"""
        source_col = self.get_source_param_column()

        for row_idx in range(len(self.rows)):
            for col in range(self.parent.COL_STEP_OBJ_CAN, self.parent.COL_STEP_PUP + 1):
                item = self.table.item(row_idx, col)
                if item:
                    if col == source_col:
                        item.setBackground(QBrush(QColor(100, 150, 200)))  # blue
                    else:
                        item.setBackground(QBrush(QColor(80, 80, 80)))  # dark gray
